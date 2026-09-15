"""클랜원 자료형."""

from __future__ import annotations

import dataclasses

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberProfile, MemberStatus

NOW = "2026-09-10T05:30:00Z"


def _member(**overrides) -> ClanMember:
    """테스트용 클랜원 하나. 바꾸고 싶은 것만 넘긴다."""
    base = {
        "id": "0198f0c1-0000-7000-8000-000000000001",
        "external_id": "#2ABC123",
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


def test_클랜원은_고칠_수_없다():
    """얼려 둔다. 지나가는 코드가 값을 바꿔 놓으면 어디서 바뀌었는지 못 찾는다."""
    member = _member()

    with pytest.raises(dataclasses.FrozenInstanceError):
        member.warnings = 3  # type: ignore[misc]


def test_CoC_가_주인인_값은_담지_않는다():
    """이름·직책·홀·트로피는 필요할 때 CoC 에 묻는다. 사본을 들면 어긋난다."""
    fields = {f.name for f in dataclasses.fields(ClanMember)}

    assert fields == {
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


def test_표기는_비어_있을_수_있다():
    """사람이 고치기 전까지는 None 이다. 동기화가 채우지 않는다."""
    assert _member().display_name is None
    assert _member(display_name="도토리형").display_name == "도토리형"


def test_모르는_직책은_UNKNOWN():
    """CoC 가 새 직책을 만들어도 한 명 때문에 동기화가 멈추면 안 된다."""
    assert ClanRole.from_coc("coLeader") is ClanRole.COLEADER
    assert ClanRole.from_coc("admin") is ClanRole.ADMIN
    assert ClanRole.from_coc("보물창고지기") is ClanRole.UNKNOWN
    assert ClanRole.from_coc("") is ClanRole.UNKNOWN


def test_현황은_받은_시각을_함께_담는다():
    """사본이 아니라 언제 받은 값인지 밝혀야 한다."""
    profile = MemberProfile(
        external_id="#2ABC123",
        name="도토리",
        role=ClanRole.ADMIN,
        townhall=16,
        trophies=4200,
        donations=100,
        donations_received=50,
        fetched_at=NOW,
    )

    assert profile.fetched_at == NOW
