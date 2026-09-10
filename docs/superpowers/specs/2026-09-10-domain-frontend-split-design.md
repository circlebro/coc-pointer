# 도메인과 화면을 가르는 설계 — 클랜원 조회

작성일: 2026-09-10
상태: 검토 대기
앞선 문서: `2026-09-10-backend-server-design.md` — **이 문서가 그것의 3절(전체 구조)을 대체한다.** 그 문서의 D1 표 구조와 Python Workers 제약은 그대로 유효하다.

## 1. 목적

**백엔드가 무엇이 참인지 말하고, 프론트가 그것을 어떻게 보일지 정한다.**

지금은 프론트가 둘 다 한다. `apps/web/src/coc_pointer/render.py`가 점수를 계산하고 선발 명단을 뽑은 뒤 HTML을 만든다. 규칙이 바뀌면 화면을 다시 배포해야 하고, 서버도 같은 계산을 하게 되면 규칙이 두 곳에 생긴다.

경계를 이렇게 긋는다.

| | 백엔드 | 프론트 |
|---|---|---|
| 클랜원 직책 | `"role": "ADMIN"` | "장로"로 표시 |
| 상태 | `"status": "INACTIVE"` | 회색 배지 |
| 점수 | `"score": 87.5` | "87.5점" 또는 막대 길이 |
| 시각 | `"2026-09-05T14:30:00Z"` | "9월 5일 23시" |

왼쪽은 사실이고 오른쪽은 표현이다. 규칙이 바뀌면 왼쪽만, 문구를 바꾸려면 오른쪽만 고친다.

`render.py`의 `ROLE_KO`(직책을 한국어로 바꾸는 표)는 프론트가 할 일이 맞다. 같은 파일의 `from coc_core.scoring import rank_month, roster, split_rewards`가 걷어낼 부분이다.

## 2. 범위

**클랜원 하나만 처음부터 끝까지 관통한다.** 가장 단순하면서 전 구간을 지나므로, 이 길이 뚫리면 나머지 화면은 같은 길을 따라간다.

```
CoC API → MemberService → MemberRepository → D1 → GET /api/v1/members → React
```

### 이번에 하는 것

- `clan_members` 표와 마이그레이션 체계
- `coc_core/member/` — 자료형, 인터페이스, 서비스
- CoC API 어댑터와 D1 어댑터
- `GET /api/v1/members`
- React 클랜원 목록 화면
- API 계약(`contracts/openapi.yaml`)과 거기서 나오는 서버 모델·프론트 타입

### 이번에 하지 않는 것

- 클랜전·점수·추첨 (`wars`, `war_members`, `attacks`, `monthly_scores`, `draws`) — 표는 이미 있으나 손대지 않는다
- 기존 화면(`/`, `/2026-09/`) — 지금 방식으로 계속 돈다
- 로그인과 사용자 관리 (TASK-23)
- 예약 실행으로 수집 (TASK-21)
- 클랜원 관리 화면 (TASK-22)
- `packages/core`를 `domain`과 `application`으로 나누기 — 605줄에는 이르다
- 화면 개선 — 보이는 모습은 지금과 같게 둔다

**아직 클랜에 공개하지 않았으므로 중간에 사이트가 어긋나도 된다.** 옛 경로와 새 경로를 함께 살리는 장치를 만들지 않는다.

## 3. API 계약이 먼저다

`contracts/openapi.yaml`을 손으로 쓰고, 거기서 양쪽이 나온다.

```
contracts/openapi.yaml          ← 계약. 이것이 기준이다
    ├──→ apps/api/src/schemas/       Pydantic 모델   (자동 생성)
    └──→ apps/web/src/api/schema.d.ts TypeScript 타입 (자동 생성)
```

**명세는 하나여야 한다.** 서버용과 프론트용으로 나누면 무엇이 진짜인지 알 수 없게 되고, 계약이 계약이 아니게 된다.

