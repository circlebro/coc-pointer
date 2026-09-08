from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.models import ClanMember, ClanSnapshot, War


def test_war_file_name_uses_utc_end_time_type_and_opponent_tag():
    w = war([member("#P1", "도토리", (3, 2))], end="2026-09-05T14:30:00Z", opponent_tag="#2PP0JJ8L")
    assert w.file_name == "2026-09-05T14-30-00Z_regular_2PP0JJ8L.json"


def test_war_round_trips_through_dict():
    w = war([member("#P1", "도토리", (3, 2), townhall=18), member("#P2", "제니")])
    d = w.to_dict()
    assert d["members"][0]["attacks"] == [{"order": 1, "stars": 3}, {"order": 2, "stars": 2}]
    assert d["members"][1]["attacks"] == []
    assert d["end_time"] == "2026-09-05T14:30:00Z"
    assert War.from_dict(d) == w


def test_clan_snapshot_round_trips_through_dict():
    snap = ClanSnapshot(
        fetched_at=datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
        name="미니언즈",
        tag="#2C8L822LQ",
        members=(ClanMember("#P1", "도토리", "coLeader", 18, 5200, 1200, 900),),
    )
    d = snap.to_dict()
    assert d["fetched_at"] == "2026-09-07T09:00:00Z"
    assert d["members"][0]["role"] == "coLeader"
    assert ClanSnapshot.from_dict(d) == snap
