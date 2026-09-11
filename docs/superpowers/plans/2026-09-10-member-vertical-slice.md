# 클랜원 조회 관통 구현 계획

> **작업자에게:** 이 계획은 `superpowers:subagent-driven-development` 또는
> `superpowers:executing-plans`로 한 작업씩 실행한다. 각 단계는 `- [ ]` 체크박스로 표시되어 있다.

**목표:** 클랜원 조회 하나를 CoC API에서 React 화면까지 관통시켜, 나머지 화면이 따라올 길을 뚫는다.

**접근:** API 계약(`contracts/openapi.yaml`)을 먼저 쓰고 거기서 서버 모델과 프론트 타입을 생성한다. 도메인은 `packages/core/src/coc_core/member/`에 두고 저장소는 인터페이스(Protocol)로만 안다. D1 어댑터와 CoC API 어댑터가 바깥과 만나는 자리이며, 거기서 외부 표기를 우리 값으로 바꾼다.

**기술:** Python 3.13(Workers 런타임), FastAPI, D1(SQLite), uv 작업 공간, pytest, Vite + React + TypeScript

**설계 문서:** `docs/superpowers/specs/2026-09-10-domain-frontend-split-design.md`

## 전체 제약

- **파이썬 3.13에서 돌아야 한다.** Cloudflare Workers의 Pyodide가 3.13.2다. 3.14 전용 문법(PEP 758의 괄호 없는 다중 except 등)을 쓰면 배포가 막힌다. `packages/core/tests/test_py313_syntax.py`가 이것을 검사한다
- `uv`가 가상 환경을 관리한다. `pip`나 시스템 `python3`를 직접 부르지 않는다
- ruff 검사와 형식 검사를 통과해야 한다: `uv run ruff check .` / `uv run ruff format --check .`
- **ruff는 마크다운 안의 파이썬 코드 블록도 검사한다.** 이 계획서의 코드를 그대로 옮겨 쓰면 통과하도록 이미 형식을 맞춰 두었다
- **SQL 문자열은 어댑터에만 둔다.** 도메인(`coc_core`)에 SQL이 들어가면 안 된다
- **점수 규칙은 `packages/core/src/coc_core/scoring.py` 한 곳에만 있다.** 이 계획은 그것을 건드리지 않는다
- 시각은 UTC ISO 8601 문자열(`2026-09-10T05:30:00Z`). `coc_core.models.to_iso()`를 쓴다
- CoC API 토큰은 `.env`와 Cloudflare Secret에만 둔다. 코드·저장소에 넣지 않는다
- 생성물(`apps/api/src/schemas.py`, `apps/web/src/api/schema.d.ts`)은 손으로 고치지 않는다
- 커밋 제목은 `타입: 한국어 요약` 형식, 본문은 한국어 불릿. 트레일러 두 줄을 유지한다:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU`
- 스테이징은 경로를 명시한다. `git add -A`를 쓰지 않는다
- **배포 명령을 실행하지 않는다.** `pywrangler deploy`, `wrangler d1 ... --remote`는 사람이 한다. `--local`은 괜찮다

## 파일 구조

| 파일 | 책임 |
|---|---|
| `contracts/openapi.yaml` | **계약.** 손으로 쓴다. 서버와 프론트가 여기서 나온다 |
| `scripts/generate-from-contract.sh` | 계약에서 양쪽 생성 |
| `apps/api/database/migrations/0001_*.sql` | 표 변경 이력. 손으로 쓴다 |
| `apps/api/database/schema.sql` | 현재 전체 구조. 마이그레이션에서 뽑는다 |
| `packages/core/src/coc_core/member/models.py` | `ClanRole`, `MemberStatus`, `ClanMember` |
| `packages/core/src/coc_core/member/repository.py` | `MemberRepository` (Protocol) |
| `packages/core/src/coc_core/member/service.py` | `MemberService`, `SyncResult` |
| `apps/api/src/adapters/coc_api.py` | CoC API 호출. 바깥 표기를 우리 값으로 |
| `apps/api/src/adapters/member_repository.py` | `D1MemberRepository`. SQL은 여기만 |
| `apps/api/src/routes/member.py` | `GET /api/v1/members` |
| `apps/api/src/cli.py` | `refresh-members` 명령 |
| `apps/web/src/pages/Members.tsx` | 클랜원 화면 |

---

### Task 1: 계약과 생성 절차

**파일:**
- 생성: `contracts/openapi.yaml`
- 생성: `scripts/generate-from-contract.sh`
- 수정: `apps/api/pyproject.toml` (생성 도구 추가)
- 수정: `.gitignore`

**인터페이스:**
- 만들어 내는 것: `contracts/openapi.yaml`의 `ClanRole`, `MemberStatus`, `Member`, `MemberListResponse` 스키마. 뒤 작업이 이 이름과 필드를 그대로 쓴다

- [ ] **1단계: 계약을 쓴다**

`contracts/openapi.yaml`을 만든다.

```yaml
openapi: 3.1.0
info:
  title: coc-pointer API
  version: 0.5.0
  description: |
    클래시 오브 클랜 클랜 "미니언즈"의 클랜원과 점수를 다루는 API.

    이 파일이 계약이다. 서버 모델과 프론트 타입은 여기서 생성하며
    손으로 고치지 않는다. scripts/generate-from-contract.sh 참고.

servers:
  - url: https://coc-api.coc-api.workers.dev
    description: 운영

paths:
  /api/v1/members:
    get:
      operationId: listMembers
      summary: 클랜원 목록
      tags: [members]
      parameters:
        - name: tag
          in: query
          required: false
          description: 플레이어 태그로 좁힌다. '#'을 포함해 넘긴다
          schema:
            type: string
            example: "#2ABC123"
      responses:
        "200":
          description: 클랜원 목록
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/MemberListResponse"

components:
  schemas:
    ClanRole:
      type: string
      description: |
        게임 안 직책. CoC API 표기를 대문자로 바꾼 값이다.
        ADMIN 은 게임 화면에서 "장로(Elder)"로 불린다.
        UNKNOWN 은 CoC 가 우리가 모르는 값을 보냈다는 뜻이다.
      enum: [LEADER, COLEADER, ADMIN, MEMBER, UNKNOWN]

    MemberStatus:
      type: string
      description: |
        클랜 소속 여부. CoC API 가 주지 않고 우리가 판정한다.
        목록에 있으면 ACTIVE, 사라지면 INACTIVE 로 내린다.
      enum: [ACTIVE, INACTIVE]

    Member:
      type: object
      required:
        - id
        - tag
        - name
        - role
        - status
        - createdAt
        - updatedAt
      properties:
        id:
          type: string
          format: uuid
          description: 우리 식별자
        tag:
          type: string
          description: CoC 플레이어 태그
          example: "#2ABC123"
        name:
          type: string
        role:
          $ref: "#/components/schemas/ClanRole"
        status:
          $ref: "#/components/schemas/MemberStatus"
        townhall:
          type: integer
          nullable: true
        trophies:
          type: integer
          nullable: true
        donations:
          type: integer
          nullable: true
        donationsReceived:
          type: integer
          nullable: true
        description:
          type: string
          nullable: true
          description: 관리자 메모. 동기화가 덮어쓰지 않는다
        createdAt:
          type: string
          format: date-time
        updatedAt:
          type: string
          format: date-time

    MemberListResponse:
      type: object
      required: [members]
      properties:
        members:
          type: array
          items:
            $ref: "#/components/schemas/Member"
```

- [ ] **2단계: 생성 도구를 더한다**

`apps/api/pyproject.toml`의 `[dependency-groups] dev` 목록 끝에 한 줄을 더한다.

```toml
    "datamodel-code-generator>=0.28",
```

루트 `pyproject.toml`의 `[dependency-groups] dev`에도 같은 줄을 더한다. 루트에서 생성 명령을 돌리기 때문이다.

- [ ] **3단계: 생성 스크립트를 만든다**

`scripts/generate-from-contract.sh`를 만든다.

```bash
#!/usr/bin/env bash
# 계약에서 서버 모델과 프론트 타입을 생성한다.
#
#   ./scripts/generate-from-contract.sh
#
# 생성물은 손으로 고치지 않는다. 고치려면 contracts/openapi.yaml 을 고치고
# 이 스크립트를 다시 돌린다.
set -euo pipefail
cd "$(dirname "$0")/.."

CONTRACT="contracts/openapi.yaml"

echo "== 서버 모델 (Pydantic) =="
uv run datamodel-codegen \
  --input "$CONTRACT" \
  --input-file-type openapi \
  --output apps/api/src/schemas.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.13 \
  --use-standard-collections \
  --use-union-operator \
  --custom-file-header "# 이 파일은 contracts/openapi.yaml 에서 생성되었다. 손으로 고치지 마라."
echo "  → apps/api/src/schemas.py"

echo
echo "== 프론트 타입 (TypeScript) =="
mkdir -p apps/web/src/api
npx --yes openapi-typescript@7 "$CONTRACT" -o apps/web/src/api/schema.d.ts
echo "  → apps/web/src/api/schema.d.ts"

