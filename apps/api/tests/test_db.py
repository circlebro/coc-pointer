"""db.py 의 질의가 실제 SQL 로 도는지 확인한다."""

from __future__ import annotations


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
