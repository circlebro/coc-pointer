"""D1 질의. SQL 문자열은 이 파일에만 둔다.

D1 은 SQLite 라서 표준 SQL 이 그대로 돈다. 다만 부르는 모양이 다르다.

    await db.prepare(SQL).bind(값).all()     # 여러 행. 결과는 .results
    await db.prepare(SQL).bind(값).first()   # 한 행. 없으면 None
    await db.prepare(SQL).bind(값).run()     # 쓰기

파이썬 쪽 자료형으로 바꿔 돌려주므로, 부르는 쪽은 D1 의 행 객체를 몰라도 된다.
"""

from __future__ import annotations

import json
from typing import Any

_TABLES = (
    "SELECT name FROM sqlite_master WHERE type = 'table' "
    "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_%' ESCAPE '\\' "
    "ORDER BY name"
)

_MONTHLY_SCORES = (
    "SELECT tag, name, attacks, stars, score FROM monthly_scores "
    "WHERE month = ? "
    "ORDER BY score DESC, stars DESC, attacks DESC, name"
)

_GET_DRAW = "SELECT month, winners, candidates, slots, drawn_at FROM draws WHERE month = ?"

_SAVE_DRAW = (
    "INSERT INTO draws (month, winners, candidates, slots, drawn_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT(month) DO UPDATE SET "
    "winners = excluded.winners, candidates = excluded.candidates, "
    "slots = excluded.slots, drawn_at = excluded.drawn_at"
)


async def list_tables(db: Any) -> list[str]:
    """만들어진 표 이름. 배포가 제대로 되었는지 확인할 때 쓴다."""
    result = await db.prepare(_TABLES).all()
    return [row.name for row in result.results]


async def get_monthly_scores(db: Any, month: str) -> list[dict]:
    """그달 점수표. 점수 높은 순, 같으면 별 많은 순, 그다음 공격 많은 순."""
    result = await db.prepare(_MONTHLY_SCORES).bind(month).all()
    return [
        {
            "tag": row.tag,
            "name": row.name,
            "attacks": row.attacks,
            "stars": row.stars,
            "score": row.score,
        }
        for row in result.results
    ]


async def get_draw(db: Any, month: str) -> dict | None:
    """그달 추첨 결과. 아직 뽑지 않았으면 None."""
    row = await db.prepare(_GET_DRAW).bind(month).first()
    if row is None:
        return None
    return {
        "month": row.month,
        "winners": json.loads(row.winners),
        "candidates": json.loads(row.candidates),
        "slots": row.slots,
        "drawn_at": row.drawn_at,
    }


async def save_draw(
    db: Any,
    *,
    month: str,
    winners: list[str],
    candidates: list[str],
    slots: int,
    drawn_at: str,
) -> None:
    """추첨 결과를 저장한다. 이미 있으면 덮어쓴다(다시 뽑기).

    당첨자와 후보는 JSON 문자열로 담는다. SQLite 에 JSON 타입이 없기 때문이고,
    추첨 결과는 늘 통째로 읽고 쓰므로 표를 나눌 이유가 없다.
    """
    await (
        db.prepare(_SAVE_DRAW)
        .bind(
            month,
            json.dumps(winners, ensure_ascii=False),
            json.dumps(candidates, ensure_ascii=False),
            slots,
            drawn_at,
        )
        .run()
    )
