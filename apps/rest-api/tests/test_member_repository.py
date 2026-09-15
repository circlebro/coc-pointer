"""D1 클랜원 저장소.

가짜 D1 은 sqlite3 라서 실제 D1 과 같은 SQL 이 돈다. 여기서 검증한 질의는
배포된 D1 에서도 같은 결과를 낸다.
"""

from __future__ import annotations

import pytest
from coc_core.member.models import ClanMember, MemberStatus

from adapters.member_repository import D1MemberRepository

NOW = "2026-09-10T05:30:00Z"
LATER = "2026-09-11T05:30:00Z"


def _member(external_id: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "display_name": None,
        "status": MemberStatus.ACTIVE,
        "warnings": 0,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
        "synced_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


async def test_등록하고_모두_읽는다(fake_db):
    repository = D1MemberRepository(fake_db)

    added = await repository.register_many([_member("#A"), _member("#B")])

    assert added == 2
    rows = await repository.find_all()
    assert sorted(m.external_id for m in rows) == ["#A", "#B"]


async def test_자료형이_그대로_돌아온다(fake_db):
    """열거형이 문자열이 아니라 우리 자료형으로 돌아와야 한다."""
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A", display_name="도토리형", warnings=2)])

    found = await repository.find_by_external_id("#A")

    assert found is not None
    assert found.status is MemberStatus.ACTIVE
    assert found.display_name == "도토리형"
    assert found.warnings == 2
    assert found.synced_at == NOW


async def test_다시_등록하면_새로_센_수는_0(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A")])

    added = await repository.register_many([_member("#A", updated_at=LATER, synced_at=LATER)])

    assert added == 0
    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.synced_at == LATER


async def test_동기화는_사람이_적은_값을_덮지_않는다(fake_db):
    """표기·경고·메모와 처음 본 시각은 동기화가 건드리면 안 된다."""
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A")])
    await repository.update_managed(
        _member("#A", display_name="도토리형", warnings=2, description="메모", updated_at=LATER)
    )

    await repository.register_many(
        [_member("#A", display_name=None, warnings=0, description=None, created_at=LATER)]
    )

    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.display_name == "도토리형"
    assert found.warnings == 2
    assert found.description == "메모"
    assert found.created_at == NOW


async def test_INACTIVE_로_내린다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A")])

    left = await repository.mark_inactive(["#A"], LATER)

    assert left == 1
    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.status is MemberStatus.INACTIVE


async def test_우리_식별자로_찾는다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A"), _member("#B")])

    found = await repository.find_by_id("uuid-B")

    assert found is not None
    assert found.external_id == "#B"


async def test_없는_식별자면_None(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A")])

    assert await repository.find_by_id("uuid-없음") is None


async def test_사람이_정하는_값만_덮는다(fake_db):
    """수정이 status 나 synced_at 까지 덮으면 동기화와 같은 열을 두 자리에서 쓴다."""
    repository = D1MemberRepository(fake_db)
    await repository.register_many([_member("#A")])

    await repository.update_managed(
        _member(
            "#A",
            display_name="도토리형",
            warnings=3,
            description="메모",
            status=MemberStatus.INACTIVE,
            updated_at=LATER,
            synced_at=LATER,
        )
    )

    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.display_name == "도토리형"
    assert found.warnings == 3
    assert found.description == "메모"
    assert found.updated_at == LATER
    assert found.status is MemberStatus.ACTIVE  # 동기화가 맡는 값은 그대로다
    assert found.synced_at == NOW


async def test_모르는_상태는_표가_거부한다(fake_db):
    """읽을 때 죽는 대신 넣을 때 막는다."""
    repository = D1MemberRepository(fake_db)

    with pytest.raises(Exception, match="CHECK|constraint"):
        await repository.register_many([_member("#C", status="GONE")])  # type: ignore[arg-type]


async def test_CoC_가_주인인_열은_표에_없다(fake_db):
    """사본을 들면 두 곳에서 관리하게 되고 언젠가 어긋난다."""
    rows = await fake_db.prepare("PRAGMA table_info(clan_members)").all()
    columns = {row.name for row in rows.results}

    assert columns == {
        "id",
        "external_id",
        "display_name",
        "status",
        "warnings",
        "description",
        "created_at",
        "updated_at",
        "synced_at",
    }
