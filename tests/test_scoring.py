from datetime import UTC, datetime

import pytest
from helpers import member, war

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember
from coc_pointer.scoring import (
    ROSTER_SIZE,
    RULES,
    MemberMonth,
    aggregate_month,
    group_wars_by_month,
    month_key,
    passes_cutline,
    rank_month,
    roster,
)


def mm(attacks: int, opportunities: int, stars: int, tag="#P", name="x") -> MemberMonth:
    return MemberMonth(
        tag=tag,
        name=name,
        townhall=16,
        attacks=attacks,
        opportunities=opportunities,
        stars=stars,
    )


# Rows taken from the clan's real August 2026 sheet; the formula must reproduce them.
@pytest.mark.parametrize(
    ("attacks", "opportunities", "stars", "score"),
    [
        (27, 27, 81, 100.0),  # 도토리
        (27, 27, 80, 99.5),  # Taimanin
        (25, 27, 75, 92.6),  # 정사과
        (23, 27, 62, 81.9),  # 군방
        (70, 72, 170, 90.28),  # 빼빼 (1차 입력표, 소수 둘째 자리)
    ],
)
def test_score_matches_excel(attacks, opportunities, stars, score):
    m = mm(attacks, opportunities, stars)
    assert round(m.score, 2) == pytest.approx(score, abs=0.005) or round(m.score, 1) == score


def test_missed_and_star_avg():
    m = mm(25, 27, 75)
    assert m.missed == 2
    assert round(m.star_avg, 2) == 2.78


def test_zero_opportunities_gives_zero_score():
    m = mm(0, 0, 0)
    assert m.score == 0.0
    assert m.star_avg == 0.0


def test_cutline_requires_ten_attacks_and_seventy_points():
    assert passes_cutline(mm(10, 10, 20))  # (50+20)/80 = 87.5
    assert not passes_cutline(mm(9, 9, 27))  # attacks < 10
    assert not passes_cutline(mm(10, 16, 10))  # (50+10)/128 = 46.9


def test_month_key_uses_korea_time():
    # 2026-08-31 15:30 UTC == 2026-09-01 00:30 KST
    assert month_key(datetime(2026, 8, 31, 15, 30, tzinfo=UTC)) == "2026-09"
    assert month_key(datetime(2026, 8, 31, 14, 30, tzinfo=UTC)) == "2026-08"


def test_rules_text_mentions_formula_and_cutline():
    joined = " ".join(RULES)
    assert "5" in joined
    assert "8" in joined
    assert "10회" in joined
    assert "70점" in joined
    assert "30" in joined


def by_tag(rows):
    return {r.tag: r for r in rows}


def test_aggregate_scores_regular_wars_only():
    regular = war(
        [member("#P1", "도토리", (3, 2)), member("#P2", "제니", (1,))], war_type="regular"
    )
    cwl = war(
        [member("#P1", "도토리", (3,)), member("#P3", "리그만", (3,))],
        war_type="cwl",
        end="2026-09-06T10:00:00Z",
    )
    rows = by_tag(aggregate_month([regular, cwl]))
    assert rows["#P1"].attacks == 2 and rows["#P1"].opportunities == 2 and rows["#P1"].stars == 5
    assert rows["#P2"].attacks == 1 and rows["#P2"].opportunities == 2 and rows["#P2"].missed == 1
    assert "#P3" not in rows, "a member seen only in CWL gets no row from wars alone"


def test_cwl_only_member_gets_zero_row_when_on_clan_roster():
    cwl = war([member("#P3", "리그만", (3,))], war_type="cwl")
    rows = by_tag(aggregate_month([cwl], [ClanMember("#P3", "리그만", "member", 15, 1, 0, 0)]))
    assert (rows["#P3"].attacks, rows["#P3"].opportunities, rows["#P3"].score) == (0, 0, 0.0)


def test_aggregate_uses_latest_name_and_townhall():
    old = war([member("#P1", "옛이름", (3, 3), townhall=16)], end="2026-09-01T10:00:00Z")
    new = war([member("#P1", "새이름", (3, 3), townhall=17)], end="2026-09-03T10:00:00Z")
    row = aggregate_month([new, old])[0]
    assert row.name == "새이름" and row.townhall == 17


