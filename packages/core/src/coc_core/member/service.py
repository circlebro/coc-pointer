"""클랜원 서비스.

동기화와 조회를 나눈다. 동기화는 CoC API 에서 받아 우리 DB 에 맞추는 일이고,
조회는 담아 둔 것을 돌려주는 일이다.

동기화가 지켜야 할 것이 셋 있다.

- 한 사람 때문에 전체가 멈추지 않는다. 모르는 직책이 와도 그 사람만 UNKNOWN 이 된다
- 나간 사람을 지우지 않는다. status 를 INACTIVE 로 내려 과거 기록을 지킨다
- 무슨 일이 있었는지 남긴다. SyncResult 가 그 기록이다
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Final

from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus
from coc_core.member.repository import MemberRepository, MemberSource


class Unset:
    """값을 주지 않았다는 표시.

    수정에서는 "안 보냈다"와 "비워 달라"가 서로 다른 뜻이다. 둘 다 None 으로
    적으면 사유를 지우려는 요청과 사유를 건드리지 않으려는 요청을 가릴 수 없다.
    그래서 "안 보냈다" 쪽에 이 표시를 따로 쓴다.
    """

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = Unset()


@dataclass(frozen=True)
class SyncResult:
    """동기화가 무엇을 했는지.

    unknown_roles 가 비어 있지 않으면 CoC 가 우리가 모르는 값을 보냈다는 뜻이다.
    조용히 넘어가면 UNKNOWN 이 쌓이는 것을 아무도 모른다.
    """

    total: int = 0
    added: int = 0
    left: int = 0
    unknown_roles: dict[str, int] = field(default_factory=dict)


class MemberService:
    def __init__(self, repository: MemberRepository, source: MemberSource | None = None) -> None:
        """source 는 동기화할 때만 쓴다.

        조회 경로는 CoC API 를 부를 일이 없으므로 넘기지 않는다. 요청마다
        HTTP 클라이언트를 새로 만드는 낭비를 피하기 위해서다.
        """
        self._repository = repository
        self._source = source

    async def sync(self, now: str) -> SyncResult:
        """CoC API 에서 받아 우리 DB 에 맞춘다."""
        if self._source is None:
            raise RuntimeError("동기화하려면 source 가 있어야 합니다")

        raw_members = await self._source.fetch_members()
        existing = {m.external_id: m for m in await self._repository.find_all()}

        unknown_roles: dict[str, int] = {}
        members: list[ClanMember] = []

        for raw in raw_members:
            raw_role = raw.get("role", "")
            role = ClanRole.from_coc(raw_role)
            if role is ClanRole.UNKNOWN:
                unknown_roles[raw_role] = unknown_roles.get(raw_role, 0) + 1

            external_id = raw["tag"]  # CoC 가 주는 이름은 tag 다
            before = existing.get(external_id)
            members.append(
                ClanMember(
                    id=before.id if before else str(uuid.uuid4()),
                    external_id=external_id,
                    name=raw["name"],
                    role=role,
                    status=MemberStatus.ACTIVE,
                    # 등급·사유·경고는 우리가 정하는 값이라 동기화가 덮지 않는다.
                    # 처음 보는 사람은 경쟁으로 둔다.
                    grade=before.grade if before else MemberGrade.COMPETING,
                    grade_reason=before.grade_reason if before else None,
                    warnings=before.warnings if before else 0,
                    townhall=raw.get("townHallLevel"),
                    trophies=raw.get("trophies"),
                    donations=raw.get("donations"),
                    donations_received=raw.get("donationsReceived"),
                    description=before.description if before else None,
                    created_at=before.created_at if before else now,
                    updated_at=now,
                )
            )

        added = await self._repository.upsert_many(members)

        seen = {m.external_id for m in members}
        gone = [
            external_id
            for external_id, m in existing.items()
            if external_id not in seen and m.status is MemberStatus.ACTIVE
        ]
        left = await self._repository.mark_inactive(gone, now) if gone else 0

        return SyncResult(
            total=len(members),
            added=added,
            left=left,
            unknown_roles=unknown_roles,
        )

    async def find_all(self) -> list[ClanMember]:
        return await self._repository.find_all()

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        return await self._repository.find_by_id(member_id)

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        return await self._repository.find_by_external_id(external_id)

    async def update_managed(
        self,
        member_id: str,
        now: str,
        *,
        grade: MemberGrade | Unset = UNSET,
        grade_reason: str | None | Unset = UNSET,
        warnings: int | Unset = UNSET,
        description: str | None | Unset = UNSET,
    ) -> ClanMember | None:
        """우리가 정하는 값을 고친다. 그 식별자를 가진 사람이 없으면 None.

        넘기지 않은 값은 그대로 둔다. 그래서 등급만 바꾸려는 요청이 관리자
        메모를 함께 지우는 일이 생기지 않는다.

        경고 횟수는 음수가 될 수 없다. 횟수를 세는 값이라 음수는 뜻을 갖지 않고,
        한번 들어가면 화면과 집계가 함께 어긋난다.
        """
        if not isinstance(warnings, Unset) and warnings < 0:
            raise ValueError("경고 횟수는 0 이상이어야 합니다")

        before = await self._repository.find_by_id(member_id)
        if before is None:
            return None

        after = replace(
            before,
            grade=before.grade if isinstance(grade, Unset) else grade,
            grade_reason=before.grade_reason if isinstance(grade_reason, Unset) else grade_reason,
            warnings=before.warnings if isinstance(warnings, Unset) else warnings,
            description=before.description if isinstance(description, Unset) else description,
            updated_at=now,
        )
        await self._repository.update_managed(after)
        return after
