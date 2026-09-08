import json
from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.models import ClanMember, ClanSnapshot
from coc_pointer.storage import (
    load_clan_snapshot,
    load_wars,
    save_clan_snapshot,
    save_war,
)


def test_save_war_writes_json_once(tmp_path):
    w = war([member("#P1", "도토리", (3, 2))])
    first = save_war(w, tmp_path)
    assert first == tmp_path / "wars" / w.file_name
    assert json.loads(first.read_text(encoding="utf-8"))["opponent"]["tag"] == "#OPP1"
    assert save_war(w, tmp_path) is None, "existing files are never rewritten"


def test_load_wars_sorted_by_end_time(tmp_path):
    late = war([member("#P1", "a", (3, 3))], end="2026-09-05T10:00:00Z")
    early = war([member("#P1", "a", (3, 3))], end="2026-09-01T10:00:00Z", opponent_tag="#OPP2")
    save_war(late, tmp_path)
    save_war(early, tmp_path)
    assert load_wars(tmp_path) == [early, late]


def test_load_wars_empty_when_missing(tmp_path):
    assert load_wars(tmp_path / "nope") == []


def test_clan_snapshot_round_trip_overwrites(tmp_path):
    snap = ClanSnapshot(
        fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
        name="미니언즈",
        tag="#2C8L822LQ",
        members=(ClanMember("#P1", "도토리", "leader", 18, 5000, 10, 20),),
    )
    assert load_clan_snapshot(tmp_path) is None
    save_clan_snapshot(snap, tmp_path)
    newer = ClanSnapshot(snap.fetched_at, snap.name, snap.tag, ())
    save_clan_snapshot(newer, tmp_path)
    assert load_clan_snapshot(tmp_path) == newer
