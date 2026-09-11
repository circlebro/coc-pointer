"""D1 클랜원 저장소.

가짜 D1 은 sqlite3 라서 실제 D1 과 같은 SQL 이 돈다. 여기서 검증한 질의는
배포된 D1 에서도 같은 결과를 낸다.
"""

from __future__ import annotations

from coc_core.member.models import ClanMember, ClanRole, MemberStatus

from adapters.member_repository import D1MemberRepository

NOW = "2026-09-10T05:30:00Z"
LATER = "2026-09-11T05:30:00Z"


def _member(tag: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{tag.lstrip('#')}",
        "tag": tag,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donations_received": 50,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


async def test_넣고_모두_읽는다(fake_db):
    repository = D1MemberRepository(fake_db)

    added = await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    assert added == 2
    rows = await repository.find_all()
    assert sorted(m.name for m in rows) == ["도토리", "히로"]


async def test_자료형이_그대로_돌아온다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", role=ClanRole.ADMIN)])

    found = await repository.find_by_tag("#A")

    assert found is not None
    assert found.role is ClanRole.ADMIN
    assert found.status is MemberStatus.ACTIVE
    assert found.townhall == 16


async def test_없는_태그는_None(fake_db):
    repository = D1MemberRepository(fake_db)

    assert await repository.find_by_tag("#없음") is None


async def test_다시_넣으면_갱신하고_새로_센_수는_0(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    added = await repository.upsert_many([_member("#A", "도토리2", updated_at=LATER)])

    assert added == 0
    found = await repository.find_by_tag("#A")
    assert found is not None
    assert found.name == "도토리2"
    assert found.updated_at == LATER


async def test_관리자_메모와_처음_본_시각은_지켜진다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", description="추방 예정")])

    await repository.upsert_many([_member("#A", "도토리", description=None, created_at=LATER)])

    found = await repository.find_by_tag("#A")
    assert found is not None
    assert found.description == "추방 예정"
    assert found.created_at == NOW


async def test_INACTIVE_로_내린다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    count = await repository.mark_inactive(["#A"], LATER)

    assert count == 1
    by_tag = {m.tag: m for m in await repository.find_all()}
    assert by_tag["#A"].status is MemberStatus.INACTIVE
    assert by_tag["#A"].updated_at == LATER
    assert by_tag["#B"].status is MemberStatus.ACTIVE


async def test_모르는_직책도_담긴다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", role=ClanRole.UNKNOWN)])

    found = await repository.find_by_tag("#A")

    assert found is not None
    assert found.role is ClanRole.UNKNOWN
