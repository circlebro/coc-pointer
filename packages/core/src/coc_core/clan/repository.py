"""클랜 저장소와 바깥 자료의 약속.

도메인이 "이런 게 필요하다"고 선언하는 자리다. 구현은 바깥(어댑터)에 있고
도메인은 그것이 D1 인지 파일인지 모른다. Protocol 이라 구현체가 상속을
선언하지 않아도 된다.
"""

from __future__ import annotations

from typing import Any, Protocol

from coc_core.clan.models import Clan


class ClanRepository(Protocol):
    """클랜을 담고 꺼낸다."""

    async def find_all(self) -> list[Clan]:
        """모두. 더는 다루지 않는 것(INACTIVE)도 포함한다."""
        ...

    async def find_by_external_id(self, external_id: str) -> Clan | None:
        """CoC 태그로 찾는다. 없으면 None.

        태그로 찾는 까닭은 그것이 바뀌지 않기 때문이다. 이름은 바뀌고
        우리 식별자는 처음 담을 때 우리가 붙인다.
        """
        ...

    async def upsert(self, clan: Clan) -> None:
        """있으면 갱신하고 없으면 넣는다. 기준은 external_id 다."""
        ...


class ClanSource(Protocol):
    """클랜 자료를 가져오는 곳. 지금은 CoC API 다."""

    async def fetch_clan(self) -> dict[str, Any]:
        """CoC 가 준 그대로. 우리 값으로 바꾸는 일은 서비스가 한다."""
        ...
