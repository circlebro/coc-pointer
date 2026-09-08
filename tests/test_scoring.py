from datetime import UTC, datetime

import pytest

from coc_pointer.scoring import RULES, MemberMonth, month_key, passes_cutline


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
