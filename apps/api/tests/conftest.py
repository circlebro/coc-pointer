"""D1 인터페이스를 흉내내는 가짜.

D1은 SQLite라서 파이썬 표준 sqlite3 로 같은 SQL 이 그대로 돈다. 그래서 여기서
검증한 질의는 실제 D1 에서도 같은 결과를 낸다. 다른 점은 부르는 모양뿐이라,
이 파일이 그 모양만 맞춰 준다.

    stmt = db.prepare("SELECT ...").bind(값)
    result = await stmt.all()     # result.results 에 행 목록
    row = await stmt.first()      # 없으면 None
    await stmt.run()              # 쓰기
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SCHEMA = Path(__file__).resolve().parents[1] / "schema.sql"


class FakeRow:
    """D1 은 행의 값을 row.컬럼명 으로 준다. sqlite3 의 행을 그 모양으로 바꾼다."""

    def __init__(self, mapping: dict) -> None:
        self.__dict__.update(mapping)

    def __repr__(self) -> str:
        return f"FakeRow({self.__dict__})"


class FakeResult:
    def __init__(self, rows: list[FakeRow]) -> None:
        self.results = rows


class FakeStatement:
    def __init__(self, conn: sqlite3.Connection, sql: str, params: tuple = ()) -> None:
        self._conn = conn
        self._sql = sql
        self._params = params

    def bind(self, *params) -> FakeStatement:
        return FakeStatement(self._conn, self._sql, params)

    def _run(self) -> sqlite3.Cursor:
        return self._conn.execute(self._sql, self._params)

    async def all(self) -> FakeResult:
        cur = self._run()
        cols = [d[0] for d in cur.description or []]
        return FakeResult([FakeRow(dict(zip(cols, r, strict=True))) for r in cur.fetchall()])

    async def first(self) -> FakeRow | None:
        cur = self._run()
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description or []]
        return FakeRow(dict(zip(cols, row, strict=True)))

    async def run(self) -> None:
        self._run()
        self._conn.commit()


class FakeD1:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def prepare(self, sql: str) -> FakeStatement:
        return FakeStatement(self._conn, sql)


@pytest.fixture
def fake_db() -> FakeD1:
    """스키마가 적용된 빈 데이터베이스.

    ``check_same_thread=False`` 가 필요하다. FastAPI 의 TestClient 는 앱을 다른
    스레드에서 돌리는데, sqlite3 는 기본적으로 만든 스레드 밖의 접근을 막기 때문이다.
    테스트는 한 번에 하나씩 도므로 동시 접근 걱정은 없다.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return FakeD1(conn)
