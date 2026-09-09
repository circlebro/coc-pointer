from datetime import UTC, datetime
from pathlib import Path

from helpers import member, war

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, ClanSnapshot
from coc_pointer.render import (
    build_month_view,
    build_site,
    next_month_label,
    war_cell,
    war_status,
)
from coc_pointer.storage import load_wars, save_clan_snapshot, save_war

CFG = ClanConfig(clan_tag="#2C8L822LQ", elite=frozenset({"#P1"}), warnings={"#P2": 1})


def test_war_cell_formats():
    w = war([member("#P1", "a", (3, 2)), member("#P2", "b", (1,)), member("#P3", "c")])
    assert war_cell(w, "#P1") == "3/2"
    assert war_cell(w, "#P2") == "1/x"
    assert war_cell(w, "#P3") == "x/x"
    assert war_cell(w, "#NOPE") == ""
    cwl = war([member("#P1", "a", (3,))], war_type="cwl")
    assert war_cell(cwl, "#P1") == "3"


def test_build_month_view_grids_list_participants_only():
    regular = war([member("#P1", "도토리", (3, 3)), member("#P2", "제니", (2, 1))])
    cwl = war([member("#P1", "도토리", (3,))], war_type="cwl", end="2026-09-06T10:00:00Z")
    newcomer = ClanMember("#P9", "신입", "member", 12, 1000, 0, 0)
    view = build_month_view("2026-09", [regular, cwl], CFG, [newcomer])
    assert view.label == "2026년 9월"
    assert [r.member.name for r in view.ranked] == ["도토리", "제니", "신입"]  # everyone
    assert [r.member.name for r, _ in view.regular_grid] == ["도토리", "제니"]
    assert [cells for _, cells in view.regular_grid] == [["3/3"], ["2/1"]]
    assert [r.member.name for r, _ in view.cwl_grid] == ["도토리"]  # CWL participants only
    assert [cells for _, cells in view.cwl_grid] == [["3"]]
    assert [w.war_type for w in view.regular_wars] == ["regular"]
    assert [w.war_type for w in view.cwl_wars] == ["cwl"]
    assert [m.name for m in view.cwl_participants] == ["도토리"], "actual CWL roster this month"
    assert view.next_label == "2026년 10월"


def test_next_month_label_wraps_year():
    assert next_month_label("2026-12") == "2027년 1월"
    assert next_month_label("2026-01") == "2026년 2월"


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
    assert "반영된 일반 클랜전 1개" in index
    assert "2026년 9월 리그전" in index and "참여자 명단 (1명)" in index
    assert "2026년 10월 리그전 선발 명단" in index, "selection is for next month"
    assert "2026-09-07 12:00" in index, "generated time shown in KST"
    assert index.index('class="updated"') < index.index("<main>"), "last-updated sits in the header"

    # 3 attacks < MIN_ATTACKS, so nobody is selected; the full score table still lists everyone.
    month = (out / "2026-09" / "index.html").read_text(encoding="utf-8")
    assert "커트라인을 넘은 멤버가 없습니다" in month
    assert "도토리" in month and "제니" in month and "3/3" in month and "리그상대" in month
    assert "●" in month, "elite mark in score table"
    assert "신입" in month, "clan members without wars still appear in the score table"
    assert "일반 클랜전 기록" in month and "리그 기록" in month, "two separate grids"
    assert "Day 1" in month, "CWL columns are numbered by round"
    assert "Day 2" not in month, "only one CWL war seeded"

    members = (out / "members" / "index.html").read_text(encoding="utf-8")
    assert "#P9" in members and "신입" in members and "공동 대표" in members


def test_build_site_with_no_data(tmp_path):
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "기록 없음" in index


def test_build_site_with_member_passing_cutline(tmp_path):
    """A member with >=10 attacks and score >=70 must show up in the roster tables."""
    cfg = ClanConfig(clan_tag="#2C8L822LQ", elite=frozenset({"#P1"}))
    opponents = ["#OPP1", "#OPP2", "#OPP3", "#OPP4", "#OPP5"]
    for day, opponent_tag in enumerate(opponents, start=1):
        save_war(
            war(
                [member("#P1", "도토리", (3, 3))],
                end=f"2026-09-0{day}T14:30:00Z",
                opponent_tag=opponent_tag,
            ),
            tmp_path,
        )

    out = tmp_path / "site"
    build_site(tmp_path, cfg, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "도토리" in index
    assert "100.0" in index
    assert "정예 멤버" in index

    month = (out / "2026-09" / "index.html").read_text(encoding="utf-8")
    assert "도토리" in month
    assert "100.0" in month
    assert "선발" in month


def test_tabs_and_month_select(tmp_path):
    seed(tmp_path)
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    index = (out / "index.html").read_text(encoding="utf-8")
    assert '<option value="2026-09/" selected>2026/09</option>' in index, "YYYY/MM, current month"
    tabs = ("길드원", "점수판", "선발 명단", "일반 클랜전", "리그전")
    labels = [index.index(f">{t}<") for t in tabs]
    assert labels == sorted(labels), "tab order: 길드원 first"
    assert 'id="tab-members" checked' in index, "길드원 tab opens by default"
    assert ">규칙<" not in index, "rules are no longer a tab"
    scores = index[index.index('id="panel-scores"') : index.index('id="panel-roster"')]
    assert "기본 5점" in scores and "<select" in scores, "rules and month select live in 점수판"
    members_panel = index[index.index('id="panel-members"') : index.index('id="panel-scores"')]
    assert "<th>설정</th>" not in members_panel and "clan.yaml" not in members_panel
    import re

    m = re.search(r'href="style\.css\?v=([0-9a-f]{8})"', index)
    assert m, "stylesheet link carries a content-hash version to defeat stale caches"


def test_current_month_page_exists_without_data(tmp_path):
    save_war(war([member("#P1", "도토리", (3, 3))], end="2026-08-20T10:00:00Z"), tmp_path)
    out = tmp_path / "site"
    written = build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, tzinfo=UTC))
    files = {str(p.relative_to(out)) for p in written}
    assert {"2026-08/index.html", "2026-09/index.html"} <= files
    index = (out / "index.html").read_text(encoding="utf-8")
    assert '<option value="2026-09/" selected>2026/09</option>' in index
    assert '<option value="2026-08/">2026/08</option>' in index
    assert "기록 없음" in index, "current month without wars"
    august = (out / "2026-08" / "index.html").read_text(encoding="utf-8")
    assert '<option value="../2026-08/" selected>2026/08</option>' in august


