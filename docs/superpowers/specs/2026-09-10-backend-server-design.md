# 백엔드 서버 설계 문서

작성일: 2026-09-10
상태: 검토 대기
관련 티켓: TASK-20, TASK-21, TASK-22, TASK-18, BUG-02

## 1. 목적

데이터의 주인을 저장소에서 서버로 옮긴다. 파이썬 FastAPI를 Cloudflare Workers 위에 올리고, 자료는 D1에 담는다.

첫 설계 문서(2026-09-07)는 "서버, 데이터베이스, 로그인 화면"을 하지 않는 것으로 정했다. 그 판단은 당시 범위에서는 옳았으나, 그 뒤 세 가지가 드러나 전제가 바뀌었다.

- **추첨을 누른 순간 당첨자가 정해져야 한다.** 미리 뽑아 두는 방식은 답을 정해 놓고 보여 주는 것이라 쓸 수 없다. 그 순간 응답하는 서버가 필요하다.
- **GitHub Actions의 예약 실행이 3~4시간씩 밀린다.** 30분으로 설정해도 그렇다. 그래서 기록을 잃을 뻔했다(BUG-01, BUG-02).
- **사용자 관리처럼 서버가 판단해야 하는 기능이 앞으로 계속 붙는다.** 지금 자바스크립트로 만들면 나중에 파이썬으로 다시 옮겨야 한다.

## 2. 왜 파이썬을 Cloudflare에 올릴 수 있나

Cloudflare의 Python Workers가 FastAPI와 Pydantic을 공식 지원한다. 파이썬이 WebAssembly로 컴파일된 CPython(Pyodide) 위에서 돈다.

| 항목 | 내용 |
|---|---|
| 상태 | 오픈 베타. `python_workers` 호환성 플래그가 필요하다 |
| 지원 패키지 | Pyodide가 미리 준비한 것과 순수 파이썬 패키지. FastAPI, Pydantic 포함 |
| HTTP 라이브러리 | 비동기만 가능하다. `httpx`는 되고 `requests`는 안 된다 |
| 요금 | 무료 플랜으로 하루 10만 요청 |
| **CPU 시간** | **요청 한 건당 10밀리초.** 유료 플랜(월 5달러)은 30초 |
| 콜드 스타트 | 빠르다. 잠들었다 깨어나는 지연이 없다 |

CPU 10밀리초 제한이 이 설계의 여러 판단을 좌우한다. 아래 4.5절과 6절에서 다룬다.

## 3. 전체 구조

```
┌─ Cloudflare ────────────────────────────────────┐
│                                                 │
│  Cron Trigger (30분마다)                        │
│      ├─ CoC API에서 클랜전을 받아온다            │
│      ├─ D1에 저장한다                            │
│      └─ 월별 점수를 계산해서 D1에 저장한다        │
│                                                 │
│  FastAPI                                        │
│      인증 · 사용자 · 클랜원 · 설정 · 점수 · 추첨   │
│                                                 │
│  D1 (SQLite)                                    │
└─────────────────────────────────────────────────┘
              ↑ API 호출
┌─ GitHub Pages ──────────────────────────────────┐
│  정적 HTML. 빌드 때 만든 점수표를 그대로 보여준다 │
└─────────────────────────────────────────────────┘
```

화면은 지금 방식을 유지한다. 페이지 전체를 API로 그리도록 바꾸면 잘 돌아가는 부분까지 다시 만들게 되고, 중간에 문제가 생기면 사이트 전체가 멈춘다. 데이터의 주인만 서버로 옮기고 화면은 그대로 둔다.

### 3.1 저장소 구조

```
apps/web/       파이썬 - 정적 페이지 생성
apps/api/       파이썬 - FastAPI + Cron
packages/core/  점수 계산 등 공용 코드 (coc_core)
```

`packages/core`는 2026-09-10에 분리를 마쳤다. 자료형(models), 설정(config), 점수 계산(scoring), 보상 판정(rewards), 그리고 두 테스트 묶음이 함께 쓰는 생성기(testing)가 들어 있다.

공용 코드를 나눈 이유는 **서버가 추첨 후보를 직접 정해야 하기 때문**이다. 브라우저가 후보 명단을 보내면 개발자 도구로 그 명단을 바꿔 보낼 수 있고, 서버는 진짜 후보인지 확인할 방법이 없다. 서버가 자기 데이터를 보고 점수를 계산해 후보를 정하면 이 문제가 사라진다.

## 4. 데이터베이스 설계

여덟 개 표를 세 갈래로 나눌 수 있다.

| 갈래 | 표 | 무엇인가 |
|---|---|---|
| 사실 | `wars`, `war_members`, `attacks`, `members` | CoC API에서 받은 것 |
| 계산 | `monthly_scores` | 사실로부터 계산한 결과 |
| 기록 | `users`, `draws`, `settings` | 사람이 만든 것 |

### 4.1 클랜전 기록

