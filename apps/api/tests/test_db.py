"""db.py 의 질의가 실제 SQL 로 도는지 확인한다."""

from __future__ import annotations

from db import get_draw, get_monthly_scores, list_tables, save_draw


async def test_스키마가_여덟_개_표를_만든다(fake_db):
    result = await fake_db.prepare(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).all()
    names = [r.name for r in result.results]
    assert names == [
        "attacks",
        "draws",
        "members",
        "monthly_scores",
        "settings",
        "users",
        "war_members",
        "wars",
    ]


async def test_표_목록을_돌려준다(fake_db):
    assert "monthly_scores" in await list_tables(fake_db)


async def test_월_점수는_높은_순으로_나온다(fake_db):
    await (
        fake_db.prepare(
            "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind("2026-09", "#AAA", "도토리", 10, 25, 87.5, "2026-09-10T00:00:00Z")
        .run()
    )
    await (
        fake_db.prepare(
            "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind("2026-09", "#BBB", "히로", 12, 30, 93.75, "2026-09-10T00:00:00Z")
        .run()
    )

    rows = await get_monthly_scores(fake_db, "2026-09")

    assert [r["name"] for r in rows] == ["히로", "도토리"]
    assert rows[0]["score"] == 93.75
    assert rows[0]["attacks"] == 12


async def test_다른_달_점수는_섞이지_않는다(fake_db):
    await (
        fake_db.prepare(
            "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind("2026-08", "#AAA", "도토리", 10, 25, 87.5, "2026-09-10T00:00:00Z")
        .run()
    )

    assert await get_monthly_scores(fake_db, "2026-09") == []


async def test_추첨하지_않은_달은_None(fake_db):
    assert await get_draw(fake_db, "2026-09") is None


async def test_추첨_결과를_저장하고_읽는다(fake_db):
    await save_draw(
        fake_db,
        month="2026-09",
        winners=["#AAA", "#BBB"],
        candidates=["#AAA", "#BBB", "#CCC"],
        slots=2,
        drawn_at="2026-09-10T12:00:00Z",
    )

    drawn = await get_draw(fake_db, "2026-09")

    assert drawn["winners"] == ["#AAA", "#BBB"]
    assert drawn["candidates"] == ["#AAA", "#BBB", "#CCC"]
    assert drawn["slots"] == 2
    assert drawn["drawn_at"] == "2026-09-10T12:00:00Z"


async def test_다시_뽑으면_덮어쓴다(fake_db):
    for winners in (["#AAA"], ["#BBB"]):
        await save_draw(
            fake_db,
            month="2026-09",
            winners=winners,
            candidates=["#AAA", "#BBB"],
            slots=1,
            drawn_at="2026-09-10T12:00:00Z",
        )

    drawn = await get_draw(fake_db, "2026-09")

    assert drawn["winners"] == ["#BBB"]
