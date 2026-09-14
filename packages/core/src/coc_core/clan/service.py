"""클랜 로직.

CoC 가 주는 것 가운데 우리가 보는 것은 태그와 이름뿐이다. 마크·레벨·점수·전적은
일부러 버린다. 우리가 사본을 들고 있으면 두 곳에서 관리하게 되고, 동기화 사이에
화면이 낡은 값을 보여 준다. 필요하면 external_id 로 CoC 에 물으면 된다.
"""

from __future__ import annotations

import uuid

from coc_core.clan.models import Clan, ClanStatus
from coc_core.clan.repository import ClanRepository, ClanSource


class ClanService:
    """클랜을 다룬다."""

    def __init__(self, repository: ClanRepository, source: ClanSource | None = None) -> None:
        self._repository = repository
        self._source = source

    async def find_all(self) -> list[Clan]:
        """우리가 아는 클랜 모두."""
        return await self._repository.find_all()

    async def sync(self, now: str) -> Clan:
        """CoC 에서 받아 우리 쪽에 맞춘다.

        우리가 정한 것(식별자, 우리가 붙인 이름, 처음 본 시각)은 지킨다.
        CoC 이름은 우리 이름이 아직 비어 있을 때만 쓴다.
        """
        if self._source is None:
            raise RuntimeError("동기화하려면 source 가 있어야 합니다")

        raw = await self._source.fetch_clan()
        external_id = raw["tag"]
        before = await self._repository.find_by_external_id(external_id)

        clan = Clan(
            id=before.id if before else str(uuid.uuid4()),
            external_id=external_id,
            # 우리가 붙인 이름이 있으면 지킨다. 없을 때만 CoC 이름으로 채운다.
            display_name=(
                before.display_name if before and before.display_name else raw.get("name")
            ),
            status=before.status if before else ClanStatus.ACTIVE,
            created_at=before.created_at if before else now,
            updated_at=now,
        )
        await self._repository.upsert(clan)
        return clan
