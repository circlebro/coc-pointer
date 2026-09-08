from datetime import UTC, datetime

from helpers import member, war

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, ClanSnapshot
from coc_pointer.render import build_month_view, build_site, war_cell
from coc_pointer.storage import save_clan_snapshot, save_war

CFG = ClanConfig(clan_tag="#2C8L822LQ", elite=frozenset({"#P1"}), warnings={"#P2": 1})


def test_war_cell_formats():
    w = war([member("#P1", "a", (3, 2)), member("#P2", "b", (1,)), member("#P3", "c")])
    assert war_cell(w, "#P1") == "3/2"
    assert war_cell(w, "#P2") == "1/x"
    assert war_cell(w, "#P3") == "x/x"
    assert war_cell(w, "#NOPE") == ""
    cwl = war([member("#P1", "a", (3,))], war_type="cwl")
    assert war_cell(cwl, "#P1") == "3"


def test_build_month_view_label_and_grid():
    w = war([member("#P1", "도토리", (3, 3)), member("#P2", "제니", (2, 1))])
    view = build_month_view("2026-09", [w], CFG)
    assert view.label == "2026년 9월"
    assert [r.member.name for r in view.ranked] == ["도토리", "제니"]
    assert view.grid[0][1] == ["3/3"]


def seed(tmp_path):
    save_war(
        war([member("#P1", "도토리", (3, 3), townhall=18), member("#P2", "제니", (2, 1))]),
        tmp_path,
    )
    save_war(
        war(
            [member("#P1", "도토리", (3,))],
            war_type="cwl",
            end="2026-09-06T10:00:00Z",
            opponent_tag="#OPP2",
            opponent_name="리그상대",
        ),
        tmp_path,
    )
    save_clan_snapshot(
        ClanSnapshot(
            fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
            name="미니언즈",
            tag="#2C8L822LQ",
            members=(
                ClanMember("#P1", "도토리", "coLeader", 18, 5200, 1200, 900),
                ClanMember("#P9", "신입", "member", 12, 1000, 0, 0),
            ),
        ),
        tmp_path,
    )


def test_build_site_writes_pages(tmp_path):
    seed(tmp_path)
    out = tmp_path / "site"
    files = build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    names = {str(p.relative_to(out)) for p in files}
    assert names == {"index.html", "style.css", "members/index.html", "2026-09/index.html"}

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "미니언즈" in index and "2026년 9월" in index
    assert "기본 5점" in index, "rules text must be shown"
    assert "2026-09-07 12:00" in index, "generated time shown in KST"

    # 3 attacks < MIN_ATTACKS, so nobody is selected; the full score table still lists everyone.
    month = (out / "2026-09" / "index.html").read_text(encoding="utf-8")
    assert "커트라인을 넘은 멤버가 없습니다" in month
    assert "도토리" in month and "제니" in month and "3/3" in month and "리그상대" in month
    assert "●" in month, "elite mark in score table"

    members = (out / "members" / "index.html").read_text(encoding="utf-8")
    assert "#P9" in members and "신입" in members and "공동 대표" in members


def test_build_site_with_no_data(tmp_path):
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "기록 없음" in index