echo
echo "생성이 끝났습니다. 바뀐 것이 있으면 함께 커밋하세요."
```

실행할 수 있게 한다.

```bash
chmod +x scripts/generate-from-contract.sh
```

- [ ] **4단계: 생성해 본다**

```bash
uv sync
./scripts/generate-from-contract.sh
```

기대: `apps/api/src/schemas.py`에 파이썬 파일이 생기고 `apps/web/src/api/schema.d.ts`가 생긴다.

생성된 파이썬 파일을 열어 `ClanRole`이 다섯 값을 갖는지 확인한다. `schema.d.ts`에서도 `ClanRole: "LEADER" | "COLEADER" | ...`가 보여야 한다.

**`--output`에는 확장자를 붙인다.** `datamodel-code-generator`는 단일 입력·단일 출력일 때 경로 끝의 슬래시를 버리고 그 경로를 그대로 파일 이름으로 쓴다. `apps/api/src/schemas/`라고 적으면 확장자 없는 `schemas` 파일이 만들어져 파이썬이 모듈로 찾지 못한다. 더 고약한 것은 `ruff`도 확장자 없는 파일을 재귀 탐색에서 건너뛰어, 검사가 통과한 것처럼 보이면서 아무것도 검증하지 않는다는 점이다.

- [ ] **5단계: 생성물이 검사를 통과하게 한다**

생성된 코드가 ruff 형식과 어긋날 수 있다. 확인한다.

```bash
uv run ruff check apps/api/src/schemas.py
uv run ruff format --check apps/api/src/schemas.py
```

어긋나면 `uv run ruff format apps/api/src/schemas.py`로 맞춘다. **다만 생성 스크립트를 다시 돌리면 되돌아간다.** 그러니 형식을 맞추는 줄을 생성 스크립트 끝에 넣는다.

```bash
uv run ruff format apps/api/src/schemas.py >/dev/null
```

이 줄을 `scripts/generate-from-contract.sh`의 "프론트 타입" 절 앞에 넣는다.

- [ ] **6단계: `.gitignore`를 확인한다**

생성물은 커밋한다. `.gitignore`에 `schemas/`나 `schema.d.ts`가 걸리지 않는지 본다.

```bash
git check-ignore -v apps/api/src/schemas.py apps/web/src/api/schema.d.ts || echo "무시되지 않음 (정상)"
```

무시된다면 `.gitignore`에서 그 줄을 고친다.

- [ ] **7단계: 전체 검사**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

기대: 테스트 128개 통과, 검사 통과.

- [ ] **8단계: 커밋한다**

```bash
git add contracts/ scripts/generate-from-contract.sh apps/api/pyproject.toml pyproject.toml uv.lock apps/api/src/schemas.py apps/web/src/api/schema.d.ts
git commit -F - <<'MSG'
feat: API 계약과 생성 절차 마련

- contracts/openapi.yaml 이 계약이다. 서버 모델과 프론트 타입이 여기서 나온다
- 명세를 하나로 둔다. 서버용·프론트용으로 나누면 무엇이 진짜인지 알 수 없다
- 생성물은 손으로 고치지 않는다. 파일 머리에 그 규칙을 적었다
- 생성물을 커밋해 명세를 고쳤을 때 무엇이 따라 바뀌었는지 PR 에서 보이게 한다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 2: 마이그레이션 체계와 clan_members 표

**파일:**
- 생성: `apps/api/database/migrations/0001_clan_members.sql`
- 생성: `apps/api/database/schema.sql`
- 생성: `scripts/dump-schema.sh`
- 삭제: `apps/api/schema.sql`
- 수정: `apps/api/wrangler.toml`
- 수정: `apps/api/deploy.sh`
- 수정: `apps/api/tests/conftest.py`
- 생성: `apps/api/tests/test_schema.py`

**인터페이스:**
- 쓰는 것: 없음
- 만들어 내는 것: `clan_members` 표. 뒤 작업의 어댑터가 이 컬럼 이름을 그대로 쓴다. `fake_db` 픽스처가 마이그레이션을 적용한 상태로 바뀐다

- [ ] **1단계: 마이그레이션을 쓴다**

`apps/api/database/migrations/0001_clan_members.sql`을 만든다.

```sql
-- 클랜원 표를 새로 만든다.
--
-- 앞선 설계의 members 표를 지우고 clan_members 로 바꾼다. 자료가 하나도
-- 없어 안전하다. 표 이름에 clan 이 들어가 war_members 와 나란히 읽히고,
-- role 컬럼이 users.role(서비스 권한)과 헷갈리지 않는다.

DROP TABLE IF EXISTS members;

CREATE TABLE clan_members (
  id                 TEXT PRIMARY KEY,
  tag                TEXT NOT NULL UNIQUE,
  name               TEXT NOT NULL,

  -- CoC API 가 채운다
  role               TEXT NOT NULL,
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,

  -- 우리가 판정한다
  status             TEXT NOT NULL DEFAULT 'ACTIVE',
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,

  -- 관리자가 적는다. 동기화가 덮어쓰지 않는다
  description        TEXT
);

CREATE INDEX idx_clan_members_status ON clan_members(status);
```

- [ ] **2단계: 남은 표를 옮긴다**

기존 `apps/api/schema.sql`에는 표가 여덟 개 있다. `members`를 뺀 일곱 개를 그대로 옮겨야 한다.

`apps/api/database/migrations/0001_clan_members.sql`의 맨 위(`DROP TABLE` 앞)에 기존 `schema.sql`의 내용 중 **`members` 표 정의만 뺀 나머지 전부**를 붙인다. `wars`, `war_members`, `attacks`, `users`, `settings`, `monthly_scores`, `draws`와 인덱스 두 개다.

`users` 표의 `member_tag TEXT REFERENCES members(tag)` 줄은 참조 대상이 사라지므로 `member_tag TEXT`로 바꾼다. 클랜원과 잇는 일은 나중 티켓에서 다시 정한다.

옮긴 뒤 `apps/api/schema.sql`을 지운다.

```bash
git rm apps/api/schema.sql
```

- [ ] **3단계: `wrangler.toml`에 경로를 알린다**

`main = "src/worker.py"` 줄 아래에 한 줄을 더한다.

```toml
migrations_dir = "database/migrations"
```

- [ ] **4단계: `deploy.sh`의 3/5 단계를 바꾼다**

`apps/api/deploy.sh`에서 이 부분을 찾는다.

```bash
echo "== 3/5 표 만들기 =="
# schema.sql 은 CREATE TABLE IF NOT EXISTS 라서 여러 번 돌려도 안전하다.
$WRANGLER d1 execute coc-pointer --remote --file=schema.sql
```

이렇게 바꾼다.

```bash
echo "== 3/5 표 만들기 =="
# D1 이 어디까지 적용했는지 스스로 기록한다(d1_migrations 표). 이미 적용한
# 파일은 건너뛰므로 여러 번 돌려도 안전하다.
$WRANGLER d1 migrations apply coc-pointer --remote
```

- [ ] **5단계: 스키마 덤프 스크립트를 만든다**

`scripts/dump-schema.sh`를 만든다.

```bash
#!/usr/bin/env bash
# 마이그레이션을 적용한 결과를 apps/api/database/schema.sql 로 뽑는다.
#
#   ./scripts/dump-schema.sh
#
# schema.sql 은 손으로 쓰지 않는다. 마이그레이션이 유일한 원본이고 이 파일은
# 현재 구조를 한눈에 보기 위한 사본이다. 둘이 어긋나면 테스트가 잡는다.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

for f in apps/api/database/migrations/*.sql; do
  sqlite3 "$TMP" < "$f"
done

{
  echo "-- 이 파일은 마이그레이션에서 생성되었다. 손으로 고치지 마라."
  echo "-- 고치려면 apps/api/database/migrations/ 에 파일을 더하고"
  echo "-- ./scripts/dump-schema.sh 를 돌린다."
  echo
  sqlite3 "$TMP" .schema | grep -v '^CREATE TABLE sqlite_'
} > apps/api/database/schema.sql

echo "apps/api/database/schema.sql 갱신됨"
```

실행할 수 있게 하고 돌린다.

```bash
chmod +x scripts/dump-schema.sh
./scripts/dump-schema.sh
```

- [ ] **6단계: 가짜 D1이 마이그레이션을 쓰게 한다**

`apps/api/tests/conftest.py`의 `SCHEMA` 상수와 `fake_db` 픽스처를 바꾼다.

```python
MIGRATIONS = Path(__file__).resolve().parents[1] / "database" / "migrations"
```

```python
@pytest.fixture
def fake_db() -> FakeD1:
    """마이그레이션을 순서대로 적용한 빈 데이터베이스.

    실제 배포와 같은 경로를 지나므로 마이그레이션이 깨지면 여기서 먼저 걸린다.

    ``check_same_thread=False`` 가 필요하다. FastAPI 의 TestClient 는 앱을 다른
    스레드에서 돌리는데, sqlite3 는 기본적으로 만든 스레드 밖의 접근을 막기 때문이다.
    테스트는 한 번에 하나씩 도므로 동시 접근 걱정은 없다.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
    return FakeD1(conn)
```

- [ ] **7단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_schema.py`를 만든다.

```python
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
```

- [ ] **8단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_schema.py -v
```

