"""이미 올라가 있는 데이터베이스 위에 마이그레이션을 걸어 본다.

빈 데이터베이스에만 걸어 보면 드러나지 않는 것이 있다. 실제로 0001 이 members
표를 지우면서, 그것을 외래키로 가리키던 users 표를 못 쓰게 만든 적이 있다.
users 는 CREATE TABLE IF NOT EXISTS 라 이미 있는 표를 고치지 않기 때문이다.
그 상태에서는 member_tag 가 NULL 이어도 users 에 아무 행도 넣을 수 없다.
SQLite 가 외래키의 대상 표가 없으면 삽입 자체를 거부하는 탓이다.

다른 테스트들은 모두 빈 데이터베이스에서 출발하므로 이 어긋남을 잡지 못한다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
MIGRATIONS = HERE.parent / "database" / "migrations"
DEPLOYED = HERE / "fixtures" / "deployed-2026-09-10.sql"

# 표마다 한 행씩. 실제로 넣어 봐야 외래키가 성한지 알 수 있다.
SAMPLE_ROWS = {
    "users": (
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("u1", "admin", "해시", "관리자", "admin", None, "2026-09-11T00:00:00Z", None),
    ),
    "clan_members": (
        "INSERT INTO clan_members VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "id1",
            "#A",
            "도토리",
            "MEMBER",
            16,
            4200,
            100,
            50,
            "ACTIVE",
            "2026-09-11T00:00:00Z",
            "2026-09-11T00:00:00Z",
            None,
        ),
    ),
    "settings": ("INSERT INTO settings VALUES (?, ?)", ("k", "v")),
}


def _fresh() -> sqlite3.Connection:
    """마이그레이션만 건 빈 데이터베이스."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    return conn


def _deployed() -> sqlite3.Connection:
    """지금 배포되어 있는 것 위에 마이그레이션을 건 데이터베이스."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(DEPLOYED.read_text(encoding="utf-8"))
    _apply_migrations(conn)
    return conn


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("table", sorted(SAMPLE_ROWS))
@pytest.mark.parametrize(
    "start", ["fresh", "deployed"], ids=["빈_데이터베이스", "배포된_데이터베이스"]
)
def test_마이그레이션_뒤에_표를_쓸_수_있다(start: str, table: str) -> None:
    conn = _fresh() if start == "fresh" else _deployed()
    sql, values = SAMPLE_ROWS[table]

    try:
        conn.execute(sql, values)
    except sqlite3.Error as exc:
        pytest.fail(f"{start} 에서 {table} 에 넣지 못했습니다: {type(exc).__name__}: {exc}")

    assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1


def test_어느_쪽에서_출발해도_같은_스키마가_된다() -> None:
    """마이그레이션은 출발점과 무관하게 같은 결과를 내야 한다.

    갈라지면 배포된 것과 테스트가 보는 것이 영영 달라지는데, 모든 테스트가
    빈 데이터베이스에서 출발하므로 그 차이를 아무도 눈치채지 못한다.
    """

    def schema_of(conn: sqlite3.Connection) -> dict[str, str]:
        return {
            name: sql
            for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        }

    assert schema_of(_fresh()) == schema_of(_deployed())
