# 백엔드 서버 도입 구현 계획 (TASK-20)

> **작업자에게:** 이 계획은 `superpowers:subagent-driven-development` 또는
> `superpowers:executing-plans`로 한 작업씩 실행한다. 각 단계는 `- [ ]` 체크박스로 표시되어 있다.

**목표:** 파이썬 FastAPI를 Cloudflare Python Workers에 올리고 D1 데이터베이스를 붙여, 이후 기능이 얹힐 서버 기반을 만든다.

**접근:** D1은 SQLite이므로 파이썬 표준 `sqlite3`로 같은 SQL이 돈다. 이 점을 이용해 D1 인터페이스를 흉내내는 가짜를 만들고 로컬에서 pytest로 SQL까지 검증한다. Cloudflare에 올려야만 알 수 있는 것(Pyodide에서 공용 코드가 도는지, 시간대 자료가 있는지)은 `GET /api/health`가 한 번에 확인한다.

**기술:** Python 3.14, FastAPI, Cloudflare Python Workers (Pyodide), D1 (SQLite), uv 작업 공간, pytest

**설계 문서:** `docs/superpowers/specs/2026-09-10-backend-server-design.md`

## 전체 제약

- 파이썬 3.14. `uv`가 가상 환경과 인터프리터를 관리한다. `pip`나 시스템 `python3`를 직접 부르지 않는다
- Python Workers는 **비동기 HTTP 라이브러리만** 쓸 수 있다. `httpx`는 되고 `requests`는 안 된다
- 무료 플랜은 요청 한 건당 **CPU 10밀리초**. 무거운 계산을 요청 처리 중에 하지 않는다
- 점수 규칙은 `packages/core/src/coc_core/scoring.py` 한 곳에만 둔다. 서버가 규칙을 다시 쓰지 않는다
- CoC API 토큰과 관리자 비밀번호는 `.env`와 Cloudflare Secret에만 둔다. 코드·저장소·대화에 넣지 않는다
- 커밋 제목은 `타입: 한국어 요약` 형식. 본문은 한국어 불릿. `Co-Authored-By`와 `Claude-Session` 트레일러를 유지한다
- ruff 검사와 형식 검사를 통과해야 한다: `uv run ruff check .` / `uv run ruff format --check .`

## 파일 구조

| 파일 | 책임 |
|---|---|
| `apps/api/schema.sql` | D1 표 정의. 설계 문서 4절 여덟 개 표 |
| `apps/api/src/db.py` | D1 질의. **SQL 문자열은 여기에만 둔다** |
| `apps/api/src/worker.py` | FastAPI 앱, 경로, Workers 진입점 |
| `apps/api/tests/conftest.py` | `sqlite3`를 D1 인터페이스로 감싼 가짜와 pytest 픽스처 |
| `apps/api/tests/test_db.py` | `db.py` 질의가 실제 SQL로 도는지 |
| `apps/api/tests/test_worker.py` | 엔드포인트가 올바른 응답을 내는지 |
| `apps/api/pyproject.toml` | 의존성. 작업 공간 멤버가 된다 |
| `apps/api/wrangler.toml` | Workers 설정. `python_workers` 플래그, D1 바인딩 |
| `apps/api/deploy.sh` | D1 생성 → 표 만들기 → `coc_core` 복사 → 배포 |

SQL을 `db.py` 한 곳에 모으는 이유는 `worker.py`가 얇아지고, 가짜 D1으로 SQL만 따로 검증할 수 있기 때문이다.

---

### Task 1: 가짜 D1과 스키마

D1 인터페이스를 흉내내는 가짜를 만들고, 그 위에서 스키마가 실제로 만들어지는지 확인한다.

**파일:**
- 생성: `apps/api/schema.sql`
- 생성: `apps/api/tests/conftest.py`
- 생성: `apps/api/pyproject.toml`
- 수정: `pyproject.toml` (작업 공간에 `apps/api` 추가, 테스트 경로 추가)

**인터페이스:**
- 만들어 내는 것: `fake_db` 픽스처. `prepare(sql).bind(*params).all() / .first() / .run()`을 `await`로 부를 수 있는 객체. `all()`의 결과는 `.results` 속성에 행 목록을 담고, 각 행은 `row.컬럼명`으로 값을 읽는다

