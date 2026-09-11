"""클랜 자료형."""

from __future__ import annotations

import dataclasses

import pytest

from coc_core.clan.models import Clan, ClanStatus

NOW = "2026-09-11T07:18:57Z"


def _clan(**overrides) -> Clan:
    base = {
        "id": "3f2a1b4c-5d6e-4f70-8a91-b2c3d4e5f607",
        "external_id": "#2C8L822LQ",
        "display_name": "미니언즈",
        "status": ClanStatus.ACTIVE,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return Clan(**base)


def test_상태는_두_가지다():
    assert [s.value for s in ClanStatus] == ["ACTIVE", "INACTIVE"]


def test_문자열처럼_쓸_수_있다():
    """StrEnum 이라 SQL 에 넣거나 응답에 담을 때 변환이 필요 없다."""
    assert str(ClanStatus.ACTIVE) == "ACTIVE"
    assert ClanStatus("INACTIVE") is ClanStatus.INACTIVE


def test_이름은_없을_수_있다():
    """첫 동기화 전에는 우리가 붙인 이름이 없다."""
    clan = _clan(display_name=None)

    assert clan.display_name is None


def test_한_번_만들면_바뀌지_않는다():
    """서비스가 새 자료형을 만들어 돌려주지, 가진 것을 고치지 않는다."""
    clan = _clan()

    with pytest.raises(dataclasses.FrozenInstanceError):
        clan.display_name = "다른 이름"  # type: ignore[misc]


def test_CoC_가_주는_값은_담지_않는다():
    """마크·레벨·점수·전적을 들고 있으면 두 곳에서 관리하게 된다.

    필드가 늘어나는 것을 여기서 막는다. 늘리려면 왜 우리가 가져야 하는지를
    먼저 답해야 한다.
    """
    fields = {f.name for f in dataclasses.fields(Clan)}

    assert fields == {
        "id",
        "external_id",
        "display_name",
        "status",
        "created_at",
        "updated_at",
    }
