"""클랜 서비스.

저장소와 CoC 자리에 가짜를 끼워 로직만 본다. 도메인은 D1 도 HTTP 도 모른다.
"""

from __future__ import annotations

import pytest

from coc_core.clan.models import Clan, ClanStatus
from coc_core.clan.service import ClanService

NOW = "2026-09-11T07:18:57Z"
LATER = "2026-09-12T07:18:57Z"

# CoC 가 주는 것 중 우리가 보는 것은 둘뿐이다. 나머지는 일부러 무시한다.
COC_CLAN = {
    "tag": "#2C8L822LQ",
    "name": "미니언즈",
    "clanLevel": 11,
    "clanPoints": 117250,
    "badgeUrls": {"small": "https://example.test/s.png"},
    "warWins": 28,
}


class FakeRepository:
    def __init__(self, clans: list[Clan] | None = None) -> None:
        self.clans = list(clans or [])

    async def find_all(self) -> list[Clan]:
        return list(self.clans)

    async def find_by_external_id(self, external_id: str) -> Clan | None:
        return next((c for c in self.clans if c.external_id == external_id), None)

    async def upsert(self, clan: Clan) -> None:
        self.clans = [c for c in self.clans if c.external_id != clan.external_id]
        self.clans.append(clan)


class FakeSource:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload if payload is not None else COC_CLAN

    async def fetch_clan(self) -> dict:
        return self.payload


async def test_처음_보면_새로_담는다():
    repository = FakeRepository()

    clan = await ClanService(repository, FakeSource()).sync(now=NOW)

    assert clan.external_id == "#2C8L822LQ"
    assert clan.display_name == "미니언즈"  # 첫 동기화 때 CoC 이름으로 채운다
    assert clan.status is ClanStatus.ACTIVE
    assert clan.created_at == NOW
    assert clan.id  # 우리 식별자를 붙인다


async def test_우리가_붙인_이름은_지켜진다():
    """게임에서 이름이 바뀌어도 우리 표기는 그대로 둔다.

    이것이 display_name 을 우리가 관리하는 까닭이다. CoC 이름을 그대로
    받아쓸 것이면 담을 필요가 없다.
    """
    before = Clan(
        id="uuid-1",
        external_id="#2C8L822LQ",
        display_name="미니언즈 본클",
        status=ClanStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    repository = FakeRepository([before])

    after = await ClanService(repository, FakeSource()).sync(now=LATER)

    assert after.display_name == "미니언즈 본클"  # CoC 의 "미니언즈"로 덮지 않는다
    assert after.id == "uuid-1"  # 식별자도 지킨다
    assert after.created_at == NOW  # 처음 본 시각도 지킨다
    assert after.updated_at == LATER  # 갱신 시각만 바뀐다


async def test_이름이_비어_있으면_그때_채운다():
    """어떤 까닭으로 이름 없이 들어온 행은 다음 동기화에서 채워진다."""
    before = Clan(
        id="uuid-1",
        external_id="#2C8L822LQ",
        display_name=None,
        status=ClanStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )

    after = await ClanService(FakeRepository([before]), FakeSource()).sync(now=LATER)

    assert after.display_name == "미니언즈"


async def test_CoC_가_주는_나머지는_버린다():
    """마크·레벨·점수·전적이 자료형에 스며들지 않는지 본다."""
    repository = FakeRepository()

    await ClanService(repository, FakeSource()).sync(now=NOW)

    stored = repository.clans[0]
    assert not hasattr(stored, "clan_level")
    assert not hasattr(stored, "badge_small")
    assert not hasattr(stored, "war_wins")


async def test_저장소에_담긴다():
    repository = FakeRepository()

    await ClanService(repository, FakeSource()).sync(now=NOW)

    assert len(repository.clans) == 1
    assert repository.clans[0].external_id == "#2C8L822LQ"


async def test_source_가_없으면_동기화하지_않는다():
    """조회만 할 때는 CoC 를 끼우지 않는다. 실수로 부르면 알려 준다."""
    service = ClanService(FakeRepository())

    with pytest.raises(RuntimeError, match="source"):
        await service.sync(now=NOW)


async def test_모두_돌려준다():
    clans = [
        Clan("uuid-1", "#AAA", "가", ClanStatus.ACTIVE, NOW, NOW),
        Clan("uuid-2", "#BBB", "나", ClanStatus.INACTIVE, NOW, NOW),
    ]

    found = await ClanService(FakeRepository(clans)).find_all()

    assert [c.external_id for c in found] == ["#AAA", "#BBB"]