기대: 둘 다 통과. 실패하면 `./scripts/dump-schema.sh`를 다시 돌린다.

- [ ] **9단계: 기존 테스트가 여전히 도는지 본다**

`apps/api/tests/test_db.py`의 첫 테스트가 표 여덟 개를 기대한다. 이제 `members`가 `clan_members`로 바뀌었으므로 그 목록을 고쳐야 한다.

```python
async def test_스키마가_여덟_개_표를_만든다(fake_db):
    result = await fake_db.prepare(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).all()
    names = [r.name for r in result.results]
    assert names == [
        "attacks",
        "clan_members",
        "draws",
        "monthly_scores",
        "settings",
        "users",
        "war_members",
        "wars",
    ]
```

- [ ] **10단계: 전체 검사**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
bash -n apps/api/deploy.sh && bash -n scripts/dump-schema.sh
```

기대: 테스트 130개 통과, 검사 통과, 스크립트 문법 정상.

- [ ] **11단계: 커밋한다**

```bash
git add apps/api/database/ apps/api/wrangler.toml apps/api/deploy.sh apps/api/tests/ scripts/dump-schema.sh
git rm --cached apps/api/schema.sql 2>/dev/null || true
git commit -F - <<'MSG'
feat: 마이그레이션 체계와 clan_members 표

- apps/api/database/ 아래 migrations/ 와 schema.sql 두 벌로 관리한다.
  마이그레이션이 원본이고 schema.sql 은 현재 구조를 한눈에 보는 사본이다
- schema.sql 은 dump-schema.sh 가 만든다. 손으로 쓰지 않는다.
  둘이 어긋나는 것이 이 방식의 유일한 위험이라 일치를 테스트로 잡는다
- D1 이 어디까지 적용했는지 스스로 기록하므로 배포를 여러 번 돌려도 안전하다
- members 를 clan_members 로 바꿨다. war_members 와 나란히 읽히고
  role 컬럼이 users.role(서비스 권한)과 헷갈리지 않는다
- 가짜 D1 이 마이그레이션을 지나가게 해 배포와 같은 경로를 검증한다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 3: 도메인 자료형

**파일:**
- 생성: `packages/core/src/coc_core/member/__init__.py`
- 생성: `packages/core/src/coc_core/member/models.py`
- 생성: `packages/core/tests/test_member_models.py`

**인터페이스:**
- 만들어 내는 것:
  - `ClanRole` — `StrEnum`. `LEADER` `COLEADER` `ADMIN` `MEMBER` `UNKNOWN`. `from_coc(raw: str) -> ClanRole` 클래스 메서드
  - `MemberStatus` — `StrEnum`. `ACTIVE` `INACTIVE`
  - `ClanMember` — `frozen` 데이터클래스. `id` `tag` `name` `role` `status` `townhall` `trophies` `donations` `donations_received` `description` `created_at` `updated_at`

- [ ] **1단계: 실패하는 테스트를 쓴다**

`packages/core/tests/test_member_models.py`를 만든다.

```python
"""클랜원 자료형."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberStatus


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("leader", ClanRole.LEADER),
        ("coLeader", ClanRole.COLEADER),
        ("admin", ClanRole.ADMIN),
        ("member", ClanRole.MEMBER),
    ],
)
def test_coc_표기를_우리_값으로_바꾼다(raw, expected):
    assert ClanRole.from_coc(raw) == expected


def test_모르는_직책은_UNKNOWN():
    assert ClanRole.from_coc("veteran") == ClanRole.UNKNOWN
    assert ClanRole.from_coc("") == ClanRole.UNKNOWN


def test_문자열처럼_비교된다():
    assert ClanRole.ADMIN == "ADMIN"
    assert MemberStatus.ACTIVE == "ACTIVE"


def test_클랜원은_고칠_수_없다():
    member = ClanMember(
        id="0198f0c1-0000-7000-8000-000000000001",
        tag="#2ABC123",
        name="도토리",
        role=ClanRole.ADMIN,
        status=MemberStatus.ACTIVE,
        townhall=16,
        trophies=4200,
        donations=1200,
        donations_received=800,
        description=None,
        created_at="2026-09-10T05:30:00Z",
        updated_at="2026-09-10T05:30:00Z",
    )

    # 예외를 좁혀 잡는다. Exception 으로 두면 오타 같은 엉뚱한 오류에도
    # 테스트가 통과한다(ruff B017 이 그것을 막는다).
    with pytest.raises(FrozenInstanceError):
        member.name = "다른 이름"  # type: ignore[misc]
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest packages/core/tests/test_member_models.py -v
```

기대: `ModuleNotFoundError: No module named 'coc_core.member'`로 수집 단계에서 실패.

- [ ] **3단계: 자료형을 쓴다**

`packages/core/src/coc_core/member/__init__.py`를 만든다.

```python
"""클랜원 도메인.

자료형(models), 저장소 약속(repository), 로직(service)이 여기 있다.
바깥과 만나는 자리는 repository 의 Protocol 뿐이라, 이 폴더는 D1 도 CoC API 도
모른다.
"""
```

`packages/core/src/coc_core/member/models.py`를 만든다.

```python
"""클랜원 자료형.

CoC API 의 표기를 그대로 들이지 않는다. 어댑터가 경계에서 우리 값으로 바꾸고,
모르는 값이 오면 UNKNOWN 으로 둔다. 그래야 CoC 가 새 직책을 만들어도 한 명
때문에 동기화가 통째로 멈추지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClanRole(StrEnum):
    """게임 안 직책.

    이름을 CoC API 표기의 대문자와 맞춘다. 그래서 변환이 한 줄로 끝난다.
    """

    LEADER = "LEADER"
    COLEADER = "COLEADER"  # 언더스코어를 넣지 않는다. API 의 coLeader 와 맞추기 위해서다
    ADMIN = "ADMIN"  # 게임 화면에서는 "장로(Elder)". API 가 admin 으로 준다
    MEMBER = "MEMBER"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_coc(cls, raw: str) -> ClanRole:
        """CoC API 표기를 우리 값으로. 모르는 값이면 UNKNOWN."""
        try:
            return cls(raw.upper())
        except ValueError:
            return cls.UNKNOWN


class MemberStatus(StrEnum):
    """클랜 소속 여부. CoC API 가 주지 않고 우리가 판정한다."""

    ACTIVE = "ACTIVE"  # 지금 클랜 목록에 있다
    INACTIVE = "INACTIVE"  # 목록에서 사라졌다. 지우지 않고 내려 둔다


@dataclass(frozen=True)
class ClanMember:
    """클랜원 한 명.

    id 는 우리 식별자이고 tag 는 CoC 세계의 식별자다. 주소에서 '#' 을 인코딩하지
    않으려고 id 를 따로 둔다.
    """

    id: str
    tag: str
    name: str
    role: ClanRole
    status: MemberStatus
    townhall: int | None
    trophies: int | None
    donations: int | None
    donations_received: int | None
    description: str | None
    created_at: str
    updated_at: str
```

- [ ] **4단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest packages/core/tests/test_member_models.py -v
```

기대: 일곱 개 모두 통과.

- [ ] **5단계: 3.13 검사가 이 파일도 보는지 확인한다**

```bash
uv run pytest packages/core/tests/test_py313_syntax.py -v
```

기대: 통과. `member/` 아래 파일도 검사 대상에 들어가야 한다. 들어가지 않으면 그 테스트의 탐색 경로를 고친다.

- [ ] **6단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add packages/core/src/coc_core/member/ packages/core/tests/test_member_models.py
git commit -F - <<'MSG'
feat: 클랜원 자료형 추가

- ClanRole 의 이름을 CoC API 표기의 대문자와 맞춰 변환을 한 줄로 끝낸다
- 모르는 직책은 UNKNOWN 으로 둔다. CoC 가 새 값을 보내도 한 명 때문에
  동기화가 통째로 멈추지 않게 하려는 것이다
- status 는 CoC 가 주지 않고 우리가 판정한다. 목록에서 사라지면 INACTIVE
- ClanMember 는 고칠 수 없게 둔다. 도메인 자료형은 값이지 상태가 아니다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 4: 저장소 약속과 서비스

**파일:**
- 생성: `packages/core/src/coc_core/member/repository.py`
- 생성: `packages/core/src/coc_core/member/service.py`
- 생성: `packages/core/tests/test_member_service.py`

**인터페이스:**
- 쓰는 것: Task 3의 `ClanMember`, `ClanRole`, `MemberStatus`
- 만들어 내는 것:
  - `MemberRepository(Protocol)` — `find_all()`, `find_by_tag(tag)`, `upsert_many(members)`, `mark_inactive(tags, now)`
  - `MemberSource(Protocol)` — `fetch_members()`. CoC API 쪽 약속
  - `MemberService(repository, source)` — `sync(now) -> SyncResult`, `find_all()`, `find_by_tag(tag)`
  - `SyncResult` — `total` `added` `left` `unknown_roles`

- [ ] **1단계: 실패하는 테스트를 쓴다**

`packages/core/tests/test_member_service.py`를 만든다.

```python
"""클랜원 서비스.

가짜 대역을 클래스로 만들어 넣는다. 모킹 라이브러리를 쓰지 않는다.
"""

from __future__ import annotations