`contracts/`를 루트에 두는 이유는 어느 한쪽 것이 아니기 때문이다. `packages/`가 "두 앱이 함께 쓰는 코드"인 것처럼 `contracts/`는 "두 앱이 함께 지키는 약속"이다.

### 3.1 생성 명령

```bash
# 서버 모델
uv run datamodel-codegen \
  --input contracts/openapi.yaml \
  --output apps/api/src/schemas/ \
  --output-model-type pydantic_v2.BaseModel

# 프론트 타입
npx openapi-typescript contracts/openapi.yaml -o apps/web/src/api/schema.d.ts
```

**생성물은 손으로 고치지 않는다.** 고치고 싶으면 명세를 고치고 다시 생성한다. 파일 맨 위에 그 규칙을 주석으로 남긴다.

생성물은 git에 커밋한다. 명세를 고쳤을 때 무엇이 따라 바뀌었는지 PR에서 보이고, 새로 받은 저장소가 생성 없이도 빌드된다.

### 3.2 무엇이 좋아지나

계약이 먼저 굳으면 **서버가 없어도 프론트가 작업할 수 있다.** 그리고 서버에서 값을 하나 늘리면 프론트 빌드가 깨져 그 값을 다루게 만든다.

```
서버 enum 에 VETERAN 을 더한다
   ↓ 명세가 바뀐다
ClanRole: "LEADER" | ... | "VETERAN"
   ↓ 프론트의 Record<ClanRole, string> 에 VETERAN 이 없다
빌드가 깨진다 → 번역을 넣어야 배포된다
```

이것이 없으면 화면에 `VETERAN`이 그대로 노출된다. 한국어 화면에 영어 대문자가 섞여 나오면 **누가 봐도 버그로 보이는데 서버도 프론트도 오류를 내지 않는다.** 다국어를 붙이면 영어 사용자에게는 그럴듯해 보여 아무도 알아차리지 못한다.

## 4. 경로

```
/api/health              버전 없음. 배포 상태 확인
/api/v1/members          목록
/api/v1/members/{id}     단건
/api/v1/members?tag=...  태그로 찾기
```

**버전을 넣는다.** 우리 프론트만 쓰더라도 브라우저에 옛 자바스크립트가 캐시되어 남으므로 남이 쓰는 것과 다르지 않다. 이 저장소는 옛 `style.css`가 캐시되어 모바일 화면이 깨진 적이 있다. 넣는 비용은 경로 한 마디이고, 나중에 넣으려면 프론트의 모든 호출을 고쳐야 한다.

`/api/health`만 버전을 두지 않는다. 배포가 되었는지 보는 자리라 버전이 바뀌어도 같은 곳에 있는 편이 낫다.

기존 `/api/scores/{월}`, `/api/draws/{월}`도 `/api/v1/` 아래로 옮긴다. 부르는 곳이 없어 지금이 가장 싸다.

### 4.1 주소는 프론트와 다르다

```
프론트 (사용자가 접속)
  https://circlebro.github.io/coc-pointer/members/

백엔드 (프론트가 부른다)
  https://coc-api.coc-api.workers.dev/api/v1/members
```

호스팅이 다르므로 CORS 설정이 필요하다. 이미 넣어 두었다.

경로 모양도 다르다. 프론트는 화면 구조를 따르고(`admin/members`), 백엔드는 자원을 따른다(`members`). 프론트에 관리자 화면이 있다고 백엔드에 `admin` 경로가 필요하지 않다. **같은 자원이고 권한만 다르다.**

## 5. 데이터

### 5.1 표

```sql
CREATE TABLE clan_members (
  id                 TEXT PRIMARY KEY,          -- UUID4
  tag                TEXT NOT NULL UNIQUE,      -- CoC 플레이어 태그. 바뀌지 않는다
  name               TEXT NOT NULL,

  -- CoC API 가 채운다
  role               TEXT NOT NULL,             -- LEADER | COLEADER | ADMIN | MEMBER | UNKNOWN
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,

  -- 우리가 판정한다
  status             TEXT NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE | INACTIVE
  created_at         TEXT NOT NULL,             -- 2026-09-10T05:30:00Z
  updated_at         TEXT NOT NULL,

  -- 관리자가 적는다
  description        TEXT
);

CREATE INDEX idx_clan_members_status ON clan_members(status);
```