def test_group_wars_by_month_uses_korea_time_and_sorts():
    aug = war([member("#P1", "a", (3, 3))], end="2026-08-31T14:00:00Z")  # 23:00 KST Aug 31
    sep = war([member("#P1", "a", (3, 3))], end="2026-08-31T15:30:00Z")  # 00:30 KST Sep 1
    later = war([member("#P1", "a", (3, 3))], end="2026-09-05T15:30:00Z")
    grouped = group_wars_by_month([later, sep, aug])
    assert list(grouped) == ["2026-08", "2026-09"]
    assert grouped["2026-09"] == [sep, later]


def strong(tag, name="m", score_stars=3):
    # 12 attacks, all made, star avg configurable -> score >= 70
    return mm(12, 12, 12 * score_stars, tag=tag, name=name)


def test_rank_orders_by_score_then_stars_then_attacks_then_name():
    a = mm(10, 10, 20, tag="#A", name="가")  # 87.5
    b = mm(11, 11, 22, tag="#B", name="나")  # 87.5, more stars & attacks
    c = mm(10, 10, 20, tag="#C", name="다")  # 87.5, same as a, later name
    ranked = rank_month([c, a, b], ClanConfig(clan_tag="#X"))
    assert [r.member.tag for r in ranked] == ["#B", "#A", "#C"]
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_selection_elite_first_then_by_score_up_to_roster_size():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1", "#E2"}))
    members = [strong(f"#M{i:02d}", name=f"m{i:02d}", score_stars=2) for i in range(35)]
    members += [strong("#E1", "e1", score_stars=1), strong("#E2", "e2", score_stars=1)]
    ranked = rank_month(members, cfg)
    sel = {r.member.tag: r.selection for r in ranked}
    assert sel["#E1"] == "정예" and sel["#E2"] == "정예"
    assert sum(1 for v in sel.values() if v is not None) == ROSTER_SIZE
    assert sum(1 for v in sel.values() if v == "선발") == ROSTER_SIZE - 2
    # the 28 selected regulars are the top-scoring ones; the 7 weakest get None
    unselected = sorted(t for t, v in sel.items() if v is None)
    assert len(unselected) == 7


def test_elite_below_cutline_is_not_selected_as_elite():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1"}))
    weak_elite = mm(9, 12, 27, tag="#E1", name="e1")  # 9 attacks < 10
    ranked = rank_month([weak_elite, strong("#M1")], cfg)
    by = {r.member.tag: r for r in ranked}
    assert by["#E1"].is_elite and not by["#E1"].meets_cutline and by["#E1"].selection is None
    assert by["#M1"].selection == "선발"


def test_alt_is_never_elite_but_can_be_selected():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#A1"}), alts=frozenset({"#A1"}))
    ranked = rank_month([strong("#A1")], cfg)
    r = ranked[0]
    assert r.is_alt and not r.is_elite and r.selection == "선발"


def test_excluded_member_is_listed_but_never_selected():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#X1"}), excluded=frozenset({"#X1"}))
    ranked = rank_month([strong("#X1"), strong("#M1")], cfg)
    by = {r.member.tag: r for r in ranked}
    assert by["#X1"].is_excluded and by["#X1"].selection is None
    assert by["#M1"].selection == "선발"


def test_warnings_are_carried_but_do_not_affect_score():
    cfg = ClanConfig(clan_tag="#X", warnings={"#M1": 2})
    r = rank_month([strong("#M1")], cfg)[0]
    assert r.warnings == 2 and r.selection == "선발"


def test_roster_puts_elite_first_and_renumbers():
    cfg = ClanConfig(clan_tag="#X", elite=frozenset({"#E1"}))
    ranked = rank_month([strong("#M1", score_stars=3), strong("#E1", score_stars=1)], cfg)
    final = roster(ranked)
    assert [r.member.tag for r in final] == ["#E1", "#M1"]
    assert [r.rank for r in final] == [1, 2]
    assert [r.selection for r in final] == ["정예", "선발"]


def test_aggregate_adds_zero_rows_for_roster_members_without_wars():
    w = war([member("#P1", "도토리", (3, 2))])
    roster_members = [
        ClanMember("#P1", "도토리(현재)", "member", 18, 5000, 0, 0),
        ClanMember("#P9", "신입", "member", 12, 1000, 0, 0),
    ]
    rows = by_tag(aggregate_month([w], roster_members))
    assert rows["#P1"].name == "도토리", "war-time name wins over the snapshot name"
    assert rows["#P1"].attacks == 2
    new = rows["#P9"]
    assert (new.name, new.townhall) == ("신입", 12)
    assert (new.attacks, new.opportunities, new.stars) == (0, 0, 0)
    assert new.score == 0.0 and new.missed == 0
