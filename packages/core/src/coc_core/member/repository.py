"""클랜원 저장소 약속.

도메인이 "이런 게 필요하다"고 선언하는 자리다. 구현은 바깥(어댑터)에 있고
도메인은 그것이 D1 인지 파일인지 모른다. Spring 의 Repository 인터페이스와
같은 자리이며, Protocol 이라 구현체가 상속을 선언하지 않아도 된다.
"""

from __future__ import annotations

from typing import Protocol

from coc_core.member.models import ClanMember


class MemberRepository(Protocol):
    """클랜원을 담고 꺼낸다."""

    async def find_all(self) -> list[ClanMember]:
        """모두. 나간 사람(INACTIVE)도 포함한다."""
        ...

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        """태그로 한 명. 없으면 None."""
        ...

    async def upsert_many(self, members: list[ClanMember]) -> int:
        """태그를 열쇠로 넣거나 갱신하고, 새로 들어온 수를 돌려준다.

        description 과 created_at 은 갱신하지 않는다. 관리자가 적은 메모가
        동기화에 지워지면 안 되고, 처음 본 시각은 처음 한 번만 정해진다.
        """
        ...

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        """주어진 태그들을 INACTIVE 로 내리고 그 수를 돌려준다."""
        ...


class MemberSource(Protocol):
    """클랜원 명단을 가져오는 곳. CoC API 가 그 구현이다."""

    async def fetch_members(self) -> list[dict]:
        """CoC API 가 준 그대로의 항목 목록.

        가공하지 않은 값을 넘긴다. 우리 값으로 바꾸는 일은 서비스가 한다.
        """
        ...