**`id`와 `tag`의 역할이 다르다.** `id`는 우리 API가 자원을 가리키는 이름이고, `tag`는 CoC 세계의 식별자다. `id`를 두면 주소에서 `#`을 인코딩하지 않아도 된다.

```
/api/v1/members/%232ABC123      → /api/v1/members/{uuid}
```

`uuid4`를 쓴다. `uuid7`은 파이썬 3.14에서 추가되었고 Workers의 3.13에는 없다. 시간순 정렬이 필요하면 `created_at`으로 한다.

**앞으로 표끼리 클랜원을 가리킬 때는 `id`를 쓴다.** 클랜원이 중심이 되고 나머지가 그것을 참조한다. 다만 이번 범위에서는 클랜원 표 하나뿐이라 그 결정이 드러나지 않는다.

### 5.2 시각

SQLite에는 날짜 타입이 없다. `timestamptz`에 해당하는 것이 없으므로 **TEXT에 ISO 8601 문자열**을 담는다.

```
2026-09-10T05:30:00Z
```

끝의 `Z`가 시간대다. 이 형식은 **사전순 정렬이 곧 시간순**이라 범위 검색이 그대로 된다.

```sql
WHERE created_at >= '2026-09-01T00:00:00Z'
  AND created_at <  '2026-10-01T00:00:00Z'
```

인덱스도 탄다. 다만 두 가지를 지켜야 성립한다.

| 지킬 것 | 어기면 |
|---|---|
| 자릿수 고정 (`2026-09-05`, `2026-9-5` 아님) | `2026-9-5`가 `2026-10-01`보다 크게 정렬된다 |
| 시간대 하나로 통일 (전부 UTC `Z`) | `+09:00`과 `Z`가 섞이면 순서가 어긋난다 |

`models.py`의 `to_iso()`가 항상 `%Y-%m-%dT%H:%M:%SZ`로 만든다. 다른 경로로 시각을 넣지 않는다.

컬럼에 함수를 씌우면 인덱스를 버리므로 `strftime('%Y-%m', created_at) = '2026-09'` 같은 질의는 쓰지 않는다.

### 5.3 마이그레이션

```
apps/api/database/
  schema.sql              현재 전체 구조. 자동 생성물
  migrations/
    0001_init.sql         변경 이력. 손으로 쓴다
```

`wrangler.toml`에 경로를 알린다.

```toml
migrations_dir = "database/migrations"
```

적용은 이렇게 한다.

```bash
wrangler d1 migrations apply coc-pointer --remote
```

**D1이 어디까지 적용했는지 스스로 기록한다.** `d1_migrations` 표가 자동으로 생기고 이미 적용한 파일은 건너뛴다. Flyway의 `flyway_schema_history`와 같은 자리다.

`schema.sql`은 손으로 쓰지 않는다. 마이그레이션을 적용한 결과에서 뽑는다. 두 벌이 어긋나는 것이 이 방식의 유일한 위험이므로, **둘이 일치하는지 확인하는 테스트를 둔다.** 가짜 D1이 이미 `sqlite3` 위에서 도니 그 위에서 검증한다.

첫 마이그레이션에서 앞선 설계의 `members` 표를 지우고 `clan_members`를 만든다. 지금 자료가 하나도 없어 안전하다.

## 6. 백엔드 구조

### 6.1 계층

파이썬 관례를 따라 **두 겹**으로 둔다. Java의 Service → Dao → Repository 세 겹은 파이썬 코드에서 흔치 않다.

| Spring | 여기 |
|---|---|
| `interface MemberRepository` | `class MemberRepository(Protocol)` |
| `@Repository class JpaMemberRepository` | `class D1MemberRepository` |
| `@Service class MemberService` | `class MemberService` |
| 컨테이너가 조립 | `Depends`로 조립하고 그 자리가 코드에 보인다 |

