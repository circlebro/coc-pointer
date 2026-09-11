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
from dataclasses import dataclass, field

from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from coc_core.member.repository import MemberRepository, MemberSource


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
        existing = {m.tag: m for m in await self._repository.find_all()}

        unknown_roles: dict[str, int] = {}
        members: list[ClanMember] = []

        for raw in raw_members:
            raw_role = raw.get("role", "")
            role = ClanRole.from_coc(raw_role)
            if role is ClanRole.UNKNOWN:
                unknown_roles[raw_role] = unknown_roles.get(raw_role, 0) + 1

            tag = raw["tag"]
            before = existing.get(tag)
            members.append(
                ClanMember(
                    id=before.id if before else str(uuid.uuid4()),
                    tag=tag,
                    name=raw["name"],
                    role=role,
                    status=MemberStatus.ACTIVE,
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

        seen = {m.tag for m in members}
        gone = [
            tag
            for tag, m in existing.items()
            if tag not in seen and m.status is MemberStatus.ACTIVE
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

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        return await self._repository.find_by_tag(tag)