from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from coc_core.member.service import MemberService

NOW = "2026-09-10T05:30:00Z"


class FakeSource:
    """CoC API 대역. 받아 온 그대로의 값을 흉내낸다."""

    def __init__(self, raw: list[dict]) -> None:
        self.raw = raw

    async def fetch_members(self) -> list[dict]:
        return self.raw


class FakeRepository:
    """저장소 대역. 태그를 열쇠로 담아 둔다."""

    def __init__(self, existing: list[ClanMember] | None = None) -> None:
        self.rows: dict[str, ClanMember] = {m.tag: m for m in (existing or [])}
        self.marked_inactive: list[str] = []

    async def find_all(self) -> list[ClanMember]:
        return list(self.rows.values())

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        return self.rows.get(tag)

    async def upsert_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            if m.tag not in self.rows:
                added += 1
            self.rows[m.tag] = m
        return added

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        for tag in tags:
            row = self.rows.get(tag)
            if row is not None:
                self.rows[tag] = ClanMember(**{**row.__dict__, "status": MemberStatus.INACTIVE})
                self.marked_inactive.append(tag)
        return len(tags)


def _raw(tag: str, name: str, role: str = "member") -> dict:
    return {
        "tag": tag,
        "name": name,
        "role": role,
        "townHallLevel": 16,
        "trophies": 4200,
        "donations": 100,
        "donationsReceived": 50,
    }


async def test_처음_동기화하면_모두_새로_들어온다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.added == 2
    assert result.left == 0
    assert len(await service.find_all()) == 2


async def test_모르는_직책이_와도_나머지는_저장된다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리", "veteran"), _raw("#B", "히로", "member")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.unknown_roles == {"veteran": 1}
    by_tag = {m.tag: m for m in await service.find_all()}
    assert by_tag["#A"].role == ClanRole.UNKNOWN
    assert by_tag["#B"].role == ClanRole.MEMBER


async def test_목록에서_사라지면_INACTIVE_로_내린다():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)

    service_after = MemberService(repository=repository, source=FakeSource([]))
    result = await service_after.sync(now=NOW)

    assert result.left == 1
    assert repository.rows["#A"].status == MemberStatus.INACTIVE
    assert repository.rows["#A"].tag == "#A"  # 지우지 않는다


async def test_돌아온_사람은_다시_ACTIVE():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)
    await MemberService(repository=repository, source=FakeSource([])).sync(now=NOW)

    await MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")])).sync(
        now=NOW
    )

    assert repository.rows["#A"].status == MemberStatus.ACTIVE


async def test_태그로_한_명을_찾는다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )
    await service.sync(now=NOW)

    found = await service.find_by_tag("#B")

    assert found is not None
    assert found.name == "히로"
    assert await service.find_by_tag("#없음") is None
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest packages/core/tests/test_member_service.py -v
```

기대: `ModuleNotFoundError: No module named 'coc_core.member.service'`.

- [ ] **3단계: 저장소 약속을 쓴다**

`packages/core/src/coc_core/member/repository.py`를 만든다.

```python
"""클랜원 저장소 약속.

도메인이 "이런 게 필요하다"고 선언하는 자리다. 구현은 바깥(어댑터)에 있고
도메인은 그것이 D1 인지 파일인지 모른다. Spring 의 Repository 인터페이스와
같은 자리이며, Protocol 이라 구현체가 상속을 선언하지 않아도 된다.
"""

from __future__ import annotations

from typing import Protocol

from coc_core.member.models import ClanMember


class MemberRepository(Protocol):
    """클랜원을 담고 꺼낸다."""

    async def find_all(self) -> list[ClanMember]:
        """모두. 나간 사람(INACTIVE)도 포함한다."""
        ...

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        """태그로 한 명. 없으면 None."""
        ...

    async def upsert_many(self, members: list[ClanMember]) -> int:
        """태그를 열쇠로 넣거나 갱신하고, 새로 들어온 수를 돌려준다.

        description 과 created_at 은 갱신하지 않는다. 관리자가 적은 메모가
        동기화에 지워지면 안 되고, 처음 본 시각은 처음 한 번만 정해진다.
        """
        ...

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        """주어진 태그들을 INACTIVE 로 내리고 그 수를 돌려준다."""
        ...


class MemberSource(Protocol):
    """클랜원 명단을 가져오는 곳. CoC API 가 그 구현이다."""

    async def fetch_members(self) -> list[dict]:
        """CoC API 가 준 그대로의 항목 목록.

        가공하지 않은 값을 넘긴다. 우리 값으로 바꾸는 일은 서비스가 한다.
        """
        ...
```

- [ ] **4단계: 서비스를 쓴다**

`packages/core/src/coc_core/member/service.py`를 만든다.

```python
"""클랜원 서비스.

동기화와 조회를 나눈다. 동기화는 CoC API 에서 받아 우리 DB 에 맞추는 일이고,
조회는 담아 둔 것을 돌려주는 일이다.

동기화가 지켜야 할 것이 셋 있다.

- 한 사람 때문에 전체가 멈추지 않는다. 모르는 직책이 와도 그 사람만 UNKNOWN 이 된다
- 나간 사람을 지우지 않는다. status 를 INACTIVE 로 내려 과거 기록을 지킨다
- 무슨 일이 있었는지 남긴다. SyncResult 가 그 기록이다
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from coc_core.member.repository import MemberRepository, MemberSource


@dataclass(frozen=True)
class SyncResult:
    """동기화가 무엇을 했는지.

    unknown_roles 가 비어 있지 않으면 CoC 가 우리가 모르는 값을 보냈다는 뜻이다.
    조용히 넘어가면 UNKNOWN 이 쌓이는 것을 아무도 모른다.
    """

    total: int = 0
    added: int = 0
    left: int = 0
    unknown_roles: dict[str, int] = field(default_factory=dict)


class MemberService:
    def __init__(self, repository: MemberRepository, source: MemberSource | None = None) -> None:
        """source 는 동기화할 때만 쓴다.

        조회 경로는 CoC API 를 부를 일이 없으므로 넘기지 않는다. 요청마다
        HTTP 클라이언트를 새로 만드는 낭비를 피하기 위해서다.
        """
        self._repository = repository
        self._source = source

    async def sync(self, now: str) -> SyncResult:
        """CoC API 에서 받아 우리 DB 에 맞춘다."""
        if self._source is None:
            raise RuntimeError("동기화하려면 source 가 있어야 합니다")

        raw_members = await self._source.fetch_members()
        existing = {m.tag: m for m in await self._repository.find_all()}

        unknown_roles: dict[str, int] = {}
        members: list[ClanMember] = []

        for raw in raw_members:
            raw_role = raw.get("role", "")
            role = ClanRole.from_coc(raw_role)
            if role is ClanRole.UNKNOWN:
                unknown_roles[raw_role] = unknown_roles.get(raw_role, 0) + 1

            tag = raw["tag"]
            before = existing.get(tag)
            members.append(
                ClanMember(
                    id=before.id if before else str(uuid.uuid4()),
                    tag=tag,
                    name=raw["name"],
                    role=role,
                    status=MemberStatus.ACTIVE,
                    townhall=raw.get("townHallLevel"),
                    trophies=raw.get("trophies"),
                    donations=raw.get("donations"),
                    donations_received=raw.get("donationsReceived"),
                    description=before.description if before else None,
                    created_at=before.created_at if before else now,
                    updated_at=now,
                )
            )

        added = await self._repository.upsert_many(members)

        seen = {m.tag for m in members}
        gone = [
            tag
            for tag, m in existing.items()
            if tag not in seen and m.status is MemberStatus.ACTIVE
        ]
        left = await self._repository.mark_inactive(gone, now) if gone else 0

        return SyncResult(
            total=len(members),
            added=added,
            left=left,
            unknown_roles=unknown_roles,
        )

    async def find_all(self) -> list[ClanMember]:
        return await self._repository.find_all()

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        return await self._repository.find_by_tag(tag)
```

- [ ] **5단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest packages/core/tests/test_member_service.py -v
```

기대: 다섯 개 모두 통과.

- [ ] **6단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add packages/core/src/coc_core/member/ packages/core/tests/test_member_service.py
git commit -F - <<'MSG'
feat: 클랜원 저장소 약속과 서비스

- MemberRepository 는 Protocol 이라 구현체가 상속을 선언하지 않아도 된다.
  도메인은 저장소가 D1 인지 파일인지 모른다
- 동기화와 조회를 나눴다. 동기화는 SyncResult 로 무슨 일이 있었는지 남긴다
- 모르는 직책이 와도 그 사람만 UNKNOWN 이 되고 나머지는 저장된다.
  한 명 때문에 동기화가 통째로 멈추면 안 된다
- 목록에서 사라진 사람은 지우지 않고 INACTIVE 로 내린다.
  과거 기록이 이어지고 돌아온 사람의 설정이 살아 있다
- 가짜 대역은 클래스 하나면 된다. 모킹 라이브러리를 들이지 않는다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 5: CoC API 어댑터

**파일:**
- 생성: `apps/api/src/adapters/__init__.py`
- 생성: `apps/api/src/adapters/coc_api.py`
- 생성: `apps/api/tests/test_coc_api.py`

**인터페이스:**
- 쓰는 것: Task 4의 `MemberSource` 약속
- 만들어 내는 것: `CocApi(token, clan_tag, base_url=PROXY_BASE_URL)` — `fetch_members() -> list[dict]`, `aclose()`

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_coc_api.py`를 만든다.

```python
"""CoC API 어댑터.