```sql
CREATE TABLE wars (
  id                 TEXT PRIMARY KEY,   -- 2026-09-05T14-30-00Z_regular_2ABC123
  war_type           TEXT NOT NULL,      -- regular | cwl
  start_time         TEXT NOT NULL,
  end_time           TEXT NOT NULL,
  team_size          INTEGER NOT NULL,
  attacks_per_member INTEGER NOT NULL,   -- 일반 2, 리그전 1
  opponent_tag       TEXT NOT NULL,
  opponent_name      TEXT NOT NULL,
  in_progress        INTEGER NOT NULL DEFAULT 0,
  round_no           INTEGER,            -- 리그전만
  total_rounds       INTEGER             -- 리그전만
);

CREATE TABLE war_members (
  war_id   TEXT NOT NULL REFERENCES wars(id) ON DELETE CASCADE,
  tag      TEXT NOT NULL,
  name     TEXT NOT NULL,
  townhall INTEGER NOT NULL,
  PRIMARY KEY (war_id, tag)
);

CREATE TABLE attacks (
  war_id       TEXT NOT NULL,
  attacker_tag TEXT NOT NULL,
  attack_order INTEGER NOT NULL,
  stars        INTEGER NOT NULL,
  PRIMARY KEY (war_id, attacker_tag, attack_order),
  FOREIGN KEY (war_id, attacker_tag)
    REFERENCES war_members(war_id, tag) ON DELETE CASCADE
);
```

`id`는 지금 파일 이름을 그대로 쓴다. 종료 시각과 종류와 상대 태그를 합쳐 만들므로 같은 클랜전이 두 번 들어오는 것을 막아 준다.

`war_members`에 `name`을 함께 담는다. 닉네임은 바뀌고 사람은 클랜을 떠난다. 그때 그 클랜전에서 어떤 이름이었는지 남겨야 과거 기록이 읽힌다. 사람을 식별하는 것은 언제나 `tag`다.

### 4.2 게임 계정

```sql
CREATE TABLE members (
  tag                TEXT PRIMARY KEY,
  name               TEXT NOT NULL,
  role               TEXT,                        -- 게임 안 직책
  townhall           INTEGER,
  trophies           INTEGER,
  donations          INTEGER,
  donations_received INTEGER,
  in_clan            INTEGER NOT NULL DEFAULT 1,
  first_seen_at      TEXT NOT NULL,
  last_seen_at       TEXT NOT NULL
);
```

지금 `data/clan.json`은 현재 클랜원만 담는 스냅샷이라, 나간 사람은 흔적 없이 사라진다. 이 표는 한 번 들어온 사람을 지우지 않고 `in_clan`만 0으로 바꾼다. 그래야 9월 점수표를 10월에 봐도 이름이 나오고, 나갔다 돌아온 사람의 기록이 이어진다.

정예·부캐·제외·경고는 이 표에 넣지 않는다. 당분간 `config/clan.yaml`에 그대로 두고, 어디에 둘지는 TASK-22에서 정한다. 게임 계정에 붙일 수도, 사람에게 붙일 수도 있다.

### 4.3 서비스 계정

```sql
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,                   -- 해시만. 원문은 어디에도 남기지 않는다
  display_name  TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'member',  -- admin | member
  member_tag    TEXT REFERENCES members(tag),    -- 연결된 게임 계정. 없어도 된다
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);
```

게임 계정과 서비스 계정은 다른 것이다. 관리자는 게임 계정 없이도 로그인할 수 있고, 클랜원은 자기 게임 계정에 연결해 자기 점수를 본다. `member_tag`가 둘을 잇는다.

### 4.4 클랜 설정

```sql
CREATE TABLE settings (
  key   TEXT PRIMARY KEY,   -- clan_tag, cwl_bonus_count
  value TEXT NOT NULL
);
```

### 4.5 미리 계산해 둔 점수

```sql
CREATE TABLE monthly_scores (
  month       TEXT NOT NULL,     -- 2026-09
  tag         TEXT NOT NULL,
  name        TEXT NOT NULL,
  attacks     INTEGER NOT NULL,
  stars       INTEGER NOT NULL,
  score       REAL NOT NULL,
  computed_at TEXT NOT NULL,
  PRIMARY KEY (month, tag)
);
```

**이 표가 CPU 10밀리초 제한에 대한 답이다.** 클랜원 46명의 여러 달치 점수를 요청이 올 때마다 계산하기는 빠듯하다. 그래서 30분마다 수집할 때 함께 계산해 넣어 둔다. 예약 실행에는 그 제한이 적용되지 않는다. 요청이 오면 읽기만 하므로 순식간에 끝난다.

`name`이 `members`와 겹치는 것은 일부러다. 9월 점수표를 보는데 그 사람이 10월에 클랜을 나갔다면 이름을 붙일 곳이 없기 때문이다.

### 4.6 추첨 결과

```sql
CREATE TABLE draws (
  month      TEXT PRIMARY KEY,   -- 2026-09
  winners    TEXT NOT NULL,      -- JSON 배열
  candidates TEXT NOT NULL,      -- 뽑을 때 후보가 누구였는지
  slots      INTEGER NOT NULL,
  drawn_at   TEXT NOT NULL
);
```

