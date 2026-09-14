"""클랜원 자료형."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("leader", ClanRole.LEADER),
        ("coLeader", ClanRole.COLEADER),
        ("admin", ClanRole.ADMIN),
        ("member", ClanRole.MEMBER),
    ],
)
def test_coc_표기를_우리_값으로_바꾼다(raw, expected):
    assert ClanRole.from_coc(raw) == expected


def test_모르는_직책은_UNKNOWN():
    assert ClanRole.from_coc("veteran") == ClanRole.UNKNOWN
    assert ClanRole.from_coc("") == ClanRole.UNKNOWN


def test_문자열처럼_비교된다():
    assert ClanRole.ADMIN == "ADMIN"
    assert MemberStatus.ACTIVE == "ACTIVE"


def _member(**overrides) -> ClanMember:
    """테스트용 클랜원 하나. 바꾸고 싶은 것만 넘긴다."""
    base = {
        "id": "0198f0c1-0000-7000-8000-000000000001",
        "tag": "#2ABC123",
        "name": "도토리",
        "role": ClanRole.ADMIN,
        "status": MemberStatus.ACTIVE,
        "grade": MemberGrade.COMPETING,
        "grade_reason": None,
        "warnings": 0,
        "townhall": 16,
        "trophies": 4200,
        "donations": 1200,
        "donations_received": 800,
        "description": None,
        "created_at": "2026-09-10T05:30:00Z",
        "updated_at": "2026-09-10T05:30:00Z",
    }
    base.update(overrides)
    return ClanMember(**base)


def test_클랜원은_고칠_수_없다():
    member = _member()

    # 예외를 좁혀 잡는다. Exception 으로 두면 오타 같은 엉뚱한 오류에도
    # 테스트가 통과한다(ruff B017 이 그것을 막는다).
    with pytest.raises(FrozenInstanceError):
        member.name = "다른 이름"  # type: ignore[misc]


def test_등급은_셋이다():
    """넷이 아니라 셋이다. 예비는 담지 않는다.

    확정과 제외는 사람이 매기고, 경쟁은 기본값이다. 예비는 그 달 점수 순위가
    가르는 값이라 저장하면 두 곳에서 관리하게 된다.
    """
    assert [g.value for g in MemberGrade] == ["FIXED", "COMPETING", "EXCLUDED"]


def test_아무것도_매기지_않으면_경쟁이다():
    member = _member()

    assert member.grade is MemberGrade.COMPETING


def test_사유와_경고를_담는다():
    member = _member(grade=MemberGrade.EXCLUDED, grade_reason="쉬는 계정", warnings=2)

    assert member.grade is MemberGrade.EXCLUDED
    assert member.grade_reason == "쉬는 계정"
    assert member.warnings == 2