httpx 의 MockTransport 로 응답을 흉내낸다. 실제 API 를 부르지 않는다.
"""

from __future__ import annotations

import httpx
import pytest

from adapters.coc_api import USER_AGENT, CocApi, CocApiError, encode_tag

CLAN_PAYLOAD = {
    "tag": "#2C8L822LQ",
    "name": "미니언즈",
    "memberList": [
        {
            "tag": "#A",
            "name": "도토리",
            "role": "admin",
            "townHallLevel": 16,
            "trophies": 4200,
            "donations": 100,
            "donationsReceived": 50,
        }
    ],
}


def _api(handler) -> CocApi:
    return CocApi(
        token="test-token",
        clan_tag="#2C8L822LQ",
        transport=httpx.MockTransport(handler),
    )


async def test_클랜원_목록을_그대로_돌려준다():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    members = await api.fetch_members()
    await api.aclose()

    assert len(members) == 1
    assert members[0]["role"] == "admin"  # 가공하지 않는다


async def test_태그를_인코딩해_부른다():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    await api.fetch_members()
    await api.aclose()

    assert seen == ["/v1/clans/%232C8L822LQ"]


async def test_프록시가_요구하는_헤더를_붙인다():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json=CLAN_PAYLOAD)

    api = _api(handler)
    await api.fetch_members()
    await api.aclose()

    assert seen["authorization"] == "Bearer test-token"
    assert seen["user-agent"] == USER_AGENT


async def test_실패하면_이유를_담아_올린다():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"reason": "accessDenied", "message": "잘못된 토큰"})

    api = _api(handler)
    with pytest.raises(CocApiError) as caught:
        await api.fetch_members()
    await api.aclose()

    assert caught.value.status == 403
    assert "accessDenied" in str(caught.value)


def test_태그_인코딩():
    assert encode_tag("#2ABC123") == "%232ABC123"
    assert encode_tag("2ABC123") == "%232ABC123"
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_coc_api.py -v
```

기대: `ModuleNotFoundError: No module named 'adapters'`.

- [ ] **3단계: 어댑터를 쓴다**

`apps/api/src/adapters/__init__.py`를 만든다.

```python
"""바깥과 만나는 자리.

도메인이 선언한 약속(coc_core.member.repository)을 여기서 구현한다.
CoC API 의 표기나 D1 의 SQL 이 도메인 안으로 새어 들어가지 않게 막는 층이다.
"""
```

`apps/api/src/adapters/coc_api.py`를 만든다.

```python
"""CoC 공식 API 어댑터.

RoyaleAPI 프록시를 거친다. 허용 IP 를 프록시가 대신 맞춰 주기 때문이며,
프록시는 User-Agent 없는 요청을 거절한다.

받은 값을 가공하지 않고 그대로 넘긴다. 우리 값으로 바꾸는 일은 도메인 서비스가
한다. 이 층은 "가져오는 일"만 맡는다.
"""

from __future__ import annotations

from typing import Any

import httpx

PROXY_BASE_URL = "https://cocproxy.royaleapi.dev/v1"
USER_AGENT = "coc-pointer (+https://github.com/circlebro/coc-pointer)"


class CocApiError(RuntimeError):
    """CoC API 가 200 이 아닌 답을 준 경우."""

    def __init__(self, status: int, path: str, reason: str, message: str) -> None:
        super().__init__(f"{status} {path}: {reason} {message}".strip())
        self.status = status
        self.path = path
        self.reason = reason


def encode_tag(tag: str) -> str:
    """플레이어·클랜 태그를 주소에 넣을 수 있게 바꾼다.

    '#' 은 주소에서 조각 구분자라 그대로 쓸 수 없다. 앞에 '#' 이 없으면 붙인다.
    """
    return "%23" + tag.lstrip("#")


class CocApi:
    """MemberSource 를 CoC 공식 API 로 구현한다."""

    def __init__(
        self,
        token: str,
        clan_tag: str,
        base_url: str = PROXY_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._clan_tag = clan_tag
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_members(self) -> list[dict[str, Any]]:
        """클랜원 목록. CoC 가 준 항목을 그대로 돌려준다."""
        clan = await self._get(f"/clans/{encode_tag(self._clan_tag)}")
        return list(clan.get("memberList", []))

    async def _get(self, path: str) -> dict[str, Any]:
        response = await self._client.get(path)
        if response.status_code != 200:
            body: dict[str, Any] = {}
            try:
                body = response.json()
            except ValueError:
                pass
            raise CocApiError(
                status=response.status_code,
                path=path,
                reason=str(body.get("reason", "")),
                message=str(body.get("message", "")),
            )
        return response.json()
```

- [ ] **4단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_coc_api.py -v
```

기대: 다섯 개 모두 통과.

**주의:** 기존 `apps/web/src/coc_pointer/api.py`는 동기 `httpx.Client`를 쓴다. Workers는 비동기만 되므로 이것은 새로 쓴 것이고, 기존 파일은 그대로 둔다. 기존 파이프라인이 여전히 그것을 쓴다.

- [ ] **5단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add apps/api/src/adapters/ apps/api/tests/test_coc_api.py
git commit -F - <<'MSG'
feat: CoC API 어댑터 (비동기)

- Workers 는 비동기 HTTP 만 쓸 수 있어 httpx.AsyncClient 로 새로 썼다.
  apps/web 의 동기 판은 기존 파이프라인이 쓰므로 그대로 둔다
- 받은 값을 가공하지 않고 그대로 넘긴다. 우리 값으로 바꾸는 일은
  도메인 서비스가 하고 이 층은 가져오는 일만 맡는다
- 프록시가 User-Agent 없는 요청을 거절하므로 헤더를 붙인다
- MockTransport 로 응답을 흉내내 실제 API 를 부르지 않는다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 6: D1 어댑터

**파일:**
- 생성: `apps/api/src/adapters/member_repository.py`
- 생성: `apps/api/tests/test_member_repository.py`

**인터페이스:**
- 쓰는 것: Task 4의 `MemberRepository` 약속, Task 2의 `clan_members` 표
- 만들어 내는 것: `D1MemberRepository(db)` — 약속의 네 메서드

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_member_repository.py`를 만든다.

```python
"""D1 클랜원 저장소.

가짜 D1 은 sqlite3 라서 실제 D1 과 같은 SQL 이 돈다. 여기서 검증한 질의는
배포된 D1 에서도 같은 결과를 낸다.
"""

from __future__ import annotations

from coc_core.member.models import ClanMember, ClanRole, MemberStatus

from adapters.member_repository import D1MemberRepository

NOW = "2026-09-10T05:30:00Z"
LATER = "2026-09-11T05:30:00Z"


def _member(tag: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{tag.lstrip('#')}",
        "tag": tag,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donations_received": 50,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


async def test_넣고_모두_읽는다(fake_db):
    repository = D1MemberRepository(fake_db)

    added = await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    assert added == 2
    rows = await repository.find_all()
    assert sorted(m.name for m in rows) == ["도토리", "히로"]


async def test_자료형이_그대로_돌아온다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", role=ClanRole.ADMIN)])

    found = await repository.find_by_tag("#A")

    assert found is not None
    assert found.role is ClanRole.ADMIN
    assert found.status is MemberStatus.ACTIVE
    assert found.townhall == 16


async def test_없는_태그는_None(fake_db):
    repository = D1MemberRepository(fake_db)

    assert await repository.find_by_tag("#없음") is None


async def test_다시_넣으면_갱신하고_새로_센_수는_0(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리")])

    added = await repository.upsert_many([_member("#A", "도토리2", updated_at=LATER)])

    assert added == 0
    found = await repository.find_by_tag("#A")
    assert found is not None
    assert found.name == "도토리2"
    assert found.updated_at == LATER


async def test_관리자_메모와_처음_본_시각은_지켜진다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", description="추방 예정")])

    await repository.upsert_many([_member("#A", "도토리", description=None, created_at=LATER)])

    found = await repository.find_by_tag("#A")
    assert found is not None
    assert found.description == "추방 예정"
    assert found.created_at == NOW


async def test_INACTIVE_로_내린다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리"), _member("#B", "히로")])

    count = await repository.mark_inactive(["#A"], LATER)

    assert count == 1
    by_tag = {m.tag: m for m in await repository.find_all()}
    assert by_tag["#A"].status is MemberStatus.INACTIVE
    assert by_tag["#A"].updated_at == LATER
    assert by_tag["#B"].status is MemberStatus.ACTIVE


async def test_모르는_직책도_담긴다(fake_db):
    repository = D1MemberRepository(fake_db)
    await repository.upsert_many([_member("#A", "도토리", role=ClanRole.UNKNOWN)])

    found = await repository.find_by_tag("#A")

    assert found is not None
    assert found.role is ClanRole.UNKNOWN
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_member_repository.py -v
```

기대: `ModuleNotFoundError: No module named 'adapters.member_repository'`.

- [ ] **3단계: 어댑터를 쓴다**

`apps/api/src/adapters/member_repository.py`를 만든다.

```python
"""클랜원 저장소를 D1 으로 구현한다.

