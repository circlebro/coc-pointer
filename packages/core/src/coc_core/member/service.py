"""클랜원 서비스.

동기화와 조회를 나눈다. 동기화는 CoC 명단을 보고 우리 명부를 맞추는 일이고,
조회는 담아 둔 것을 돌려주는 일이다.

동기화가 하는 일은 둘뿐이다.

- 처음 보는 사람을 등록한다
- 명단에서 사라진 사람을 INACTIVE 로 내린다

이름·직책·트로피를 받아 적지 않는다. CoC 가 주인인 값이라 사본을 들면 두 곳에서
관리하게 되고 언젠가 어긋난다. 필요하면 그때 CoC 에 묻는다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Final

from coc_core.member.models import ClanMember, MemberProfile, MemberStatus
from coc_core.member.repository import MemberProfileReader, MemberRepository, MemberSource


class Unset:
    """값을 주지 않았다는 표시.

    수정에서는 "안 보냈다"와 "비워 달라"가 서로 다른 뜻이다. 둘 다 None 으로
    적으면 표기를 지우려는 요청과 표기를 건드리지 않으려는 요청을 가릴 수 없다.
    그래서 "안 보냈다" 쪽에 이 표시를 따로 쓴다.
    """

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = Unset()


@dataclass(frozen=True)
class SyncResult:
    """동기화가 무엇을 했는지.

    무슨 일이 있었는지 남기지 않으면, 사람이 통째로 사라져도 아무도 모른다.
    """

    total: int = 0
    added: int = 0
    left: int = 0
    unknown_roles: dict[str, int] = field(default_factory=dict)


class MemberService:
    def __init__(
        self,
        repository: MemberRepository,
        source: MemberSource | None = None,
        profiles: MemberProfileReader | None = None,
    ) -> None:
        """source 는 동기화할 때만, profiles 는 현황을 함께 줄 때만 쓴다.

        명단만 돌려주는 요청은 CoC 를 부를 일이 없으므로 둘 다 넘기지 않는다.
        요청마다 HTTP 클라이언트를 새로 만드는 낭비를 피하기 위해서다.
        """
        self._repository = repository
        self._source = source
        self._profiles = profiles

    async def sync(self, now: str) -> SyncResult:
        """CoC 명단을 보고 우리 명부를 맞춘다. 값은 받아 적지 않는다."""
        if self._source is None:
            raise RuntimeError("동기화하려면 source 가 있어야 합니다")

        raw_members = await self._source.fetch_members()
        existing = {m.external_id: m for m in await self._repository.find_all()}

        members: list[ClanMember] = []
        for raw in raw_members:
            external_id = raw["tag"]  # CoC 가 주는 이름은 tag 다
            before = existing.get(external_id)
            members.append(
                ClanMember(
                    id=before.id if before else str(uuid.uuid4()),
                    external_id=external_id,
                    # 사람이 적는 값은 그대로 둔다. 처음 보는 사람은 빈 채로 시작한다
                    display_name=before.display_name if before else None,
                    status=MemberStatus.ACTIVE,
                    warnings=before.warnings if before else 0,
                    description=before.description if before else None,
                    created_at=before.created_at if before else now,
                    updated_at=now,
                    synced_at=now,
                )
            )

        added = await self._repository.register_many(members)

        seen = {m.external_id for m in members}
        gone = [
            external_id
            for external_id, m in existing.items()
            if external_id not in seen and m.status is MemberStatus.ACTIVE
        ]
        left = await self._repository.mark_inactive(gone, now) if gone else 0

        return SyncResult(total=len(members), added=added, left=left)

    async def find_all(self) -> list[ClanMember]:
        return await self._repository.find_all()

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        return await self._repository.find_by_id(member_id)

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        return await self._repository.find_by_external_id(external_id)

    @property
    def can_read_profiles(self) -> bool:
        """현황을 물을 수 있는가.

        CoC 자격 증명이 없으면 조립될 때 profiles 가 비어 온다. 부르는 쪽이
        미리 알아야 500 대신 뜻이 분명한 답을 돌려줄 수 있다.
        """
        return self._profiles is not None

    async def read_clan_profiles(self) -> dict[str, MemberProfile]:
        """클랜에 있는 사람들의 현황. 태그를 열쇠로 한 사전. CoC 호출은 한 번이다.

        명단에 없는 사람(나간 사람)은 여기 들어 있지 않다. 목록에서 한 명씩 묻지
        않는 까닭은 호출이 사람 수만큼 늘고 Workers 의 하위 요청 한도에 걸리기
        때문이다. 한 명의 현황이 정확히 필요하면 read_profile 을 쓴다.
        """
        if self._profiles is None:
            raise RuntimeError("현황을 받으려면 profiles 가 있어야 합니다")
        return await self._profiles.read_clan_profiles()

    async def read_profile(self, external_id: str) -> MemberProfile | None:
        """한 사람의 현황. 클랜을 나갔어도 계정이 살아 있으면 온다.

        계정 자체가 사라졌으면 None 이다. 그 사실을 그대로 내보내고 없는 이름을
        지어내지 않는다.
        """
        if self._profiles is None:
            raise RuntimeError("현황을 받으려면 profiles 가 있어야 합니다")
        return await self._profiles.read_profile(external_id)

    async def update_managed(
        self,
        member_id: str,
        now: str,
        *,
        display_name: str | None | Unset = UNSET,
        warnings: int | Unset = UNSET,
        description: str | None | Unset = UNSET,
    ) -> ClanMember | None:
        """사람이 정하는 값을 고친다. 그 식별자를 가진 사람이 없으면 None.

        넘기지 않은 값은 그대로 둔다. 그래서 경고만 올리려는 요청이 관리자
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
            display_name=before.display_name if isinstance(display_name, Unset) else display_name,
            warnings=before.warnings if isinstance(warnings, Unset) else warnings,
            description=before.description if isinstance(description, Unset) else description,
            updated_at=now,
        )
        await self._repository.update_managed(after)
        return after