`Protocol`은 구현체가 상속을 선언하지 않아도 된다. 메서드 이름과 타입이 맞으면 그 자리에 들어간다.

### 6.2 폴더

```
packages/core/src/coc_core/
  config.py            클랜 설정 (공통)
  member/
    models.py          ClanMember, ClanRole, MemberStatus
    repository.py      MemberRepository (Protocol)
    service.py         MemberService

apps/api/
  database/
    schema.sql
    migrations/0001_init.sql
  src/
    adapters/
      member_repository.py   D1MemberRepository
      coc_api.py             CocApi
    routes/
      member.py              GET /api/v1/members
    schemas/                 명세에서 생성. 손대지 않는다
    cli.py                   refresh-members 명령
    worker.py                앱 조립과 진입점
    db.py                    D1 접근 공통
```

리소스가 늘면 `war/`, `score/`, `draw/`를 같은 모양으로 만든다. 의존은 `member ← war ← score ← draw` 한 방향으로만 흐른다.

### 6.3 바깥 값을 안으로 들이지 않는다

CoC API가 표기를 바꾸거나 새 직책을 만들어도 우리가 멈추면 안 된다. **어댑터가 경계에서 바꾼다.**

```python
class ClanRole(StrEnum):
    """클랜 안 직책.

    이름을 CoC API 표기의 대문자와 맞춘다. 그래서 변환이 한 줄로 끝난다.
    """

    LEADER = "LEADER"
    COLEADER = "COLEADER"   # 언더스코어를 넣지 않는다. API 의 coLeader 와 맞추기 위해서다
    ADMIN = "ADMIN"         # 게임 화면에서는 "장로(Elder)". API 가 admin 으로 준다
    MEMBER = "MEMBER"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_coc(cls, raw: str) -> ClanRole:
        """모르는 값이 오면 UNKNOWN. 한 명 때문에 동기화가 멈추지 않게 한다."""
        try:
            return cls(raw.upper())
        except ValueError:
            return cls.UNKNOWN
```

원본은 저장하지 않는다. 30분마다 다시 수집하므로 매핑을 고치면 다음 수집에 저절로 바로잡힌다.

**모르는 값이 왔다는 것은 알 수 있어야 한다.** 조용히 넘어가면 `UNKNOWN`이 쌓이는 것을 아무도 모른다.

| 어디 | 무엇 |
|---|---|
| 동기화 로그 | `모르는 직책: veteran (3명)` |
| `/api/health` | `UNKNOWN`인 인원 수 |
| 화면 | "알 수 없음" |

`status`는 CoC API가 주지 않고 우리가 판정하므로 이 문제가 없다.

```python
class MemberStatus(StrEnum):
    ACTIVE = "ACTIVE"      # 지금 클랜에 있다
    INACTIVE = "INACTIVE"  # 목록에서 사라졌다
```

### 6.4 서비스

동기화와 조회를 나눈다.

```python
class MemberService:
    def __init__(self, repository: MemberRepository, coc_api: CocApi) -> None:
        self._repository = repository
        self._coc_api = coc_api

    async def sync(self) -> SyncResult:
        """CoC API 에서 받아 우리 DB 에 맞춘다."""

    async def find_all(self) -> list[ClanMember]:
        """저장된 것을 돌려준다."""
```

동기화 결과를 돌려주어 무슨 일이 있었는지 남긴다.

```python
@dataclass(frozen=True)
class SyncResult:
    total: int                       # 받은 사람 수
    added: int                       # 새로 들어온 사람
    left: int                        # INACTIVE 로 내린 사람
    unknown_roles: dict[str, int]    # {"veteran": 3} — 무엇이 몇 번 왔나
```

### 6.5 동기화가 지켜야 할 것

**한 사람 때문에 전체가 멈추면 안 된다.** 모르는 직책이 와도 그 사람만 `UNKNOWN`이 되고 나머지는 정상으로 저장된다.