- [ ] **1단계: `apps/api/pyproject.toml`을 만든다**

```toml
[project]
name = "coc-api"
version = "0.5.0"
description = "coc-pointer API 서버 (Cloudflare Python Workers)"
authors = [
    { name = "박원형", email = "circle@mz.co.kr" }
]
requires-python = ">=3.14"
dependencies = [
    "coc-core",
    "fastapi>=0.115",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "ruff>=0.16.6",
    "httpx>=0.28.1",
]

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`httpx`가 개발 의존성에 있는 이유는 FastAPI의 `TestClient`가 그것을 쓰기 때문이다. 서버 코드가 쓰는 것이 아니다.

Workers에 올릴 때는 `coc-core`를 PyPI에서 받을 수 없다. `deploy.sh`가 소스를 복사해 넣는다(Task 4).

- [ ] **2단계: 루트 `pyproject.toml`에 작업 공간 멤버와 테스트 경로를 더한다**

`[tool.uv.workspace]`의 `members`를 이렇게 바꾼다.

```toml
members = ["apps/web", "apps/api", "packages/core"]
```

`[tool.uv.sources]`에 한 줄을 더한다.

```toml
coc-api = { workspace = true }
```

`[tool.pytest.ini_options]`의 `testpaths`를 이렇게 바꾼다.

```toml
testpaths = ["apps/web/tests", "apps/api/tests", "packages/core/tests"]
```

- [ ] **3단계: `apps/api/schema.sql`을 만든다**

설계 문서 4절 그대로다. 여덟 개 표를 순서대로 넣는다. 참조하는 표가 먼저 와야 한다.

```sql
-- coc-pointer D1 스키마
-- 설계: docs/superpowers/specs/2026-09-10-backend-server-design.md 4절
--
-- SQLite에는 참·거짓 타입이 없다. 0과 1을 담는 INTEGER 열로 두고
-- 파이썬에서 bool()로 바꿔 쓴다.

CREATE TABLE IF NOT EXISTS wars (
  id                 TEXT PRIMARY KEY,
  war_type           TEXT NOT NULL,
  start_time         TEXT NOT NULL,
  end_time           TEXT NOT NULL,
  team_size          INTEGER NOT NULL,
  attacks_per_member INTEGER NOT NULL,
  opponent_tag       TEXT NOT NULL,
  opponent_name      TEXT NOT NULL,
  in_progress        INTEGER NOT NULL DEFAULT 0,
  round_no           INTEGER,
  total_rounds       INTEGER
);

CREATE TABLE IF NOT EXISTS war_members (
  war_id   TEXT NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
  tag      TEXT NOT NULL,
  name     TEXT NOT NULL,
  townhall INTEGER NOT NULL,
  PRIMARY KEY (war_id, tag)
);

