from datetime import UTC, datetime
from pathlib import Path

import pytest

from coc_pointer.api import CocApiError
from coc_pointer.collect import (
    WarLogPrivateError,
    clan_snapshot_from_payload,
    collect,
    parse_api_time,
    war_from_cwl,
    war_from_regular,
)
from coc_pointer.config import ClanConfig
from coc_pointer.storage import load_clan_snapshot, load_wars

OUR = "#2C8L822LQ"


def side(tag, name, members):
    return {"tag": tag, "name": name, "members": members}


def m(tag, name, th, attacks=None):
    d = {"tag": tag, "name": name, "townhallLevel": th, "mapPosition": 1}
    if attacks is not None:
        d["attacks"] = attacks
    return d


def atk(order, stars):
    return {
        "attackerTag": "#X",
        "defenderTag": "#Y",
        "stars": stars,
        "destructionPercentage": 50,
        "order": order,
        "duration": 100,
    }


REGULAR_ENDED = {
    "state": "warEnded",
    "teamSize": 2,
    "attacksPerMember": 2,
    "preparationStartTime": "20260903T140000.000Z",
    "startTime": "20260904T140000.000Z",
    "endTime": "20260905T140000.000Z",
    "clan": side(
        OUR, "미니언즈", [m("#P1", "도토리", 18, [atk(2, 3), atk(1, 2)]), m("#P2", "제니", 16)]
    ),
    "opponent": side("#OPP1", "상대클랜", []),
}

CWL_ENDED_WE_ARE_OPPONENT = {
    "state": "warEnded",
    "teamSize": 1,
    "preparationStartTime": "20260902T084403.000Z",
    "startTime": "20260902T084403.000Z",
    "endTime": "20260903T093932.000Z",
    "warStartTime": "20260902T084403.000Z",
    "clan": side("#OTHER", "다른클랜", [m("#Q1", "남", 15, [atk(1, 1)])]),
    "opponent": side(OUR, "미니언즈", [m("#P1", "도토리", 18, [atk(1, 3)])]),
}

CLAN_PAYLOAD = {
    "tag": OUR,
    "name": "미니언즈",
    "memberList": [
        {
            "tag": "#P1",
            "name": "도토리",
            "role": "coLeader",
            "townHallLevel": 18,
            "trophies": 5200,
            "donations": 1200,
            "donationsReceived": 900,
        },
    ],
}


def test_parse_api_time():
    assert parse_api_time("20260903T093932.000Z") == datetime(2026, 9, 3, 9, 39, 32, tzinfo=UTC)


def test_war_from_regular_sorts_attacks_and_keeps_non_attackers():
    w = war_from_regular(REGULAR_ENDED)
    assert w.war_type == "regular" and w.attacks_per_member == 2 and w.team_size == 2
    assert w.opponent_tag == "#OPP1" and w.opponent_name == "상대클랜"
    assert w.end_time == datetime(2026, 9, 5, 14, 0, tzinfo=UTC)
    p1, p2 = w.members
    assert [a.stars for a in p1.attacks] == [2, 3]
    assert p2.attacks == ()


def test_war_from_cwl_finds_our_side_and_uses_one_attack():
    w = war_from_cwl(CWL_ENDED_WE_ARE_OPPONENT, OUR)
    assert w is not None
    assert w.war_type == "cwl" and w.attacks_per_member == 1
    assert w.opponent_tag == "#OTHER"
    assert w.members[0].tag == "#P1"


def test_war_from_cwl_returns_none_when_not_ours():
    assert war_from_cwl(CWL_ENDED_WE_ARE_OPPONENT, "#NOBODY") is None


def test_clan_snapshot_from_payload_maps_fields():
    snap = clan_snapshot_from_payload(CLAN_PAYLOAD, datetime(2026, 9, 7, tzinfo=UTC))
    assert snap.tag == OUR and snap.name == "미니언즈"
    mem = snap.members[0]
    assert (mem.role, mem.townhall, mem.donations_received) == ("coLeader", 18, 900)


class FakeApi:
    def __init__(self, clan=CLAN_PAYLOAD, current_war=None, league_group=None, cwl_wars=None):
        self._clan = clan
        self._current_war = current_war or {"state": "notInWar"}
        self._league_group = league_group
        self._cwl_wars = cwl_wars or {}
        self.calls: list[str] = []

    def clan(self, tag):
        self.calls.append("clan")
        return self._clan

    def current_war(self, tag):
        self.calls.append("current_war")
        if isinstance(self._current_war, Exception):
            raise self._current_war
        return self._current_war

    def league_group(self, tag):
        self.calls.append("league_group")
        return self._league_group

    def cwl_war(self, war_tag):
        self.calls.append(f"cwl:{war_tag}")
        return self._cwl_wars[war_tag]


CFG = ClanConfig(clan_tag=OUR)


def test_collect_saves_snapshot_and_ended_regular_war(tmp_path: Path):
    api = FakeApi(current_war=REGULAR_ENDED)
    new = collect(api, CFG, tmp_path, now=datetime(2026, 9, 7, tzinfo=UTC), log=lambda s: None)
    assert len(new) == 1 and new[0].name.endswith("_regular_OPP1.json")
    assert load_clan_snapshot(tmp_path).name == "미니언즈"
    assert load_wars(tmp_path)[0].war_type == "regular"
    # second run: nothing new
    assert collect(api, CFG, tmp_path, log=lambda s: None) == []


def test_collect_skips_war_in_progress(tmp_path):
    api = FakeApi(current_war={**REGULAR_ENDED, "state": "inWar"})
    assert collect(api, CFG, tmp_path, log=lambda s: None) == []
    assert load_wars(tmp_path) == []


def test_collect_saves_only_our_ended_cwl_wars(tmp_path):
    group = {
        "state": "inWar",
        "season": "2026-09",
        "rounds": [{"warTags": ["#W1", "#W2"]}, {"warTags": ["#0", "#0"]}],
    }
    in_progress = {**CWL_ENDED_WE_ARE_OPPONENT, "state": "inWar"}
    api = FakeApi(
        league_group=group, cwl_wars={"#W1": CWL_ENDED_WE_ARE_OPPONENT, "#W2": in_progress}
    )
    new = collect(api, CFG, tmp_path, log=lambda s: None)
    assert len(new) == 1 and "_cwl_OTHER.json" in new[0].name
    assert "cwl:#0" not in api.calls


def test_collect_raises_clear_error_when_war_log_private(tmp_path):
    api = FakeApi(current_war=CocApiError(403, "/clans/x/currentwar", "accessDenied", "private"))
    with pytest.raises(WarLogPrivateError, match="전적"):
        collect(api, CFG, tmp_path, log=lambda s: None)
