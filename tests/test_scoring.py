from datetime import UTC, datetime

import pytest
from helpers import member, war

from coc_pointer.scoring import (
    RULES,
    MemberMonth,
    aggregate_month,
    group_wars_by_month,
    month_key,
    passes_cutline,
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


def test_aggregate_counts_opportunities_per_war_type():
    w1 = war([member("#P1", "도토리", (3, 2)), member("#P2", "제니", (1,))], war_type="regular")
    w2 = war([member("#P1", "도토리", (3,))], war_type="cwl", end="2026-09-06T10:00:00Z")
    rows = by_tag(aggregate_month([w1, w2]))
    assert rows["#P1"].attacks == 3 and rows["#P1"].opportunities == 3 and rows["#P1"].stars == 8
    assert rows["#P2"].attacks == 1 and rows["#P2"].opportunities == 2 and rows["#P2"].missed == 1
    assert "#P3" not in rows


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
