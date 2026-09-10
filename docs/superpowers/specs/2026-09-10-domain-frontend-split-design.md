# 도메인과 화면을 가르는 설계

작성일: 2026-09-10
상태: 검토 대기
앞선 문서: `2026-09-10-backend-server-design.md` — **이 문서가 그것의 3절(전체 구조)을 대체한다.** 그 문서는 "화면은 지금 방식을 유지한다"고 적었으나 방향이 바뀌었다.

## 1. 목적

**백엔드가 무엇이 참인지 말하고, 프론트가 그것을 어떻게 보일지 정한다.**

지금은 프론트가 둘 다 한다. `apps/web/src/coc_pointer/render.py`가 점수를 계산하고 선발 명단을 뽑은 뒤 HTML을 만든다. 규칙이 바뀌면 화면을 다시 배포해야 하고, 같은 계산을 서버도 하게 되면 규칙이 두 곳에 생긴다.

경계를 이렇게 긋는다.

| | 백엔드 | 프론트 |
|---|---|---|
| 클랜원 직책 | `"role": "coLeader"` | "공동 대표"로 표시 |
| 점수 | `"score": 87.5` | "87.5점" 또는 막대 길이 |
| 선발 여부 | `"selected": true` | 초록색 배지 |
| 날짜 | `"2026-09-05T14:30:00Z"` | "9월 5일 23시" |

왼쪽은 사실이고 오른쪽은 표현이다. 규칙이 바뀌면 왼쪽만, 문구를 바꾸려면 오른쪽만 고친다.

`render.py`의 `ROLE_KO`(직책을 한국어로 바꾸는 표)는 프론트가 할 일이 맞다. 같은 파일의 `from coc_core.scoring import rank_month, roster, split_rewards`가 걷어낼 부분이다.

## 2. 지금 상태와 옮길 곳

| 파일 | 줄 | 어디로 |
|---|---|---|
| `apps/web/.../collect.py` | 184 | 서버로 |
| `apps/web/.../api.py` | 91 | 서버로 (CoC API 어댑터) |
| `apps/web/.../storage.py` | 66 | 서버로 (D1 어댑터가 된다) |
| `apps/web/.../cli.py` | 82 | 서버로 |
| `apps/web/.../render.py` | 211 | **사라진다.** 자바스크립트가 대신한다 |
| `apps/web/.../templates/` | 546 | 자바스크립트로 다시 만든다 |
| `packages/core/` | 605 | 리소스별로 나눈다 (3절) |

다 옮기면 `apps/web`에 파이썬이 남지 않는다.

## 3. 구조

### 3.1 계층

파이썬 관례를 따라 **두 겹**으로 둔다. Java의 Service → Dao → Repository 세 겹은 파이썬 코드에서 흔치 않다.

```
Service      로직. 무엇을 어떻게 할지
Repository   데이터 접근. 인터페이스는 Protocol, 구현은 어댑터에
```

| Spring | 여기 |
|---|---|
| `interface MemberRepository` | `class MemberRepository(Protocol)` |
| `@Repository class JpaMemberRepository` | `class D1MemberRepository` |
| `@Service class MemberService` | `class MemberService` |
| 컨테이너가 조립 | `Depends`로 조립하고 그 자리가 코드에 보인다 |

`Protocol`은 구현체가 상속을 선언하지 않아도 된다. 메서드 이름과 타입이 맞으면 그 자리에 들어간다.

### 3.2 리소스별로 나눈다

```
packages/core/src/coc_core/
  config.py            클랜 설정 (공통)
  member/
    models.py          ClanMember
    repository.py      MemberRepository (Protocol)
    service.py         MemberService
  war/                 (다음 단계)
  score/               (다음 단계)
  draw/                (다음 단계)

apps/api/src/
  adapters/
    member_repository.py   D1MemberRepository
    coc_api.py             CocApi — CoC 공식 API 호출
  routes/
    member.py              GET /api/members
  worker.py                앱 조립과 진입점
  db.py                    D1 접근 공통
```

각 폴더가 자료형·인터페이스·로직 셋을 갖는다. 리소스 하나를 이해하려면 그 폴더만 보면 된다.

### 3.3 의존 방향

```
member  ←  war  ←  score  ←  draw
```

- `war`는 참가자를 태그로만 가리키고 `member`를 import하지 않는다
- `score`는 `war`의 공격 기록과 `member`의 명단을 받아 계산한다
- `draw`는 `score`의 결과에서 후보를 고른다

한 방향으로만 흐른다. 거꾸로 가는 import가 생기면 설계가 틀어진 것이다.