**나간 사람을 지우지 않는다.** 목록에서 사라지면 `status`를 `INACTIVE`로 내린다. 과거 기록이 이어지고, 돌아온 사람의 설정이 살아 있다.

**`description`을 덮어쓰지 않는다.** 관리자가 "무단 이탈로 추방"이라고 적어 둔 것이 다음 수집에 지워지면 안 된다.

```sql
INSERT INTO clan_members (id, tag, name, role, ..., status, created_at, updated_at)
VALUES (?, ?, ?, ?, ..., ?, ?, ?)
ON CONFLICT(tag) DO UPDATE SET
  name       = excluded.name,
  role       = excluded.role,
  ...
  status     = excluded.status,
  updated_at = excluded.updated_at
  -- description 과 created_at 은 여기 없다
```

### 6.6 조립

파이썬에는 스프링 컨테이너가 없다. 요청마다 손으로 조립하고 그 자리를 한곳에 모은다.

```python
def get_member_service(request: Request) -> MemberService:
    env = request.scope["env"]
    return MemberService(
        repository=D1MemberRepository(env.DB),
        coc_api=CocApi(env.COC_API_TOKEN),
    )


MemberSvc = Annotated[MemberService, Depends(get_member_service)]


@app.get("/api/v1/members")
async def list_members(service: MemberSvc) -> MemberListResponse:
    ...
```

번거로워 보이지만 무엇이 들어가는지 눈에 보이고, 테스트에서 가짜를 넣기 쉽다. 모킹 프레임워크가 필요 없다.

### 6.7 수집은 명령으로

첫 조각에서는 예약 실행을 붙이지 않는다.

```bash
uv run coc-api refresh-members
```

`apps/api/pyproject.toml`에 `[project.scripts]`로 진입점을 두고, `apps/api/src/cli.py`가 서비스를 조립해 부른다. 서버가 요청을 받아 조립하는 것과 같은 일이라 조립 코드를 함께 쓴다.

원격 D1에 쓰는 방법은 구현할 때 확인한다. `wrangler d1 execute --remote`를 거치거나 D1 HTTP API를 부른다. 로컬 D1(`--local`)로 먼저 돌려 보고 원격으로 넘어간다.

예약 실행(Cron)은 클랜전 수집을 옮길 때 함께 붙인다. 지금 붙이면 인증과 실패 처리까지 딸려 와 첫 조각이 커진다.

## 7. 프론트

**Vite + React + TypeScript.** 서버 렌더링이 필요 없으므로 Next.js 같은 메타 프레임워크는 쓰지 않는다. 백엔드가 이미 Cloudflare에 따로 있어 서버가 둘이 되면 복잡해진다.

```
apps/web/
  index.html
  src/
    main.tsx
    pages/Members.tsx
    api/
      client.ts          fetch 감싸기
      schema.d.ts        명세에서 생성. 손대지 않는다
    components/
    styles/style.css     기존 것을 옮겨 온다
  package.json
  vite.config.ts
  tsconfig.json
```

`vite.config.ts`의 `base`를 `/coc-pointer/members/`로 두어 GitHub Pages 경로에 맞춘다.

### 7.1 한 페이지씩 바꾼다

기존 페이지는 그대로 두고 `/members/`만 React로 교체한다.

```
site/
  index.html          기존 방식 (Jinja2)
  2026-09/index.html  기존 방식
  members/            ← React 빌드 결과
  style.css           둘이 함께 쓴다
```

GitHub Actions가 파이썬 빌드와 Vite 빌드를 차례로 돌려 한 폴더에 넣는다.

### 7.2 모르는 코드에 폴백을 둔다

서버가 `UNKNOWN`으로 막지만 프론트에도 방어가 필요하다.

```typescript
// 이렇게 하면 안 된다 — 없으면 코드가 그대로 화면에 나온다
const label = ROLE_LABEL[role];

// 이렇게 한다
const label = ROLE_LABEL[role] ?? "알 수 없음";
```