SQL 문자열은 이 파일에만 둔다. 도메인은 SQL 을 모른다.

D1 은 SQLite 라서 표준 SQL 이 그대로 돈다. 다만 부르는 모양이 다르다.

    await db.prepare(SQL).bind(값).all()     # 여러 행. 결과는 .results
    await db.prepare(SQL).bind(값).first()   # 한 행. 없으면 None
    await db.prepare(SQL).bind(값).run()     # 쓰기
"""

from __future__ import annotations

from typing import Any

from coc_core.member.models import ClanMember, ClanRole, MemberStatus

_COLUMNS = (
    "id, tag, name, role, townhall, trophies, donations, donations_received, "
    "status, created_at, updated_at, description"
)

_FIND_ALL = f"SELECT {_COLUMNS} FROM clan_members ORDER BY name"

_FIND_BY_TAG = f"SELECT {_COLUMNS} FROM clan_members WHERE tag = ?"

_COUNT_BY_TAG = "SELECT COUNT(*) AS n FROM clan_members WHERE tag = ?"

# description 과 created_at 은 갱신하지 않는다. 관리자가 적은 메모가 동기화에
# 지워지면 안 되고, 처음 본 시각은 처음 한 번만 정해진다.
_UPSERT = """
INSERT INTO clan_members (
  id, tag, name, role, townhall, trophies, donations, donations_received,
  status, created_at, updated_at, description
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(tag) DO UPDATE SET
  name               = excluded.name,
  role               = excluded.role,
  townhall           = excluded.townhall,
  trophies           = excluded.trophies,
  donations          = excluded.donations,
  donations_received = excluded.donations_received,
  status             = excluded.status,
  updated_at         = excluded.updated_at
"""

_MARK_INACTIVE = "UPDATE clan_members SET status = 'INACTIVE', updated_at = ? WHERE tag = ?"


def _to_member(row: Any) -> ClanMember:
    return ClanMember(
        id=row.id,
        tag=row.tag,
        name=row.name,
        role=ClanRole(row.role),
        status=MemberStatus(row.status),
        townhall=row.townhall,
        trophies=row.trophies,
        donations=row.donations,
        donations_received=row.donations_received,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class D1MemberRepository:
    """MemberRepository 를 D1 으로 구현한다."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def find_all(self) -> list[ClanMember]:
        result = await self._db.prepare(_FIND_ALL).all()
        return [_to_member(row) for row in result.results]

    async def find_by_tag(self, tag: str) -> ClanMember | None:
        row = await self._db.prepare(_FIND_BY_TAG).bind(tag).first()
        return _to_member(row) if row is not None else None

    async def upsert_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            existing = await self._db.prepare(_COUNT_BY_TAG).bind(m.tag).first()
            if existing is None or existing.n == 0:
                added += 1
            await (
                self._db.prepare(_UPSERT)
                .bind(
                    m.id,
                    m.tag,
                    m.name,
                    str(m.role),
                    m.townhall,
                    m.trophies,
                    m.donations,
                    m.donations_received,
                    str(m.status),
                    m.created_at,
                    m.updated_at,
                    m.description,
                )
                .run()
            )
        return added

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        for tag in tags:
            await self._db.prepare(_MARK_INACTIVE).bind(now, tag).run()
        return len(tags)
```

- [ ] **4단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_member_repository.py -v
```

기대: 일곱 개 모두 통과.

- [ ] **5단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add apps/api/src/adapters/member_repository.py apps/api/tests/test_member_repository.py
git commit -F - <<'MSG'
feat: 클랜원 저장소를 D1 으로 구현

- SQL 문자열을 이 파일에만 둔다. 도메인은 SQL 을 모른다
- ON CONFLICT 에서 description 과 created_at 을 빼 관리자 메모와
  처음 본 시각이 동기화에 지워지지 않게 한다
- 가짜 D1 이 sqlite3 라 실제 D1 과 같은 SQL 이 돈다.
  여기서 검증한 질의는 배포된 D1 에서도 같은 결과를 낸다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 7: 조회 경로

**파일:**
- 생성: `apps/api/src/routes/__init__.py`
- 생성: `apps/api/src/routes/member.py`
- 수정: `apps/api/src/worker.py`
- 생성: `apps/api/tests/test_route_member.py`
- 수정: `apps/api/tests/test_worker.py`

**인터페이스:**
- 쓰는 것: Task 4의 `MemberService`, Task 6의 `D1MemberRepository`, Task 1의 생성 모델
- 만들어 내는 것: `GET /api/v1/members`. 기존 `/api/scores/{월}`, `/api/draws/{월}`이 `/api/v1/` 아래로 옮겨진다

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_route_member.py`를 만든다.

```python
"""클랜원 조회 경로."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from adapters.member_repository import D1MemberRepository
from coc_core.member.models import ClanMember, ClanRole, MemberStatus
from worker import app

NOW = "2026-09-10T05:30:00Z"


class FakeEnv:
    API_VERSION = "0.5.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"

    def __init__(self, db) -> None:
        self.DB = db


def _member(tag: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{tag.lstrip('#')}",
        "tag": tag,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donations_received": 50,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


@pytest.fixture
def client(fake_db):
    """실제 Workers 처럼 scope 에 env 를 넣어 주는 얇은 래퍼로 앱을 감싼다."""
    env = FakeEnv(fake_db)

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    return TestClient(with_env)


def _seed(fake_db, members):
    asyncio.run(D1MemberRepository(fake_db).upsert_many(members))


def test_아무도_없으면_빈_목록(client):
    body = client.get("/api/v1/members").json()

    assert body == {"members": []}


def test_이름_순으로_돌려준다(client, fake_db):
    _seed(fake_db, [_member("#B", "히로"), _member("#A", "도토리")])

    body = client.get("/api/v1/members").json()

    assert [m["name"] for m in body["members"]] == ["도토리", "히로"]


def test_계약대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", role=ClanRole.ADMIN)])

    member = client.get("/api/v1/members").json()["members"][0]

    assert member["tag"] == "#A"
    assert member["role"] == "ADMIN"
    assert member["status"] == "ACTIVE"
    assert member["donationsReceived"] == 50
    assert member["createdAt"] == NOW
    assert "donations_received" not in member


def test_태그로_좁힌다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    body = client.get("/api/v1/members", params={"tag": "#B"}).json()

    assert [m["name"] for m in body["members"]] == ["히로"]


def test_없는_태그면_빈_목록(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.get("/api/v1/members", params={"tag": "#없음"}).json()

    assert body == {"members": []}
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_route_member.py -v
```

기대: 404 또는 import 실패.

- [ ] **3단계: 경로를 쓴다**

`apps/api/src/routes/__init__.py`를 만든다.

```python
"""HTTP 경로.

들어오는 요청을 도메인 서비스로 넘기고 응답 모양을 계약에 맞춘다.
계산이나 판단은 여기서 하지 않는다.
"""
```

`apps/api/src/routes/member.py`를 만든다.

```python
"""클랜원 조회 경로.

응답 모양은 contracts/openapi.yaml 이 정한다. 여기서는 도메인 자료형을
그 모양으로 옮기기만 한다.
"""

from __future__ import annotations

from typing import Annotated, Any

from coc_core.member.models import ClanMember
from coc_core.member.service import MemberService
from fastapi import APIRouter, Depends, Query, Request

from adapters.member_repository import D1MemberRepository

router = APIRouter(prefix="/api/v1", tags=["members"])


def get_member_service(request: Request) -> MemberService:
    """요청마다 조립한다. 스프링 컨테이너가 하던 일을 여기서 직접 한다.

    조회만 하므로 source 를 넘기지 않는다. 동기화는 cli.py 가 따로 조립한다.
    """
    env = request.scope["env"]
    return MemberService(repository=D1MemberRepository(env.DB))


MemberSvc = Annotated[MemberService, Depends(get_member_service)]


def _to_response(member: ClanMember) -> dict[str, Any]:
    """도메인 자료형을 계약이 정한 모양으로. 키는 캐멀케이스다."""
    return {
        "id": member.id,
        "tag": member.tag,
        "name": member.name,
        "role": str(member.role),
        "status": str(member.status),
        "townhall": member.townhall,
        "trophies": member.trophies,
        "donations": member.donations,
        "donationsReceived": member.donations_received,
        "description": member.description,
        "createdAt": member.created_at,
        "updatedAt": member.updated_at,
    }


@router.get("/members")
async def list_members(
    service: MemberSvc,
    tag: Annotated[str | None, Query(description="플레이어 태그로 좁힌다")] = None,
) -> dict[str, Any]:
    """클랜원 목록. 나간 사람(INACTIVE)도 포함한다."""
    if tag is not None:
        found = await service.find_by_tag(tag)
        return {"members": [_to_response(found)] if found else []}
    return {"members": [_to_response(m) for m in await service.find_all()]}
```

- [ ] **4단계: 앱에 붙이고 기존 경로를 v1 아래로 옮긴다**

`apps/api/src/worker.py`에서 다음을 한다.

앱을 만든 뒤(미들웨어 설정 아래)에 라우터를 붙인다.

```python
from routes.member import router as member_router

app.include_router(member_router)
```

기존 두 경로의 데코레이터를 고친다.

```python
@app.get("/api/v1/scores/{month}")
```

```python
@app.get("/api/v1/draws/{month}")
```

`/api/health`와 `/api/health/crypto`는 그대로 둔다.

- [ ] **5단계: 기존 테스트의 경로를 고친다**

`apps/api/tests/test_worker.py`에서 `/api/scores/`와 `/api/draws/`를 `/api/v1/scores/`와 `/api/v1/draws/`로 바꾼다. `/api/health`는 그대로 둔다.

- [ ] **6단계: 테스트가 통과하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/ -v
```

기대: 클랜원 경로 다섯 개와 기존 테스트 모두 통과.

- [ ] **7단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add apps/api/src/routes/ apps/api/src/worker.py apps/api/tests/
git commit -F - <<'MSG'
feat: 클랜원 조회 경로와 v1 이관

- GET /api/v1/members. 태그로 좁힐 수 있다
- 기존 scores·draws 도 /api/v1/ 아래로 옮겼다. 부르는 곳이 없어 지금이 가장 싸다
- /api/health 는 버전을 두지 않는다. 배포가 되었는지 보는 자리라
  버전이 바뀌어도 같은 곳에 있는 편이 낫다
- 응답 키는 캐멀케이스. 계약이 정한 모양이고 자바스크립트가 소비한다
- 서비스 조립을 Depends 로 한 곳에 모아 테스트에서 가짜를 넣기 쉽게 했다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 8: 동기화 명령

**파일:**
- 생성: `apps/api/src/cli.py`
- 수정: `apps/api/pyproject.toml`
- 생성: `apps/api/tests/test_cli.py`

**인터페이스:**
- 쓰는 것: Task 4의 `MemberService`, Task 5의 `CocApi`, Task 6의 `D1MemberRepository`
- 만들어 내는 것: `refresh_members(db, token, clan_tag, now) -> SyncResult`와 `main()` 진입점

- [ ] **1단계: 실패하는 테스트를 쓴다**

`apps/api/tests/test_cli.py`를 만든다.

```python
"""동기화 명령.

D1 과 CoC API 를 가짜로 넣어 조립과 보고를 확인한다.
"""

from __future__ import annotations

import httpx

from cli import refresh_members

NOW = "2026-09-10T05:30:00Z"

CLAN_PAYLOAD = {
    "tag": "#2C8L822LQ",
    "name": "미니언즈",
    "memberList": [
        {
            "tag": "#A",
            "name": "도토리",
            "role": "admin",
            "townHallLevel": 16,
            "trophies": 4200,
            "donations": 100,
            "donationsReceived": 50,
        },
        {
            "tag": "#B",
            "name": "히로",
            "role": "veteran",
            "townHallLevel": 15,
            "trophies": 3800,
            "donations": 80,
            "donationsReceived": 40,
        },
    ],
}


def _transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CLAN_PAYLOAD)

    return httpx.MockTransport(handler)


async def test_동기화_결과를_돌려준다(fake_db):
    result = await refresh_members(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    assert result.total == 2
    assert result.added == 2
    assert result.unknown_roles == {"veteran": 1}


async def test_실제로_저장된다(fake_db):
    await refresh_members(
        db=fake_db,
        token="test-token",
        clan_tag="#2C8L822LQ",
        now=NOW,
        transport=_transport(),
    )

    rows = await fake_db.prepare("SELECT tag, name, role FROM clan_members ORDER BY tag").all()

    assert [(r.tag, r.name, r.role) for r in rows.results] == [
        ("#A", "도토리", "ADMIN"),
        ("#B", "히로", "UNKNOWN"),
    ]
```

- [ ] **2단계: 테스트가 실패하는 것을 확인한다**

```bash
uv run pytest apps/api/tests/test_cli.py -v
```

기대: `ModuleNotFoundError: No module named 'cli'`.

- [ ] **3단계: 명령을 쓴다**

`apps/api/src/cli.py`를 만든다.

```python
"""명령줄에서 도는 일.

지금은 클랜원 동기화 하나뿐이다. 예약 실행(Cron)은 클랜전 수집을 옮길 때
함께 붙인다.

    uv run coc-api refresh-members

서버가 요청을 받아 조립하는 것과 같은 일을 여기서 한다. 조립하는 자리가
두 곳이 되지 않게 이 파일이 그 몫을 맡는다.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

import httpx
from coc_core.member.service import MemberService, SyncResult

from adapters.member_repository import D1MemberRepository


async def refresh_members(
    db: Any,
    token: str,
    clan_tag: str,
    now: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SyncResult:
    """CoC API 에서 클랜원을 받아 D1 에 맞춘다."""
    coc_api = CocApi(token=token, clan_tag=clan_tag, transport=transport)
    try:
        service = MemberService(
            repository=D1MemberRepository(db),
            source=coc_api,
        )
        return await service.sync(now=now)
    finally:
        await coc_api.aclose()


def _now() -> str:
    """지금 시각. D1 연결이 정해지면 main 이 refresh_members 에 넘긴다."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    """진입점.

    D1 에 붙는 방법은 아직 정하지 않았다. 로컬에서는 wrangler 를 거치고
    Workers 안에서는 바인딩을 쓴다. 지금은 안내만 하고 빠진다.
    """
    if len(sys.argv) < 2 or sys.argv[1] != "refresh-members":
        print("쓰임: coc-api refresh-members")
        return 2

    token = os.environ.get("COC_API_TOKEN")
    if not token:
        print("COC_API_TOKEN 이 없습니다. 저장소 루트 .env 에 넣어 주세요.")
        return 1

    print("이 명령은 D1 연결이 필요합니다.")
    print("로컬 D1 로 시험하려면:")
    print("  cd apps/api && uv run pywrangler dev")
    print("배포된 D1 에 넣으려면 Cron 이 붙은 뒤에 서버가 스스로 합니다 (TASK-21).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **4단계: 진입점을 등록한다**

`apps/api/pyproject.toml`의 `[project]` 절 아래에 더한다.

```toml
[project.scripts]
coc-api = "cli:main"
```

- [ ] **5단계: 테스트가 통과하는 것을 확인한다**

```bash
uv sync
uv run pytest apps/api/tests/test_cli.py -v
```

기대: 둘 다 통과.

- [ ] **6단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
git add apps/api/src/cli.py apps/api/pyproject.toml apps/api/tests/test_cli.py uv.lock
git commit -F - <<'MSG'
feat: 클랜원 동기화 명령

- refresh_members 가 CoC API 에서 받아 D1 에 맞춘다.
  서버가 요청을 받아 조립하는 것과 같은 일이라 조립 자리를 한곳에 모았다
- D1 연결 방법은 아직 정하지 않았다. 로컬은 wrangler 를 거치고
  배포 뒤에는 Cron 이 붙어 서버가 스스로 한다(TASK-21)
- 가짜 D1 과 가짜 CoC API 로 조립과 보고를 검증한다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 9: React 앱과 클랜원 화면

**파일:**
- 생성: `apps/web/package.json`
- 생성: `apps/web/vite.config.ts`
- 생성: `apps/web/tsconfig.json`
- 생성: `apps/web/index.html`
- 생성: `apps/web/src/main.tsx`
- 생성: `apps/web/src/pages/Members.tsx`
- 생성: `apps/web/src/api/client.ts`
- 생성: `apps/web/src/labels.ts`
- 수정: `.gitignore`

**인터페이스:**
- 쓰는 것: Task 1이 만든 `apps/web/src/api/schema.d.ts`, Task 7의 `GET /api/v1/members`
- 만들어 내는 것: `npm run build`가 `apps/web/dist/`에 정적 파일을 낸다

- [ ] **1단계: 프로젝트 설정을 만든다**

`apps/web/package.json`을 만든다.

```json
{
  "name": "coc-pointer-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.7.0",
    "vite": "^6.0.0"
  }
}
```

`apps/web/vite.config.ts`를 만든다.

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// GitHub Pages 의 /coc-pointer/members/ 아래에 놓인다. base 를 맞추지 않으면
// 자바스크립트와 CSS 주소가 어긋나 화면이 빈 채로 뜬다.
export default defineConfig({
  plugins: [react()],
  base: "/coc-pointer/members/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
```

`apps/web/tsconfig.json`을 만든다.

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noEmit": true
  },
  "include": ["src"]
}
```

`apps/web/index.html`을 만든다.

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>클랜원 — 미니언즈</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **2단계: `.gitignore`에 더한다**

```
apps/web/node_modules/
apps/web/dist/
```

- [ ] **3단계: API 호출을 감싼다**

`apps/web/src/api/client.ts`를 만든다.

```typescript
import type { components } from "./schema";

export type Member = components["schemas"]["Member"];
export type MemberListResponse = components["schemas"]["MemberListResponse"];

const BASE_URL = "https://coc-api.coc-api.workers.dev";

export async function fetchMembers(): Promise<MemberListResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/members`);
  if (!response.ok) {
    throw new Error(`서버가 ${response.status} 로 답했습니다`);
  }
  return response.json();
}
```

- [ ] **4단계: 표시 문구를 모은다**

`apps/web/src/labels.ts`를 만든다.

```typescript
import type { components } from "./api/schema";

type ClanRole = components["schemas"]["ClanRole"];
type MemberStatus = components["schemas"]["MemberStatus"];

// Record 로 적어 두면 서버가 값을 늘렸을 때 여기 빠진 것이 빌드에서 걸린다.
// 그것이 없으면 화면에 "VETERAN" 같은 코드가 그대로 나와 버그처럼 보인다.
const ROLE_LABEL: Record<ClanRole, string> = {
  LEADER: "대표",
  COLEADER: "공동 대표",
  ADMIN: "장로",
  MEMBER: "멤버",
  UNKNOWN: "알 수 없음",
};

const STATUS_LABEL: Record<MemberStatus, string> = {
  ACTIVE: "재적",
  INACTIVE: "탈퇴",
};

// 타입이 잡지 못하는 경우가 있다. 서버가 프론트보다 먼저 배포된 순간이 그렇다.
export const roleLabel = (role: string): string =>
  ROLE_LABEL[role as ClanRole] ?? "알 수 없음";

export const statusLabel = (status: string): string =>
  STATUS_LABEL[status as MemberStatus] ?? "알 수 없음";
```

- [ ] **5단계: 화면을 만든다**

`apps/web/src/pages/Members.tsx`를 만든다.

```tsx
import { useEffect, useState } from "react";
import { fetchMembers, type Member } from "../api/client";
import { roleLabel, statusLabel } from "../labels";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; members: Member[] };

export function Members() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = () => {
    setState({ kind: "loading" });
    fetchMembers()
      .then((body) => setState({ kind: "ready", members: body.members }))
      .catch((error: Error) => setState({ kind: "error", message: error.message }));
  };

  useEffect(load, []);

  if (state.kind === "loading") {
    return <p>불러오는 중입니다.</p>;
  }

  // 실패와 빈 목록을 갈라 보여준다. 같아 보이면 원인을 찾을 수 없다.
  if (state.kind === "error") {
    return (
      <div>
        <p>클랜원을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>
        <p>{state.message}</p>
        <button onClick={load}>다시 시도</button>
      </div>
    );
  }

  if (state.members.length === 0) {
    return <p>클랜원 자료가 아직 없습니다.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>닉네임</th>
          <th>태그</th>
          <th>직책</th>
          <th>상태</th>
          <th>홀</th>
          <th>트로피</th>
          <th>기부</th>
        </tr>
      </thead>
      <tbody>
        {state.members.map((member) => (
          <tr key={member.id}>
            <td>{member.name}</td>
            <td>{member.tag}</td>
            <td>{roleLabel(member.role)}</td>
            <td>{statusLabel(member.status)}</td>
            <td>{member.townhall ?? "-"}</td>
            <td>{member.trophies ?? "-"}</td>
            <td>{member.donations ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`apps/web/src/main.tsx`를 만든다.

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Members } from "./pages/Members";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("#root 를 찾지 못했습니다");
}

createRoot(root).render(
  <StrictMode>
    <h1>클랜원</h1>
    <Members />
  </StrictMode>,
);
```

- [ ] **6단계: 빌드가 도는지 확인한다**

```bash
cd apps/web && npm install && npm run build
```

기대: `apps/web/dist/`에 `index.html`과 `assets/`가 생긴다. 타입 오류가 없어야 한다.

빌드가 `schema.d.ts`를 찾지 못하면 Task 1의 생성 스크립트를 다시 돌린다.

- [ ] **7단계: 화면을 눈으로 본다**

```bash
cd apps/web && npm run dev
```

브라우저에서 열어 본다. **서버가 아직 배포되지 않았으므로 "불러오지 못했습니다"가 뜨는 것이 맞다.** 그 화면이 제대로 나오는지, 다시 시도 버튼이 있는지 확인한다.

확인한 뒤 `Ctrl+C`로 멈춘다.

- [ ] **8단계: 커밋한다**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/vite.config.ts apps/web/tsconfig.json apps/web/index.html apps/web/src/ .gitignore
git commit -F - <<'MSG'
feat: React 클랜원 화면

- Vite + React + TypeScript. 서버가 이미 Cloudflare 에 따로 있어
  메타 프레임워크를 쓰지 않는다
- 표시 문구를 Record 로 적어 서버가 값을 늘렸을 때 빌드에서 걸리게 했다.
  그것이 없으면 화면에 코드가 그대로 나와 버그처럼 보인다
- 폴백도 남긴다. 서버가 프론트보다 먼저 배포된 순간은 타입이 잡지 못한다
- 불러오는 중·실패·빈 목록 셋을 갈라 보여준다.
  실패와 빈 목록이 같아 보이면 원인을 찾을 수 없다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

### Task 10: 두 빌드를 합쳐 배포

**파일:**
- 수정: `.github/workflows/collect.yml`
- 수정: `CLAUDE.md`

**인터페이스:**
- 쓰는 것: Task 9의 `apps/web/dist/`
- 만들어 내는 것: `site/members/`에 React 결과가 놓인 배포

- [ ] **1단계: 지금 워크플로를 읽는다**

```bash
cat .github/workflows/collect.yml
```

파이썬으로 `site/`를 만들고 GitHub Pages에 올리는 단계가 있을 것이다. 그 사이에 React 빌드를 끼워 넣는다.

- [ ] **2단계: React 빌드 단계를 더한다**

`uv run coc-pointer build` 단계 **다음**, 배포 단계 **앞**에 넣는다.

```yaml
      - name: Node 준비
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json

      - name: 클랜원 화면 빌드
        working-directory: apps/web
        run: |
          npm ci
          npm run build

      - name: 빌드 결과를 site/members/ 로
        run: |
          rm -rf site/members
          mkdir -p site/members
          cp -R apps/web/dist/. site/members/
```

**`rm -rf site/members`가 필요하다.** 파이썬 빌드가 만든 옛 `members/index.html`을 지우지 않으면 새 화면이 덮이지 않는다.

- [ ] **3단계: 파이썬이 클랜원 페이지를 만들지 않게 한다**

`apps/web/src/coc_pointer/render.py`에서 `members/` 페이지를 만드는 부분을 찾는다.

```bash
grep -n 'members' apps/web/src/coc_pointer/render.py
```

그 페이지를 만드는 호출을 지운다. 두 빌드가 같은 자리를 다투지 않게 한다. 템플릿 `members.html`도 함께 지운다.

관련 테스트가 있으면 함께 고친다.

```bash
grep -rn 'members' apps/web/tests/
```

- [ ] **4단계: 로컬에서 합쳐 본다**

```bash
uv run coc-pointer build
cd apps/web && npm run build && cd ../..
rm -rf site/members && mkdir -p site/members && cp -R apps/web/dist/. site/members/
ls site/ site/members/
```

기대: `site/index.html`과 `site/2026-09/`는 파이썬이 만든 것, `site/members/index.html`은 React 것.

- [ ] **5단계: `CLAUDE.md`를 고친다**

`Layout` 절의 `apps/web` 설명을 바꾼다.

```
- `apps/web/`: two builds land here for now. `src/coc_pointer/` still renders the legacy
  pages with Jinja2; `src/` (TypeScript) is the React app that replaces them one page at a
  time. `/members/` is React already. The workflow runs both and merges the output into
  `site/`.
```

`Data flow` 절에도 한 줄을 더한다.

```
- `/members/` is served by the React app, which calls `GET /api/v1/members`. The other
  pages are still built by `coc-pointer build`. Both outputs are merged in the workflow.
```

- [ ] **6단계: 전체 검사와 커밋**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
```

```bash
git add .github/workflows/collect.yml CLAUDE.md apps/web/src/coc_pointer/render.py apps/web/src/coc_pointer/templates/ apps/web/tests/
git commit -F - <<'MSG'
feat: 파이썬 빌드와 React 빌드를 합쳐 배포

- 워크플로가 둘을 차례로 돌려 site/ 에 합친다.
  /members/ 만 React 이고 나머지는 아직 Jinja2 다
- 파이썬 쪽 members 페이지 생성을 지웠다. 두 빌드가 같은 자리를 다투면
  어느 쪽이 남는지 알 수 없다
- 옛 members/ 를 지우고 복사한다. 지우지 않으면 새 화면이 덮이지 않는다

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01SEjU63ioVTGGo4ZeJ2B4wU
MSG
```

---

## 이 계획이 끝나면

클랜원 조회가 CoC API에서 React 화면까지 관통한다. 나머지 화면(점수표, 클랜전 기록, 리그전)은 같은 길을 따라 하나씩 옮기면 된다.

**배포는 두 가지를 기다린다.**

1. Cloudflare 계정에 Workers가 열려야 한다 (`code: 10034`)
2. D1에 클랜원 자료가 들어가야 한다. 지금은 명령이 안내만 하고 빠지므로, 실제로 채우는 방법은 Cron을 붙일 때(TASK-21) 정한다

**Task 1~9는 배포 없이 로컬에서 확인할 수 있다.** Task 10만 실제 배포가 필요하다.

이 계획에서 하지 않는 것은 설계 문서 2절에 적혀 있다.