CREATE TABLE IF NOT EXISTS attacks (
  war_id       TEXT NOT NULL,
  attacker_tag TEXT NOT NULL,
  attack_order INTEGER NOT NULL,
  stars        INTEGER NOT NULL,
  PRIMARY KEY (war_id, attacker_tag, attack_order),
  FOREIGN KEY (war_id, attacker_tag)
    REFERENCES war_members(war_id, tag) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS members (
  tag                TEXT PRIMARY KEY,
  name               TEXT NOT NULL,
  role               TEXT,
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,
  in_clan            INTEGER NOT NULL DEFAULT 1,
  first_seen_at      TEXT NOT NULL,
  last_seen_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',
  member_tag    TEXT REFERENCES members(tag),
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_scores (
  month       TEXT NOT NULL,
  tag         TEXT NOT NULL,
  name        TEXT NOT NULL,
  attacks     INTEGER NOT NULL,
  stars       INTEGER NOT NULL,
  score       REAL NOT NULL,
  computed_at TEXT NOT NULL,
  PRIMARY KEY (month, tag)
);

CREATE TABLE IF NOT EXISTS draws (
  month      TEXT PRIMARY KEY,
  winners    TEXT NOT NULL,
  candidates TEXT NOT NULL,
  slots      INTEGER NOT NULL,
  drawn_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wars_end_time ON wars(end_time);
CREATE INDEX IF NOT EXISTS idx_monthly_scores_month ON monthly_scores(month);
```

- [ ] **4단계: 가짜 D1을 만든다**

`apps/api/tests/conftest.py`를 만든다.

```python
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
```

- [ ] **5단계: 스키마가 실제로 만들어지는지 확인하는 테스트를 쓴다**

`apps/api/tests/test_db.py`를 만든다. `async def` 테스트를 그냥 쓰는데, 다음 단계에서 pytest가 알아서 돌리도록 설정한다.

```python
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
```

- [ ] **6단계: 비동기 테스트를 돌릴 수 있게 한다**

pytest는 기본으로 `async def` 테스트를 돌리지 못한다. `apps/api/pyproject.toml`의 `dev` 묶음에 한 줄을 더한다.

```toml
    "pytest-asyncio>=1.0",
```

같은 파일의 `[tool.pytest.ini_options]`에 한 줄을 더한다.

```toml
asyncio_mode = "auto"
```

`asyncio_mode = "auto"`로 두면 `async def` 테스트에 `@pytest.mark.asyncio`를 붙이지 않아도 pytest가 알아서 돌린다.

루트 `pyproject.toml`의 `[dependency-groups]` `dev`에도 같은 줄을 더한다. 루트에서 `uv run pytest`로 전체를 돌리기 때문이다.

```toml
    "pytest-asyncio>=1.0",
```

- [ ] **7단계: 동기화하고 테스트를 돌린다**

```bash
uv sync
uv run pytest apps/api/tests/test_db.py -v
```

기대: `test_스키마가_여덟_개_표를_만든다` 통과.

- [ ] **8단계: 전체 테스트와 검사를 돌린다**

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

기대: 기존 99개에 1개가 더해져 100개 통과. 검사 통과.

- [ ] **9단계: 커밋한다**

```bash
git add apps/api/pyproject.toml apps/api/schema.sql apps/api/tests pyproject.toml uv.lock
git commit -F - <<'MSG'
feat: D1 스키마와 가짜 D1 테스트 기반 마련

- 설계 문서 4절의 여덟 개 표를 schema.sql 로 옮김
- D1 은 SQLite 라서 파이썬 sqlite3 로 같은 SQL 이 돈다. 이를 이용해
  D1 인터페이스를 흉내내는 가짜를 만들어 로컬에서 SQL 까지 검증한다
- apps/api 를 uv 작업 공간 멤버로 등록

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 2: D1 질의 계층

SQL을 한 곳에 모은다. 이후 모든 기능이 이 함수들을 부른다.

**파일:**
- 생성: `apps/api/src/db.py`
- 수정: `apps/api/tests/test_db.py`

**인터페이스:**
- 쓰는 것: Task 1의 `fake_db` 픽스처
- 만들어 내는 것:
  - `async def list_tables(db) -> list[str]`
  - `async def get_monthly_scores(db, month: str) -> list[dict]` — 점수 높은 순. 각 항목은 `{"tag", "name", "attacks", "stars", "score"}`
  - `async def get_draw(db, month: str) -> dict | None` — 없으면 `None`. 있으면 `{"month", "winners", "candidates", "slots", "drawn_at"}`이고 `winners`와 `candidates`는 이미 목록으로 풀려 있다
  - `async def save_draw(db, month, winners, candidates, slots, drawn_at) -> None`

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_db.py`의 기존 테스트 아래에 붙인다. 맨 위 import에 한 줄을 더한다.

```python
from db import get_draw, get_monthly_scores, list_tables, save_draw
```

```python
async def test_표_목록을_돌려준다(fake_db):
    assert "monthly_scores" in await list_tables(fake_db)


async def test_월_점수는_높은_순으로_나온다(fake_db):
    await fake_db.prepare(
        "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ).bind("2026-09", "#AAA", "도토리", 10, 25, 87.5, "2026-09-10T00:00:00Z").run()
    await fake_db.prepare(
        "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ).bind("2026-09", "#BBB", "히로", 12, 30, 93.75, "2026-09-10T00:00:00Z").run()

    rows = await get_monthly_scores(fake_db, "2026-09")

    assert [r["name"] for r in rows] == ["히로", "도토리"]
    assert rows[0]["score"] == 93.75
    assert rows[0]["attacks"] == 12


async def test_다른_달_점수는_섞이지_않는다(fake_db):
    await fake_db.prepare(
        "INSERT INTO monthly_scores (month, tag, name, attacks, stars, score, computed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    ).bind("2026-08", "#AAA", "도토리", 10, 25, 87.5, "2026-09-10T00:00:00Z").run()

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
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_db.py -v
```

기대: `ModuleNotFoundError: No module named 'db'`로 수집 단계에서 실패.

- [ ] **3단계: `apps/api/src/db.py`를 쓴다**

```python
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

_TABLES = "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"

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
```

- [ ] **4단계: 테스트가 `db`를 찾을 수 있게 한다**

`apps/api/pyproject.toml`의 `[tool.pytest.ini_options]`에 한 줄을 더한다.

```toml
pythonpath = ["src"]
```

루트 `pyproject.toml`의 `[tool.pytest.ini_options]`에도 같은 줄을 더한다. 루트에서 돌릴 때도 찾아야 하기 때문이다.

```toml
pythonpath = ["apps/api/src"]
```

- [ ] **5단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_db.py -v
```

기대: 여섯 개 모두 통과.

- [ ] **6단계: 전체 테스트와 검사**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

기대: 105개 통과, 검사 통과.

- [ ] **7단계: 커밋한다**

```bash
git add apps/api/src/db.py apps/api/tests/test_db.py apps/api/pyproject.toml pyproject.toml uv.lock
git commit -F - <<'MSG'
feat: D1 질의 계층 추가

- SQL 문자열을 db.py 한 곳에 모아 worker 가 얇아지게 함
- 월 점수 조회, 추첨 결과 조회와 저장
- 다시 뽑기는 ON CONFLICT 로 덮어쓴다
- 가짜 D1 위에서 실제 SQL 로 검증. 테스트 6개

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 3: FastAPI 앱과 엔드포인트

**파일:**
- 생성: `apps/api/src/worker.py` (이미 초안이 있다면 이 내용으로 바꾼다)
- 생성: `apps/api/tests/test_worker.py`

**인터페이스:**
- 쓰는 것: Task 2의 `db.get_monthly_scores`, `db.get_draw`
- 만들어 내는 것:
  - `app` — FastAPI 인스턴스
  - `get_db(request)` — 의존성. 테스트에서 `app.dependency_overrides[get_db]`로 바꿔 끼운다
  - `get_env(request)` — 의존성. 환경 변수와 바인딩을 담은 객체
  - `Default` — Workers 진입점

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_worker.py`를 만든다.

```python
"""엔드포인트가 올바른 응답을 내는지 확인한다.

Workers 런타임 없이 FastAPI 만 띄워 확인한다. D1 자리에는 Task 1 의 가짜를,
환경 변수 자리에는 아래 FakeEnv 를 끼운다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from worker import app, get_db, get_env


class FakeEnv:
    API_VERSION = "0.5.0"


@pytest.fixture
def client(fake_db):
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_env] = lambda: FakeEnv()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_는_표_목록과_판을_알려준다(client):
    body = client.get("/api/health").json()

    assert body["version"] == "0.5.0"
    assert body["coc_core"] == "ok"
    assert "monthly_scores" in body["tables"]


def test_health_는_공용_코드가_도는지_확인한다(client):
    body = client.get("/api/health").json()

    # 점수 규칙을 실제로 읽어 왔다면 개수가 0 이 아니다
    assert body["rules"] > 0
    # 한국 시간이 계산되었다면 날짜 모양이다
    assert len(body["kst_now"]) == 16


def test_응답에_판_번호가_붙는다(client):
    assert client.get("/api/health").headers["X-Api-Version"] == "0.5.0"


def test_점수가_없는_달은_빈_목록(client):
    body = client.get("/api/scores/2026-09").json()

    assert body == {"month": "2026-09", "members": []}


def test_점수를_높은_순으로_돌려준다(client, fake_db):
    import asyncio

    async def seed():
        for tag, name, attacks, stars, score in [
            ("#AAA", "도토리", 10, 25, 87.5),
            ("#BBB", "히로", 12, 30, 93.75),
        ]:
            await fake_db.prepare(
                "INSERT INTO monthly_scores "
                "(month, tag, name, attacks, stars, score, computed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)"
            ).bind("2026-09", tag, name, attacks, stars, score, "2026-09-10T00:00:00Z").run()

    asyncio.run(seed())

    body = client.get("/api/scores/2026-09").json()

    assert [m["name"] for m in body["members"]] == ["히로", "도토리"]


def test_뽑지_않은_달은_drawn_이_거짓(client):
    body = client.get("/api/draws/2026-09").json()

    assert body == {"month": "2026-09", "drawn": False}
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_worker.py -v
```

기대: `ModuleNotFoundError: No module named 'worker'` 또는 `ImportError`로 실패.

- [ ] **3단계: `apps/api/src/worker.py`를 쓴다**

```python
"""리그전 보상 추첨과 점수 조회를 맡는 API 서버.

Cloudflare Python Workers 위에서 돈다. FastAPI 앱을 ``asgi.entrypoint`` 로 감싸면
Workers 가 들어온 요청을 그대로 넘겨주고, 바인딩과 비밀값은 요청의
``scope["env"]`` 에 붙어 온다.

점수 규칙은 여기 없다. 규칙은 packages/core 의 ``coc_core.scoring`` 한 곳에만 있다.
배포할 때 deploy.sh 가 coc_core 를 src/ 로 복사한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import db
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="coc-pointer API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://circlebro.github.io", "http://localhost:8000"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def get_env(request: Request) -> Any:
    """Workers 가 넘겨준 환경. 바인딩과 비밀값이 여기 붙어 있다.

    테스트에서는 dependency_overrides 로 가짜를 끼운다.
    """
    return request.scope["env"]


def get_db(request: Request) -> Any:
    """D1 바인딩."""
    return request.scope["env"].DB


@app.middleware("http")
async def stamp_version(request: Request, call_next):
    """어느 배포본이 답했는지 응답만 보고 알 수 있게 한다."""
    response = await call_next(request)
    env = request.scope.get("env")
    response.headers["X-Api-Version"] = getattr(env, "API_VERSION", "unknown")
    return response


@app.get("/api/health")
async def health(env: Any = Depends(get_env), database: Any = Depends(get_db)) -> dict:
    """배포가 제대로 되었는지 한 번에 확인한다.

    Pyodide 위에서 공용 코드가 도는지, 시간대 자료가 있는지, D1 이 붙었는지를
    각각 확인해 돌려준다. 하나라도 실패하면 그 자리에 이유가 적힌다.
    """
    result: dict = {"version": getattr(env, "API_VERSION", "unknown")}

    try:
        from coc_core.scoring import KST, RULES

        result["coc_core"] = "ok"
        result["rules"] = len(RULES)
        result["kst_now"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    except Exception as exc:  # noqa: BLE001 - 무엇이 왜 실패했는지 그대로 보여준다
        result["coc_core"] = f"실패: {type(exc).__name__}: {exc}"

    try:
        result["tables"] = await db.list_tables(database)
    except Exception as exc:  # noqa: BLE001
        result["tables"] = f"실패: {type(exc).__name__}: {exc}"

    return result


@app.get("/api/scores/{month}")
async def get_scores(month: str, database: Any = Depends(get_db)) -> dict:
    """그달 점수표. 수집할 때 미리 계산해 둔 것을 읽기만 한다."""
    return {"month": month, "members": await db.get_monthly_scores(database, month)}


@app.get("/api/draws/{month}")
async def get_draw(month: str, database: Any = Depends(get_db)) -> dict:
    """그달 추첨 결과. 아직 뽑지 않았으면 ``drawn`` 이 거짓이다."""
    drawn = await db.get_draw(database, month)
    if drawn is None:
        return {"month": month, "drawn": False}
    return {"drawn": True, **drawn}


try:  # Workers 런타임에서만 있는 모듈이라 로컬 테스트에서는 건너뛴다
    import asgi

    Default = asgi.entrypoint(app)
except ImportError:  # pragma: no cover - 로컬에서는 FastAPI 앱만 쓴다
    Default = None
```

`asgi` import를 `try`로 감싼 이유는, 그 모듈이 Workers 런타임에만 있어 로컬에서 테스트할 때 `ImportError`가 나기 때문이다.

- [ ] **4단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_worker.py -v
```

기대: 여섯 개 모두 통과.

만약 `test_health_는_공용_코드가_도는지_확인한다`가 `coc_core` 관련으로 실패하면, `apps/api/pyproject.toml`의 `dependencies`에 `coc-core`가 있는지, `uv sync`를 돌렸는지 확인한다.

- [ ] **5단계: 전체 테스트와 검사**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

기대: 111개 통과, 검사 통과.

- [ ] **6단계: 커밋한다**

```bash
git add apps/api/src/worker.py apps/api/tests/test_worker.py
git commit -F - <<'MSG'
feat: FastAPI 앱과 조회 엔드포인트 추가

- health 가 공용 코드·시간대·D1 을 한 번에 확인한다. 올려 보기 전에는
  알 수 없는 것들을 배포 후 한 번의 호출로 판정하기 위해서다
- 월 점수 조회와 추첨 결과 조회
- 응답마다 X-Api-Version 헤더를 붙여 어느 배포본이 답했는지 알 수 있게 함
- D1 과 환경을 의존성으로 받아 테스트에서 가짜로 바꿔 끼운다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 4: 배포 설정

**파일:**
- 수정: `apps/api/wrangler.toml`
- 수정: `apps/api/deploy.sh`
- 삭제: `apps/api/draw.js`
- 수정: `.gitignore`
- 수정: `CLAUDE.md`

**인터페이스:**
- 쓰는 것: Task 1의 `schema.sql`, Task 3의 `worker.py`
- 만들어 내는 것: `./apps/api/deploy.sh` 한 번으로 D1 생성부터 배포까지 끝나는 절차

- [ ] **1단계: `apps/api/wrangler.toml`을 바꾼다**

기존 내용을 모두 지우고 아래로 바꾼다.

```toml
# Cloudflare Workers 설정.
# 배포는 ./deploy.sh 로 한다. database_id 는 그 스크립트가 채운다.
name = "coc-api"
main = "src/worker.py"
compatibility_date = "2026-09-01"
compatibility_flags = ["python_workers"]

[vars]
API_VERSION = "0.5.0"

[[d1_databases]]
binding = "DB"
database_name = "coc-pointer"
database_id = "PUT_D1_ID_HERE"

[observability]
enabled = true
```

`compatibility_flags`에 `python_workers`가 있어야 파이썬이 돈다. 오픈 베타라서 필요한 표시다.

- [ ] **2단계: 옛 자바스크립트 서버가 지워졌는지 확인한다**

```bash
ls apps/api/
```

기대: `draw.js`가 없다. 이 파일은 브라우저가 보낸 후보 명단을 그대로 믿는 방식이라 더 쓰지 않는다. 서버가 후보를 직접 정하는 방식으로 바뀌었다.

아직 남아 있다면 지운다.

```bash
git rm apps/api/draw.js
```

- [ ] **3단계: `.gitignore`에 한 줄을 더한다**

```
apps/api/src/coc_core/
```

배포할 때 공용 코드를 여기로 복사하는데, 그것은 `packages/core`의 사본이므로 저장소에 두 벌 두지 않는다.

- [ ] **4단계: `apps/api/deploy.sh`를 바꾼다**

기존 내용을 모두 지우고 아래로 바꾼다.

```bash
#!/usr/bin/env bash
# API 서버를 Cloudflare에 올린다.
#
#   ./apps/api/deploy.sh
#
# 처음 실행하면 로그인을 묻고, 데이터베이스를 만들고, 표를 만든 뒤 배포한다.
# 두 번째부터는 공용 코드를 새로 복사해 배포만 다시 한다.
set -euo pipefail
cd "$(dirname "$0")"

WRANGLER="npx --yes wrangler@4"

echo "== 1/5 Cloudflare 로그인 확인 =="
if ! $WRANGLER whoami >/dev/null 2>&1; then
  echo "브라우저가 열립니다. Cloudflare 계정으로 허용해 주세요."
  $WRANGLER login
fi

echo
echo "== 2/5 데이터베이스 준비 =="
if grep -q "PUT_D1_ID_HERE" wrangler.toml; then
  echo "coc-pointer 데이터베이스를 만듭니다."
  created=$($WRANGLER d1 create coc-pointer 2>&1 | tee /dev/stderr)
  d1_id=$(printf '%s' "$created" | grep -oE '[0-9a-f-]{36}' | head -1)
  if [ -z "$d1_id" ]; then
    echo
    echo "데이터베이스 id를 자동으로 찾지 못했습니다. 위 출력에서 id를 복사해"
    echo "apps/api/wrangler.toml의 PUT_D1_ID_HERE 자리에 넣고 다시 실행해 주세요."
    exit 1
  fi
  perl -pi -e "s/PUT_D1_ID_HERE/$d1_id/" wrangler.toml
  echo "데이터베이스 id를 기록했습니다: $d1_id"
else
  echo "이미 준비되어 있습니다."
fi

echo
echo "== 3/5 표 만들기 =="
# schema.sql 은 CREATE TABLE IF NOT EXISTS 라서 여러 번 돌려도 안전하다.
$WRANGLER d1 execute coc-pointer --remote --file=schema.sql

echo
echo "== 4/5 공용 코드 복사 =="
# Workers 는 PyPI 에 없는 패키지를 받을 수 없으므로 소스를 함께 올린다.
rm -rf src/coc_core
cp -R ../../packages/core/src/coc_core src/coc_core
echo "packages/core → src/coc_core"

echo
echo "== 5/5 배포 =="
$WRANGLER deploy

echo
echo "끝났습니다. 위에 보이는 주소 뒤에 /api/health 를 붙여 열어 보세요."
echo "coc_core 가 ok 이고 표 여덟 개가 보이면 성공입니다."
```

- [ ] **5단계: 스크립트를 실행할 수 있게 한다**

```bash
chmod +x apps/api/deploy.sh
```

- [ ] **6단계: `CLAUDE.md`의 Layout 절을 고친다**

`apps/api` 설명을 찾아 아래로 바꾼다.

```
- `apps/api/`: Python app on Cloudflare Workers — the API server and the scheduled
  collector. `src/worker.py` is the FastAPI app, `src/db.py` holds every SQL string,
  `schema.sql` defines the D1 tables, `deploy.sh` creates the database and deploys.
  `src/coc_core/` is a build-time copy of `packages/core` and is gitignored.
```

- [ ] **7단계: 검사를 돌린다**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
bash -n apps/api/deploy.sh
```

기대: 테스트 111개 통과, 검사 통과, 스크립트 문법 오류 없음.

- [ ] **8단계: 커밋한다**

```bash
git add apps/api/wrangler.toml apps/api/deploy.sh .gitignore CLAUDE.md
git commit -F - <<'MSG'
chore: API 서버 배포 설정을 파이썬 기준으로 교체

- wrangler.toml 에 python_workers 플래그와 D1 바인딩을 넣음
- deploy.sh 가 데이터베이스 생성, 표 만들기, 공용 코드 복사, 배포를 한 번에 한다
- Workers 는 PyPI 에 없는 패키지를 못 받으므로 packages/core 소스를 복사해 올린다
- 브라우저가 보낸 명단을 믿던 draw.js 를 지움

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 5: 실제 배포와 검증

**여기서부터는 사용자 손이 필요하다.** Cloudflare 계정에 로그인해야 하기 때문이다.

**파일:** 없음. 확인만 한다.

**인터페이스:**
- 쓰는 것: Task 4의 `deploy.sh`
- 만들어 내는 것: 도는 서버 주소와, 설계 문서 7절 항목들의 판정 결과

- [ ] **1단계: 사용자에게 배포를 요청한다**

사용자에게 이렇게 안내한다.

> 터미널에 `! ./apps/api/deploy.sh` 를 입력해 주십시오. 브라우저가 열려 Cloudflare 로그인을 묻습니다. 계정이 없으시면 무료로 만드실 수 있습니다.

`!` 를 앞에 붙이면 이 세션에서 실행되어 결과가 대화에 남는다.

- [ ] **2단계: health 응답을 확인한다**

배포가 끝나면 주소가 나온다. 거기에 `/api/health` 를 붙여 연다.

기대하는 응답:

```json
{
  "version": "0.5.0",
  "coc_core": "ok",
  "rules": 6,
  "kst_now": "2026-09-10 21:30",
  "tables": ["attacks", "draws", "members", "monthly_scores",
             "settings", "users", "war_members", "wars"]
}
```

- [ ] **3단계: 판정한다**

| 응답 | 뜻 | 다음 |
|---|---|---|
| 위와 같다 | 모두 성공 | Task 5를 마치고 TASK-23으로 넘어간다 |
| `coc_core`에 `ModuleNotFoundError` | 공용 코드가 안 올라갔다 | `deploy.sh` 4단계 복사가 됐는지, `src/coc_core/__init__.py`가 있는지 확인 |
| `coc_core`에 `ZoneInfoNotFoundError` | 시간대 자료가 없다 | `apps/api/pyproject.toml` 의존성에 `tzdata`를 더하고 다시 배포 |
| `tables`에 오류 | D1이 안 붙었다 | `wrangler.toml`의 `database_id`가 채워졌는지, 3단계 표 만들기가 성공했는지 확인 |

- [ ] **4단계: 비밀번호 해시 방법을 확인한다**

TASK-23에서 쓸 방법을 미리 판정한다. `apps/api/src/worker.py`에 임시로 아래 경로를 더하고 배포한다.

```python
@app.get("/api/health/crypto")
async def health_crypto() -> dict:
    """비밀번호 해시에 쓸 방법이 되는지 확인한다. 판정 뒤 지운다."""
    result: dict = {}
    try:
        import js

        result["js_crypto"] = hasattr(js.crypto, "subtle")
    except Exception as exc:  # noqa: BLE001
        result["js_crypto"] = f"실패: {type(exc).__name__}: {exc}"

    try:
        import hashlib
        import time

        started = time.monotonic()
        hashlib.pbkdf2_hmac("sha256", b"test", b"salt", 100_000)
        result["pbkdf2_100k_ms"] = round((time.monotonic() - started) * 1000, 1)
    except Exception as exc:  # noqa: BLE001
        result["pbkdf2_100k_ms"] = f"실패: {type(exc).__name__}: {exc}"

    return result
```

`/api/health/crypto`를 연다.

| 응답 | 뜻 |
|---|---|
| `js_crypto`가 `true` | Workers의 암호 기능을 쓸 수 있다. 무료 플랜으로 간다 |
| `js_crypto`가 실패이고 `pbkdf2_100k_ms`가 10 이하 | 파이썬 계산으로도 된다 |
| 둘 다 안 된다 | 유료 플랜이 필요하다. 사용자에게 알린다 |

판정한 결과를 `docs/superpowers/specs/2026-09-10-backend-server-design.md` 6.1절에 적고, 이 임시 경로는 지운다.

- [ ] **5단계: 티켓과 문서를 갱신한다**

옵시디언 `TASK-20 백엔드 서버 도입` 노트에서:
- `상태`를 `완료`로, `스프린트`를 `완료`로, `순서`를 `0`으로 바꾼다
- `남은 것`의 체크박스를 채운다
- 배포된 주소를 적는다

`TASK-23 사용자 관리` 노트의 `상태`를 `진행중`으로 바꾸고 `순서`는 그대로 둔다.

- [ ] **6단계: 커밋한다**

```bash
git add docs/superpowers/specs/2026-09-10-backend-server-design.md apps/api/src/worker.py
git commit -F - <<'MSG'
docs: 배포 확인 결과를 설계 문서에 반영

- Pyodide 에서 공용 코드와 시간대 자료가 도는지 확인함
- 비밀번호 해시 방법을 판정하고 6.1 절에 적음
- 판정용 임시 경로를 지움

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

## 이 계획이 끝나면

`GET /api/health`가 정상 응답을 내는 서버가 Cloudflare에서 돌고, D1에 여덟 개 표가 만들어져 있다. 다음은 TASK-23 사용자 관리다.

이 계획에서 하지 않는 것:
- 로그인과 계정 관리 (TASK-23)
- 수집을 Cron으로 옮기기 (TASK-21)
- 추첨 실행 (TASK-18)
- 페이지를 서버와 연결 (TASK-17)