`Record<ClanRole, string>`으로 적어 두면 값을 빠뜨렸을 때 빌드가 깨진다. 폴백은 그래도 남긴다. 타입이 잡지 못하는 경우(서버가 명세보다 앞서 배포된 순간)가 있다.

### 7.3 세 상태를 구분한다

지금은 정적 파일이라 서버와 무관하게 보인다. API를 부르면 서버에 매인다.

| 상태 | 화면 |
|---|---|
| 불러오는 중 | 뼈대 화면 |
| 실패 | "잠시 후 다시 시도해 주세요"와 다시 시도 버튼 |
| 빈 목록 | "클랜원 자료가 아직 없습니다" |

실패와 빈 목록이 같아 보이면 원인을 찾을 수 없다.

## 8. 테스트

| 무엇 | 어떻게 |
|---|---|
| `MemberService` | 가짜 `MemberRepository`와 가짜 `CocApi`를 넣어 로직만 확인 |
| `ClanRole.from_coc` | 아는 값 넷과 모르는 값 |
| `D1MemberRepository` | 기존 가짜 D1(`sqlite3`) 위에서 실제 SQL 검증 |
| `schema.sql`과 마이그레이션 | 둘을 적용한 결과가 같은지 |
| `GET /api/v1/members` | FastAPI `TestClient` |
| React 화면 | 첫 조각에서는 두지 않는다 |

가짜 대역은 클래스 하나면 된다. 모킹 라이브러리를 들이지 않는다.

React 테스트를 지금 두지 않는 이유는 화면이 표 하나이고, 테스트 도구를 고르는 일이 첫 조각을 키우기 때문이다. 화면이 늘어나면 그때 둔다.

## 9. 단계

| 단계 | 내용 | 끝났을 때 |
|---|---|---|
| 1 | `contracts/openapi.yaml`과 생성 절차 | 명세에서 양쪽 타입이 나온다 |
| 2 | 마이그레이션과 `clan_members` 표 | 로컬 D1에 표가 만들어진다 |
| 3 | `coc_core/member/` — 자료형·인터페이스·서비스 | 가짜 대역 위에서 테스트가 돈다 |
| 4 | D1 어댑터와 CoC API 어댑터, `refresh-members` | 명령으로 D1을 채울 수 있다 |
| 5 | `GET /api/v1/members` | 브라우저에서 JSON이 보인다 |
| 6 | React 앱과 클랜원 화면 | 로컬에서 화면이 뜬다 |
| 7 | 두 빌드를 합쳐 배포 | `/members/`가 새 화면으로 바뀐다 |

**1~6단계는 Cloudflare 배포 없이 로컬에서 확인할 수 있다.** 지금 계정에 Workers가 열리지 않아 배포가 막혀 있으나 그 영향을 받지 않는다.

## 10. 미뤄 둔 판단

**Cloudflare 계정에 Workers가 열리지 않았다.** `code: 10034`로 배포가 막혀 있다. 단계 7만 그것을 기다린다.

**표끼리 클랜원을 어떻게 가리킬지**는 클랜전을 옮길 때 확정한다. 방향은 `id`로 잇는 것이되, 클랜전 기록은 그때의 사실을 담는 성격이라 예외가 필요할 수 있다.

**`packages/core`가 커지면 폴더를 나눌지** 다시 본다. 지금은 리소스별로만 나눈다.

**React 상태 관리 라이브러리를 지금 고르지 않는다.** 화면이 하나이고 받은 것을 그리기만 한다. 로그인이 붙어 여러 화면이 상태를 나눠 쓰게 되면 그때 정한다.

**프론트 라우팅 방식**은 상세 화면이 생길 때 정한다. GitHub Pages는 정적 파일 서버라 `/members/{id}` 같은 경로에 파일이 없으면 404를 낸다. 페이지마다 파일을 두거나 `404.html`로 SPA 라우팅을 받는다.