def test_war_status_marks_running_wars():
    assert war_status(war([member("#P1", "a", (3, 3))])) == ""
    partly = war([member("#P1", "a", (3,)), member("#P2", "b", ())], in_progress=True)
    assert war_status(partly) == "진행중", "2 of 4 attacks used"
    done = war([member("#P1", "a", (3, 3)), member("#P2", "b", (2, 1))], in_progress=True)
    assert war_status(done) == "완료 대기", "all 4 attacks used but the war is still open"


def test_running_war_is_labelled_and_counted_in_the_score(tmp_path):
    running = war([member("#P1", "도토리", (3,)), member("#P2", "제니", ())], in_progress=True)
    save_war(running, tmp_path)
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "(진행중)" in index
    # the scoreboard warns that the score can still rise
    assert "진행 중인 클랜전 1개가 포함되어" in index
    scores = index[index.index('id="panel-scores"') : index.index('id="panel-roster"')]
    assert "50.0" in scores, "도토리: (5x1 + 3) / (8x2) x 100"


def test_cwl_table_shows_a_score_column(tmp_path):
    save_war(war([member("#P1", "도토리", (3,))], war_type="cwl"), tmp_path)
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    index = (out / "index.html").read_text(encoding="utf-8")
    cwl = index[index.index('id="panel-cwl"') :]
    assert "100.0" in cwl, "3 stars on the single CWL attack"
    assert "점수판과 선발 명단에는 반영되지 않습니다" in cwl


def test_cwl_tab_holds_four_sub_tabs_and_its_own_month_select(tmp_path):
    save_war(war([member("#P1", "도토리", (3,), townhall=18)], war_type="cwl"), tmp_path)
    out = tmp_path / "site"
    build_site(tmp_path, CFG, out, now=datetime(2026, 9, 7, 3, 0, tzinfo=UTC))
    index = (out / "index.html").read_text(encoding="utf-8")
    cwl = index[index.index('id="panel-cwl"') :]
    subs = ("참여자 명단", "리그 기록", "리그 점수판", "보상 대상자")
    positions = [cwl.index(f">{name}<") for name in subs]
    assert positions == sorted(positions), "sub-tab order"
    assert 'id="cwltab-roster" checked' in cwl, "참여자 명단 opens first"
    assert cwl.count("<select") == 1, "리그전 탭에도 월 선택이 있다"
    assert index.count("<select") == 2, "점수판 탭의 월 선택은 그대로"


def test_month_select_keeps_the_open_tab():
    base = (Path("src/coc_pointer/templates") / "base.html").read_text(encoding="utf-8")
    tables = (Path("src/coc_pointer/templates") / "_tables.html").read_text(encoding="utf-8")
    assert "this.value + location.hash" in tables, "달을 바꿔도 보던 탭이 주소에 남는다"
    assert 'pick("cwltab-" + parts[1])' in base, "하위 탭까지 복원한다"


def test_cwl_roster_is_ordered_by_townhall(tmp_path):
    save_war(
        war(
            [
                member("#P1", "낮은홀", (3,), townhall=13),
                member("#P2", "높은홀", (1,), townhall=17),
            ],
            war_type="cwl",
        ),
        tmp_path,
    )
    view = build_month_view("2026-09", load_wars(tmp_path), CFG)
    assert [m.name for m in view.cwl_roster] == ["높은홀", "낮은홀"]
    assert [m.name for m in view.cwl_participants] == ["낮은홀", "높은홀"], "점수판은 성적 순"


def test_reward_rows_are_coloured_in_the_cwl_score_table(tmp_path):
    # 3명이 만점, 3명이 동점 → 2자리를 3명이 놓고 다툰다.
    top = [member(f"#S{i}", f"강{i}", (3,), townhall=17) for i in range(3)]
    tied = [member(f"#T{i}", f"동{i}", (1,), townhall=16) for i in range(3)]
    save_war(war(top + tied, war_type="cwl"), tmp_path)
    out = tmp_path / "site"
    build_site(tmp_path, ClanConfig(clan_tag="#X", bonus_count=5), out)
    page = (out / "index.html").read_text(encoding="utf-8")
    scores = page[page.index('id="subpanel-scores"') : page.index('id="subpanel-reward"')]
    assert scores.count('class="reward-sure"') == 3, "확정 3명이 초록"
    assert scores.count('class="reward-draw"') == 3, "추첨 대상 3명이 주황"
    reward = page[page.index('id="subpanel-reward"') :]
    assert "남은 <strong>2자리</strong>를 <strong>3명</strong>이 놓고 추첨합니다" in reward
    assert reward.count('class="reward-sure"') == 3, "보상 탭에도 확정자가 나온다"
