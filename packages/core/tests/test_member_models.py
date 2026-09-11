"""클랜원 자료형."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberStatus


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


def test_클랜원은_고칠_수_없다():
    member = ClanMember(
        id="0198f0c1-0000-7000-8000-000000000001",
        tag="#2ABC123",
        name="도토리",
        role=ClanRole.ADMIN,
        status=MemberStatus.ACTIVE,
        townhall=16,
        trophies=4200,
        donations=1200,
        donations_received=800,
        description=None,
        created_at="2026-09-10T05:30:00Z",
        updated_at="2026-09-10T05:30:00Z",
    )

    # 예외를 좁혀 잡는다. Exception 으로 두면 오타 같은 엉뚱한 오류에도
    # 테스트가 통과한다(ruff B017 이 그것을 막는다).
    with pytest.raises(FrozenInstanceError):
        member.name = "다른 이름"  # type: ignore[misc]
