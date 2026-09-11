"""schema.sql 이 마이그레이션과 어긋나지 않는지 확인한다.

두 벌로 관리하는 방식의 유일한 위험이 둘이 갈라지는 것이다. schema.sql 은
손으로 쓰지 않고 ./scripts/dump-schema.sh 가 만들지만, 마이그레이션을 더하고
그 명령을 잊으면 조용히 어긋난다. 그것을 여기서 잡는다.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DATABASE = Path(__file__).resolve().parents[1] / "database"
MIGRATIONS = DATABASE / "migrations"
SCHEMA = DATABASE / "schema.sql"


def _normalize(sql: str) -> set[str]:
    """주석과 공백 차이를 지우고 문장 집합으로 만든다."""
    without_comments = re.sub(r"--[^\n]*", "", sql)
    statements = (re.sub(r"\s+", " ", s).strip() for s in without_comments.split(";"))
    return {s for s in statements if s}


def test_schema_가_마이그레이션과_같다():
    conn = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    from_migrations = {
        row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
    }

    conn2 = sqlite3.connect(":memory:")
    conn2.executescript(SCHEMA.read_text(encoding="utf-8"))
    from_schema = {
        row[0] for row in conn2.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
    }

    assert _normalize(";".join(from_migrations)) == _normalize(";".join(from_schema)), (
        "schema.sql 이 마이그레이션과 다릅니다. ./scripts/dump-schema.sh 를 돌리세요."
    )


def test_clan_members_표가_있다(fake_db):
    conn = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    assert "clan_members" in names
    assert "members" not in names
