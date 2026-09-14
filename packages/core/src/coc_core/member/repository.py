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

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        """우리 식별자로 한 명. 없으면 None."""
        ...

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        """CoC 태그로 한 명. 없으면 None."""
        ...

    async def upsert_many(self, members: list[ClanMember]) -> int:
        """태그를 열쇠로 넣거나 갱신하고, 새로 들어온 수를 돌려준다.

        description 과 created_at 은 갱신하지 않는다. 관리자가 적은 메모가
        동기화에 지워지면 안 되고, 처음 본 시각은 처음 한 번만 정해진다.
        """
        ...

    async def update_managed(self, member: ClanMember) -> None:
        """우리가 정하는 값만 덮어쓴다.

        grade, grade_reason, warnings, description, updated_at 다섯이다.
        이름·직책·트로피처럼 CoC 가 주인인 값은 건드리지 않는다. 그런 값은
        동기화가 맡으므로, 여기서 함께 덮으면 두 자리가 같은 값을 쓰게 된다.
        """
        ...

    async def mark_inactive(self, external_ids: list[str], now: str) -> int:
        """주어진 태그들을 INACTIVE 로 내리고 그 수를 돌려준다."""
        ...


class MemberSource(Protocol):
    """클랜원 명단을 가져오는 곳. CoC API 가 그 구현이다."""

    async def fetch_members(self) -> list[dict]:
        """CoC API 가 준 그대로의 항목 목록.

        가공하지 않은 값을 넘긴다. 우리 값으로 바꾸는 일은 서비스가 한다.
        """
        ...
