"""D1 클랜원 저장소.

가짜 D1 은 sqlite3 라서 실제 D1 과 같은 SQL 이 돈다. 여기서 검증한 질의는
배포된 D1 에서도 같은 결과를 낸다.
"""

from __future__ import annotations

import pytest
from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus

from adapters.member_repository import D1MemberRepository

NOW = "2026-09-10T05:30:00Z"
LATER = "2026-09-11T05:30:00Z"


def _member(external_id: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "grade": MemberGrade.COMPETING,
        "grade_reason": None,
        "warnings": 0,
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

    found = await repository.find_by_external_id("#A")

    assert found is not None
    assert found.role is ClanRole.ADMIN
    assert found.status is MemberStatus.ACTIVE
    assert found.townhall == 16


async def test_없는_태그는_None(fake_db):
    repository = D1MemberRepository(fake_db)

    assert await repository.find_by_external_id("#없음") is None


async def test_다시_넣으면_갱신하고_새로_센_수는_0(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    added = await repository.upsert_many([_member("#A", "도토리2", updated_at=LATER)])

    assert added == 0
    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.name == "도토리2"
    assert found.updated_at == LATER


async def test_관리자_메모와_처음_본_시각은_지켜진다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", description="추방 예정")])

    await repository.upsert_many([_member("#A", "도토리", description=None, created_at=LATER)])

    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.description == "추방 예정"
    assert found.created_at == NOW


async def test_INACTIVE_로_내린다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    count = await repository.mark_inactive(["#A"], LATER)

    assert count == 1
    by_tag = {m.external_id: m for m in await repository.find_all()}
    assert by_tag["#A"].status is MemberStatus.INACTIVE
    assert by_tag["#A"].updated_at == LATER
    assert by_tag["#B"].status is MemberStatus.ACTIVE


async def test_모르는_직책도_담긴다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", role=ClanRole.UNKNOWN)])

    found = await repository.find_by_external_id("#A")

    assert found is not None
    assert found.role is ClanRole.UNKNOWN


async def test_등급과_사유와_경고는_갱신하지_않는다(fake_db):
    """운영진이 매긴 값이라 동기화가 덮으면 안 된다.

    서비스도 같은 판단을 하지만 여기서 한 번 더 막는다. 저장소를 직접 부르는
    자리(관리 화면, 일회성 스크립트)가 생겨도 값이 지켜져야 한다.
    """
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many(
        [_member("#A", "도토리", grade=MemberGrade.FIXED, grade_reason="길드장", warnings=2)]
    )

    # 동기화가 기본값을 들고 다시 들어온다
    await repository.upsert_many(
        [_member("#A", "도토리2", grade=MemberGrade.COMPETING, grade_reason=None, warnings=0)]
    )

    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.name == "도토리2"  # 이름은 갱신된다
    assert found.grade is MemberGrade.FIXED  # 등급은 지켜진다
    assert found.grade_reason == "길드장"
    assert found.warnings == 2


async def test_아무것도_매기지_않으면_경쟁으로_담긴다(fake_db):
    repository = D1MemberRepository(fake_db)

    await repository.upsert_many([_member("#B", "히로")])

    found = await repository.find_by_external_id("#B")
    assert found is not None
    assert found.grade is MemberGrade.COMPETING


async def test_모르는_등급은_표가_거부한다(fake_db):
    """읽을 때 죽는 대신 넣을 때 막는다. 예비를 담으려 해도 걸린다."""
    repository = D1MemberRepository(fake_db)

    with pytest.raises(Exception, match="CHECK|constraint"):
        await repository.upsert_many([_member("#C", "아무개", grade="RESERVE")])  # type: ignore[arg-type]


async def test_우리_식별자로_찾는다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    found = await repository.find_by_id("uuid-B")

    assert found is not None
    assert found.name == "히로"


async def test_없는_식별자면_None(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    assert await repository.find_by_id("uuid-없음") is None


async def test_우리가_정하는_값만_덮는다(fake_db):
    """수정이 이름과 트로피까지 덮으면 동기화와 같은 열을 두 자리에서 쓰게 된다."""
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    await repository.update_managed(
        _member(
            "#A",
            "바뀐이름",
            grade=MemberGrade.FIXED,
            grade_reason="길드장",
            warnings=3,
            description="메모",
            trophies=9999,
            updated_at=LATER,
        )
    )

    found = await repository.find_by_external_id("#A")
    assert found is not None
    assert found.grade is MemberGrade.FIXED
    assert found.grade_reason == "길드장"
    assert found.warnings == 3
    assert found.description == "메모"
    assert found.updated_at == LATER
    assert found.name == "도토리"  # CoC 가 주인인 값은 그대로다
    assert found.trophies == 4200


async def test_수정도_모르는_등급은_표가_거부한다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    with pytest.raises(Exception, match="CHECK|constraint"):
        await repository.update_managed(_member("#A", "도토리", grade="RESERVE"))  # type: ignore[arg-type]
