"""클랜원 저장소와 바깥 자료원의 약속.

도메인이 "이런 게 필요하다"고 선언하는 자리다. 구현은 바깥(어댑터)에 있고
도메인은 그것이 D1 인지 파일인지 모른다. Spring 의 Repository 인터페이스와
같은 자리이며, Protocol 이라 구현체가 상속을 선언하지 않아도 된다.
"""

from __future__ import annotations

from typing import Protocol

from coc_core.member.models import ClanMember, MemberProfile


class MemberRepository(Protocol):
    """클랜원을 담고 꺼낸다. 우리가 만들어 낸 값만 다룬다."""

    async def find_all(self) -> list[ClanMember]:
        """모두. 나간 사람(INACTIVE)도 포함한다."""
        ...

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        """우리 식별자로 한 명. 없으면 None."""
        ...

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        """CoC 태그로 한 명. 없으면 None."""
        ...

    async def register_many(self, members: list[ClanMember]) -> int:
        """처음 보는 사람을 등록하고, 이미 있는 사람은 본 시각만 올린다.

        새로 등록한 수를 돌려준다. 사람이 적은 값(표기·경고·메모)과 처음 본
        시각은 건드리지 않는다. 동기화가 그것을 덮으면 적을 때마다 지워진다.
        """
        ...

    async def mark_inactive(self, external_ids: list[str], now: str) -> int:
        """주어진 태그들을 INACTIVE 로 내리고 그 수를 돌려준다."""
        ...

    async def update_managed(self, member: ClanMember) -> None:
        """사람이 정하는 값만 덮어쓴다.

        display_name, warnings, description, updated_at 넷이다. 그 밖의 값은
        동기화가 맡으므로, 여기서 함께 덮으면 두 자리가 같은 열을 쓰게 된다.
        """
        ...


class MemberSource(Protocol):
    """클랜원 명단과 현황을 가져오는 곳. CoC API 가 그 구현이다."""

    async def fetch_members(self) -> list[dict]:
        """클랜 명단. CoC 가 준 그대로의 항목 목록.

        가공하지 않은 값을 넘긴다. 우리 값으로 바꾸는 일은 서비스가 한다.
        한 번 부르면 클랜에 있는 사람 전부가 온다.
        """
        ...

    async def fetch_player(self, external_id: str) -> dict | None:
        """한 사람. 클랜을 나갔어도 계정이 살아 있으면 온다.

        계정 자체가 사라졌으면 None. CoC 가 404 로 답하는 경우다.
        """
        ...


class MemberProfileReader(Protocol):
    """현황을 우리 자료형으로 읽어 오는 곳.

    MemberSource 가 가공하지 않은 값을 주는 데 비해 이쪽은 MemberProfile 을
    돌려준다. 서비스가 CoC 표기를 알 필요가 없도록 어댑터가 경계에서 바꾼다.
    """

    async def read_clan_profiles(self) -> dict[str, MemberProfile]:
        """클랜에 있는 사람 전부. 태그를 열쇠로 한 사전. 호출은 한 번이다."""
        ...

    async def read_profile(self, external_id: str) -> MemberProfile | None:
        """한 사람. 계정이 사라졌으면 None."""
        ...
