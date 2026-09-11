"""표에 못 박은 값 목록과 도메인 자료형이 갈라지지 않는지 본다.

같은 목록이 두 곳에 적혀 있다. SQL 의 CHECK 절과 coc_core 의 열거형이다.
한쪽만 늘리면 이런 일이 생긴다.

- 열거형에만 늘리면: 새 값을 저장하려는 순간 표가 거부한다
- CHECK 에만 늘리면: 저장은 되는데 읽어 들일 때 그 행 때문에 조회가 죽는다

둘 다 실제로 겪기 전에는 눈치채기 어려우므로 여기서 미리 맞춰 본다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from coc_core.member.models import ClanRole, MemberStatus

MIGRATIONS = Path(__file__).resolve().parent.parent / "database" / "migrations"

_COLUMNS = (
    "id, tag, name, role, townhall, trophies, donations, donations_received, "
    "status, created_at, updated_at, description"
)
_INSERT = f"INSERT INTO clan_members ({_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
NOW = "2026-09-11T00:00:00Z"


@pytest.fixture
def conn() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        db.executescript(path.read_text(encoding="utf-8"))
    return db


def _insert(db: sqlite3.Connection, tag: str, role: str, status: str) -> None:
    db.execute(_INSERT, (f"id{tag}", tag, "아무개", role, 16, 4200, 0, 0, status, NOW, NOW, None))


@pytest.mark.parametrize("role", [r.value for r in ClanRole])
def test_도메인이_아는_직책은_모두_담긴다(conn: sqlite3.Connection, role: str) -> None:
    _insert(conn, f"#{role}", role, "ACTIVE")

    assert conn.execute("SELECT role FROM clan_members").fetchone()[0] == role


@pytest.mark.parametrize("status", [s.value for s in MemberStatus])
def test_도메인이_아는_상태는_모두_담긴다(conn: sqlite3.Connection, status: str) -> None:
    _insert(conn, f"#{status}", "MEMBER", status)

    assert conn.execute("SELECT status FROM clan_members").fetchone()[0] == status


def test_도메인이_모르는_직책은_표가_거부한다(conn: sqlite3.Connection) -> None:
    """읽어 들일 때 죽는 대신 넣을 때 막는다.

    막지 않으면 그 한 행 때문에 클랜원 목록 조회가 통째로 실패한다.
    """
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, "#X", "SUPER_LEADER", "ACTIVE")


def test_도메인이_모르는_상태는_표가_거부한다(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, "#Y", "MEMBER", "KICKED")