### 3.4 조립

파이썬에는 스프링 컨테이너가 없다. 요청마다 손으로 조립하고, 그 자리를 한곳에 모은다.

```python
# apps/api/src/routes/member.py
def get_member_service(request: Request) -> MemberService:
    env = request.scope["env"]
    return MemberService(
        repository=D1MemberRepository(env.DB),
        coc_api=CocApi(env.COC_API_TOKEN),
    )


MemberSvc = Annotated[MemberService, Depends(get_member_service)]


@app.get("/api/members")
async def list_members(service: MemberSvc) -> MemberListResponse:
    ...
```

번거로워 보이지만 무엇이 들어가는지 눈에 보이고, 테스트에서 가짜를 넣기 쉽다. 모킹 프레임워크가 필요 없다.

## 4. 첫 조각: 클랜원 조회

한 번에 다 바꾸지 않는다. **클랜원 목록 하나를 처음부터 끝까지 관통해** 길을 뚫고, 나머지 화면은 그 길을 따라 하나씩 옮긴다.

```
CoC API → MemberService → MemberRepository → D1 → GET /api/members → React
```

가장 단순하다. 점수 계산도 월별 집계도 없이 목록 하나인데, 전 구간을 지난다.

### 4.1 수집은 명령으로

첫 조각에서는 예약 실행을 붙이지 않는다. 로컬에서 명령 하나로 D1을 채운다.

```
uv run coc-api refresh-members
```

이 명령은 새로 만든다. `apps/api/pyproject.toml`에 `[project.scripts]`로 진입점을 두고, `apps/api/src/cli.py`가 서비스를 조립해 부른다. 서버가 요청을 받아 조립하는 것과 같은 일을 명령줄에서 하는 것뿐이라, 조립 코드를 한곳에 모아 양쪽이 함께 쓴다.

원격 D1에 쓰려면 자격이 필요하다. `wrangler d1 execute --remote`를 거치거나 Cloudflare의 D1 HTTP API를 부른다. **둘 중 어느 쪽이 나은지는 구현할 때 확인한다.** 로컬 D1(`--local`)로 먼저 돌려 보고 원격으로 넘어가는 편이 안전하다.

예약 실행(Cron)은 클랜전 수집을 옮길 때 함께 붙인다. 지금 붙이면 인증과 실패 처리까지 딸려 와서 첫 조각이 커진다.

### 4.2 기존 페이지는 그대로

`/`와 `/2026-09/`는 지금 방식(Jinja2)으로 계속 만든다. `/members/`만 React로 바꾼다.

```
site/
  index.html          기존 방식
  2026-09/index.html  기존 방식
  members/            ← React 빌드 결과
  style.css           둘이 함께 쓴다
```

GitHub Actions가 파이썬 빌드와 Vite 빌드를 차례로 돌려 한 폴더에 넣는다.

**중간에 사이트가 어긋나도 된다.** 아직 클랜에 공개하지 않았다.

## 5. API 계약

```
GET /api/members
```

```json
{
  "members": [
    {
      "tag": "#ABC123",
      "name": "도토리",
      "role": "coLeader",
      "townhall": 16,
      "trophies": 4200,
      "donations": 1200,
      "donationsReceived": 800,
      "inClan": true
    }
  ],
  "fetchedAt": "2026-09-10T05:30:00Z"
}
```

**규칙 세 가지를 둔다.**

1. **원시 값을 준다.** `role`은 `coLeader`이지 "공동 대표"가 아니다. 화면이 옮긴다
2. **키는 캐멀케이스.** 자바스크립트가 소비하므로 그쪽 관례를 따른다. 파이썬 안에서는 스네이크케이스를 쓰고 응답을 만들 때 바꾼다
3. **시각은 UTC ISO 문자열.** 한국 시간 변환은 화면이 한다

응답 모양은 Pydantic 모델로 적어 둔다. FastAPI가 그것으로 OpenAPI 문서를 만들고, 프론트는 그 타입을 보고 TypeScript 타입을 적는다.

### 5.1 기존 경로도 함께 맞춘다

이미 있는 `/api/scores/{월}`과 `/api/draws/{월}`은 스네이크케이스를 쓴다(`drawn_at`). 새 규칙과 어긋나므로 **이번에 함께 캐멀케이스로 바꾼다.** 아직 이 경로를 부르는 곳이 없어 지금이 바꾸기 가장 싼 때다. 화면이 붙은 뒤에 바꾸면 양쪽을 함께 고쳐야 한다.

### 5.2 자료형에 세 항목을 더한다