당첨자를 별도 표로 나누지 않는다. 추첨 결과는 항상 통째로 읽고 통째로 쓰므로 표를 나누면 조인만 늘고 얻는 것이 없다. D1은 SQLite라 JSON 타입이 따로 없어 TEXT에 담는다.

`candidates`를 남기는 이유는 나중에 "왜 저 사람이 뽑혔느냐"는 말이 나왔을 때 그때 후보가 누구였는지 보여 주기 위해서다.

## 5. API 설계

경로는 모두 `/api`로 시작한다. 조회는 누구나 하고, 바꾸는 것은 로그인한 사람만 한다.

| 경로 | 권한 | 하는 일 |
|---|---|---|
| `GET /api/health` | 누구나 | 배포가 제대로 되었는지 확인 |
| `POST /api/auth/login` | 누구나 | 로그인. 토큰을 돌려준다 |
| `POST /api/auth/logout` | 로그인 | 토큰을 버린다 |
| `GET /api/users/me` | 로그인 | 내 정보 |
| `GET /api/users` | 관리자 | 계정 목록 |
| `POST /api/users` | 관리자 | 계정 만들기 |
| `PATCH /api/users/{id}` | 관리자 | 권한·연결 계정 변경 |
| `GET /api/members` | 누구나 | 클랜원 목록 |
| `GET /api/settings` | 누구나 | 보상 인원 등 클랜 설정 |
| `PATCH /api/settings` | 관리자 | 클랜 설정 변경 |
| `GET /api/scores/{월}` | 누구나 | 그달 점수표 |
| `GET /api/draws/{월}` | 누구나 | 추첨 결과 |
| `POST /api/draws/{월}` | 관리자 | 추첨 실행 |

응답에는 `X-Api-Version` 헤더를 붙여, 어느 배포본이 답했는지 응답만 보고 알 수 있게 한다.

## 6. 인증

### 6.1 비밀번호

원문은 어디에도 저장하지 않는다. 해시만 담는다. 관리자 비밀번호는 사용자가 직접 정하며 코드에도 저장소에도 남지 않는다.

**여기에 풀어야 할 문제가 있다.** 비밀번호 해시는 일부러 느린 계산을 수만 번 반복해야 안전한데, 그 계산이 CPU 10밀리초를 넘는다. 반복을 줄이면 계산은 빨라지지만 비밀번호가 뚫리기 쉬워진다.

| 방법 | 되는가 | 대가 |
|---|---|---|
| Workers의 브라우저 표준 암호 기능(`crypto.subtle`)을 파이썬에서 불러 쓴다 | **확인 필요** | 런타임이 계산하므로 빠르다 |
| 유료 플랜으로 올린다 | 확실히 된다 | 월 5달러 |
| 반복 횟수를 줄인다 | 된다 | 보안이 약해진다. 권하지 않는다 |

첫 번째를 먼저 시험하고, 안 되면 유료 플랜으로 간다. 이 판단은 실제로 올려 봐야 내릴 수 있다.

### 6.2 토큰

로그인하면 토큰을 발급해 브라우저가 갖고 있다가 요청마다 보낸다. 비밀번호를 매번 보내지 않아도 되고, 해시 계산도 로그인할 때 한 번만 일어난다.

## 7. 올려 보기 전에는 알 수 없는 것

Pyodide 환경에서 실제로 되는지 확인해야 하는 항목이다. TASK-20의 `GET /api/health`가 이것들을 한 번에 확인한다.

| 확인할 것 | 왜 걱정되나 |
|---|---|
| `coc_core`를 불러올 수 있는가 | 로컬 패키지라 PyPI에 없다. 배포할 때 함께 넣어야 한다 |
| `ZoneInfo("Asia/Seoul")`가 되는가 | 시간대 자료가 런타임에 없을 수 있다 |
| D1이 붙는가 | 바인딩 설정이 맞는지 |
| `crypto.subtle`을 파이썬에서 부를 수 있는가 | 6.1의 문제 |

## 8. 단계

| 단계 | 티켓 | 내용 | 상태 |
|---|---|---|---|
| 1 | TASK-20 | FastAPI 기반, D1 생성, 공용 코드 분리, 배포 확인 | 진행 중 |
| 2 | TASK-23 | 사용자 관리. 로그인, 계정 만들기, 권한 | 새로 만들 것 |
| 3 | TASK-21 | 수집을 Cron으로 옮기고 점수를 미리 계산. BUG-02를 닫는다 | 대기 |
| 4 | TASK-22 | 클랜원 관리. 정예·제외 설정을 화면에서 | 새로 만들 것 |
| 5 | TASK-18 | 보상 추첨. 서버가 후보를 직접 정한다 | 대기 |

## 9. 이번에 하지 않는 것

- 페이지 전체를 API로 그리기. 화면은 지금 방식을 유지한다
- 기존 `data/*.json` 삭제. 당분간 백업으로 남긴다
- 여러 클랜 지원
- 게임 계정 소유 확인. 지금은 관리자가 손으로 연결해 준다
