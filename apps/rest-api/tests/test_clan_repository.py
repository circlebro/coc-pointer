"""D1 클랜 저장소.

가짜 D1 은 sqlite3 라서 실제 D1 과 같은 SQL 이 돈다. 여기서 검증한 질의는
배포된 D1 에서도 같은 결과를 낸다.
"""

from __future__ import annotations

import pytest
from coc_core.clan.models import Clan, ClanStatus

from adapters.clan_repository import D1ClanRepository

NOW = "2026-09-11T07:18:57Z"
LATER = "2026-09-12T07:18:57Z"


def _clan(external_id: str = "#2C8L822LQ", **overrides) -> Clan:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "display_name": "미니언즈",
        "status": ClanStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Clan(**base)


async def test_넣고_모두_읽는다(fake_db):
    repository = D1ClanRepository(fake_db)

    await repository.upsert(_clan())

    rows = await repository.find_all()
    assert [c.external_id for c in rows] == ["#2C8L822LQ"]


async def test_자료형이_그대로_돌아온다(fake_db):
    repository = D1ClanRepository(fake_db)
    await repository.upsert(_clan(status=ClanStatus.INACTIVE))

    found = await repository.find_by_external_id("#2C8L822LQ")

    assert found is not None
    assert found.status is ClanStatus.INACTIVE
    assert found.display_name == "미니언즈"
    assert found.created_at == NOW


async def test_없는_태그는_None(fake_db):
    repository = D1ClanRepository(fake_db)

    assert await repository.find_by_external_id("#없음") is None


async def test_다시_넣으면_갱신한다(fake_db):
    repository = D1ClanRepository(fake_db)
    await repository.upsert(_clan())

    await repository.upsert(_clan(display_name="미니언즈 본클", updated_at=LATER))

    found = await repository.find_by_external_id("#2C8L822LQ")
    assert found is not None
    assert found.display_name == "미니언즈 본클"
    assert found.updated_at == LATER
    assert len(await repository.find_all()) == 1  # 두 줄이 되지 않는다


async def test_처음_본_시각은_갱신하지_않는다(fake_db):
    """지나간 사실이라 덮으면 안 된다. 클랜원 쪽과 같은 규칙이다."""
    repository = D1ClanRepository(fake_db)
    await repository.upsert(_clan())

    await repository.upsert(_clan(created_at=LATER, updated_at=LATER))

    found = await repository.find_by_external_id("#2C8L822LQ")
    assert found is not None
    assert found.created_at == NOW


async def test_이름이_없어도_담긴다(fake_db):
    repository = D1ClanRepository(fake_db)

    await repository.upsert(_clan(display_name=None))

    found = await repository.find_by_external_id("#2C8L822LQ")
    assert found is not None
    assert found.display_name is None


async def test_이름_순으로_돌려준다(fake_db):
    repository = D1ClanRepository(fake_db)
    await repository.upsert(_clan("#BBB", display_name="제노스"))
    await repository.upsert(_clan("#AAA", display_name="미니언즈"))

    rows = await repository.find_all()

    assert [c.display_name for c in rows] == ["미니언즈", "제노스"]


async def test_이름_없는_클랜은_뒤로_보낸다(fake_db):
    """NULL 을 그냥 정렬하면 SQLite 는 맨 앞에 둔다. 이름 없는 줄이 목록
    첫머리에 오면 화면이 빈칸부터 보여 주게 된다."""
    repository = D1ClanRepository(fake_db)
    await repository.upsert(_clan("#AAA", display_name=None))
    await repository.upsert(_clan("#BBB", display_name="미니언즈"))

    rows = await repository.find_all()

    assert [c.display_name for c in rows] == ["미니언즈", None]


async def test_모르는_상태는_표가_거부한다(fake_db):
    """읽을 때 죽는 대신 넣을 때 막는다. CHECK 가 실제로 도는지 본다."""
    repository = D1ClanRepository(fake_db)

    with pytest.raises(Exception, match="CHECK|constraint"):
        await repository.upsert(_clan(status="KICKED"))  # type: ignore[arg-type]