D1 `members` 표에는 있는데 도메인의 `ClanMember`에는 없는 것이 셋이다.

| 항목 | 뜻 |
|---|---|
| `in_clan` | 지금 클랜에 있는가. 나간 사람은 지우지 않고 이 값을 내린다 |
| `first_seen_at` | 처음 본 시각 |
| `last_seen_at` | 마지막으로 본 시각 |

`ClanMember`에 더한다. 나갔다 돌아온 사람의 기록이 이어지려면 도메인이 이것을 알아야 한다. 단 `first_seen_at`과 `last_seen_at`은 저장할 때 어댑터가 채운다. 도메인 로직이 시계를 직접 보지 않게 한다.

## 6. 프론트

**Vite + React + TypeScript.** 서버 렌더링이 필요 없으므로 Next.js 같은 메타 프레임워크는 쓰지 않는다. 백엔드가 이미 Cloudflare에 따로 있어 서버가 둘이 되면 복잡해진다.

```
apps/web/
  index.html
  src/
    main.tsx
    pages/
      Members.tsx        클랜원 목록
    api/
      client.ts          fetch 감싸기
      types.ts           서버 응답 타입
    components/
    styles/
      style.css          기존 것을 옮겨 온다
  package.json
  vite.config.ts
  tsconfig.json
```

`vite.config.ts`의 `base`를 `/coc-pointer/members/`로 두어 GitHub Pages 경로에 맞춘다.

### 6.1 서버가 죽었을 때

지금은 정적 파일이라 서버와 무관하게 보인다. API를 부르게 되면 서버에 매인다. **화면이 빌 때 무엇을 보여줄지 정해 둔다.**

- 불러오는 중: 뼈대 화면
- 실패: "잠시 후 다시 시도해 주세요"와 다시 시도 버튼
- 빈 목록: "클랜원 자료가 아직 없습니다"

셋을 구분한다. 실패와 빈 목록이 같아 보이면 원인을 못 찾는다.

## 7. 테스트

| 무엇 | 어떻게 |
|---|---|
| `MemberService` | 가짜 `MemberRepository`와 가짜 `CocApi`를 넣어 로직만 확인 |
| `D1MemberRepository` | 기존 가짜 D1(sqlite3) 위에서 실제 SQL 검증 |
| `GET /api/members` | FastAPI `TestClient` |
| React 화면 | 첫 조각에서는 두지 않는다 |

가짜 대역은 클래스 하나면 된다. 모킹 라이브러리를 들이지 않는다.

React 테스트를 지금 두지 않는 이유는 화면이 표 하나이고, 테스트 도구를 고르는 일이 첫 조각을 키우기 때문이다. 화면이 늘어나면 그때 둔다.

## 8. 단계

| 단계 | 내용 | 끝났을 때 |
|---|---|---|
| 1 | `coc_core/member/` 만들기. 자료형·인터페이스·서비스 | 테스트가 가짜 대역 위에서 돈다 |
| 2 | D1 어댑터와 CoC API 어댑터 | 명령으로 D1을 채울 수 있다 |
| 3 | `GET /api/members` | 브라우저에서 JSON이 보인다 |
| 4 | React 앱과 클랜원 화면 | 로컬에서 화면이 뜬다 |
| 5 | 두 빌드를 합쳐 배포 | `/members/`가 새 화면으로 바뀐다 |

각 단계가 끝날 때 확인할 것이 있다. 단계 3까지는 Cloudflare 배포 없이 로컬에서 확인할 수 있다.

## 9. 이번에 하지 않는 것

- 로그인과 사용자 관리 (TASK-23)
- 추첨 (TASK-18)
- 점수·클랜전 기록·리그전 화면 — 다음 조각들
- 예약 실행으로 수집 (TASK-21)
- 클랜원 관리 화면 (TASK-22)
- `packages/core`를 `domain`과 `application`으로 나누기 — 605줄에는 이르다
- 화면 개선 — 보이는 모습은 지금과 같게 둔다

## 10. 미뤄 둔 판단

**Cloudflare 계정에 Workers가 아직 열리지 않았다.** `code: 10034`로 배포가 막혀 있다. 단계 5는 그것이 풀려야 한다. 단계 1~4는 영향받지 않는다.

**`packages/core`가 커지면 폴더를 나눌지 다시 본다.** 지금은 리소스별로만 나눈다.

**React 상태 관리 라이브러리를 지금 고르지 않는다.** 화면이 하나이고 서버에서 받은 것을 그리기만 한다. 로그인이 붙어 여러 화면이 상태를 나눠 쓰게 되면 그때 정한다.
