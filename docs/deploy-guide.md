# 배포 지침

무엇을 언제 어떻게 내보내는지. 배포할 때 이 문서를 펴 놓고 따라간다.

**이 문서는 자란다.** 새로 정할 일이 생기면 정한 뒤 여기에 적는다. 각 항목에는
**무엇을 정했는지**와 **왜**를 함께 적는다.

API 가 어떤 모양이어야 하는지는 `docs/api-guide.md` 에 있다. 티켓을 언제 닫는지는
Obsidian 금고의 `Circle/Project/Toy/COC/프로세스.md` 에 있다.

---

## 1. 배포는 티켓이 아니라 릴리즈의 일이다

```
티켓    할일 → 진행중 → 검토(PR 올림) → 완료(PR 머지)
릴리즈  티켓 여럿을 묶어 내보내고 확인한다
```

**티켓은 머지되면 끝난다.** 배포하지 않아도 닫힌다.

**왜.** 둘을 섞으면 "배포했으니 끝났다"가 된다. 2026-09-16 에 실제로 그랬다 —
배포는 됐는데 기능을 한 번도 돌려 보지 않은 채 끝났다고 말했다.

---

## 2. 지금 무엇이 자동이고 무엇이 손인가

| | 어떻게 | 어디서 |
|---|---|---|
| **검사** | PR 마다 자동 | GitHub Actions (`check.yml`) |
| **클랜전 수집** | 30분마다 자동 | GitHub Actions (`collect.yml`) |
| **화면 배포** | 수집이 끝나면 자동, 또는 손으로 | GitHub Actions → GitHub Pages |
| **API 배포** | **손으로** | 사람 노트북 → Cloudflare Workers |

API 배포만 사람이 명령을 친다. 자동화는 아직 정하지 않았다 — 아래 9번 참고.

---

## 3. 배포 순서

### API 를 먼저, 화면을 나중에

```bash
./apps/rest-api/deploy.sh                    # 1. API
gh workflow run collect --ref main           # 2. 화면
```

**왜 이 순서인가.** 응답 모양이 바뀌면 화면이 먼저 올라갈 때 표가 빈다. 옛 API 가
주는 응답에 새 필드가 없기 때문이다. 거꾸로면 잠깐 옛 화면이 새 API 를 부르는데,
그쪽이 덜 아프다 — 어차피 곧 화면이 따라온다.

### `deploy.sh` 가 하는 일

1. Cloudflare 인증 확인
2. D1 데이터베이스가 없으면 만든다
3. **마이그레이션 가운데 아직 안 건 것을 건다**
4. `packages/core` 를 `apps/rest-api/src/coc_core` 로 복사한다
5. `pywrangler deploy`

3번과 4번을 눈여겨본다. 아래 5번과 6번에서 다시 다룬다.

### 배포 뒤 확인

```bash
curl https://coc-api.coc-api.workers.dev/api/health
```

`coc_core: "ok"` 와 표 아홉 개가 보이면 올라간 것이다. 그다음 릴리즈 노트의
**"배포 뒤 확인할 것"** 을 하나씩 짚는다. 각 티켓에서 모아 둔 목록이다.

**여기서 걸리면 릴리즈는 아직 안 끝났다.**

---

## 4. 비밀값 셋

Cloudflare 에 넣어 둔다. 저장소에는 두지 않는다.

```bash
cd apps/rest-api
npx wrangler@4 secret put COC_API_TOKEN
npx wrangler@4 secret put CLAN_TAG
npx wrangler@4 secret put ADMIN_PASSWORD
```

| 이름 | 무엇 | 없으면 |
|---|---|---|
| `COC_API_TOKEN` | CoC API 토큰 | `include=profile` 과 동기화가 503 |
| `CLAN_TAG` | 우리 클랜 태그 | 위와 같다 |
| `ADMIN_PASSWORD` | 운영 표면 비밀번호 (임시) | 운영 표면 전부 503 |

**`wrangler.toml` 의 `[vars]` 에 두지 않는다.** 그 파일은 저장소에 남는다. 배포
환경마다 달라지는 값과 바깥에 알릴 이유가 없는 값을 적을 자리가 아니다.

**셋 다 ASCII 여야 한다.** `ADMIN_PASSWORD` 는 HTTP 헤더로 오가기 때문이다.
한글로 정하면 브라우저가 요청을 보내지도 못하고, 서버가 거부하는 것이 아니라 아예
나가지 않아 쓰는 사람은 무엇이 잘못됐는지 알 길이 없다.

**없으면 막는다.** 열어 두는 쪽으로 기울면 설정을 빠뜨린 배포가 조용히 운영
표면을 공개해 버린다.

### Claude Code 안에서 넣으면 빈 값이 들어간다

`wrangler secret put` 은 값을 물어보는데, Claude Code 의 `!` 로 실행하면 입력
자리가 이어지지 않아 빈 값을 읽고 그대로 올린다. **터미널 앱을 따로 열어서**
실행한다. 2026-09-16 에 실제로 겪었다.

---

## 5. 개발 서버가 없다. 배포하면 곧바로 운영이다

그러므로 **PR 을 올리기 전에 노트북에서 진짜로 돌려 본다.** 가짜를 쓴 자동
테스트는 로직을 증명하지만 진짜 호출을 증명하지 않는다.

```bash
./scripts/dev-vars.sh                  # 로컬용 값을 모은다. 한 번만
cd apps/rest-api
npx wrangler@4 d1 migrations apply coc-pointer --local   # 로컬 D1 에 표를 만든다
npm run dev                            # 진짜 Worker 를 띄운다
```

`pywrangler dev` 가 **배포되는 것과 같은 런타임(Pyodide)** 으로 띄우고, 진짜 CoC 를
부르며, 로컬 D1 에 쓴다. 배포에서만 드러나던 것 대부분이 여기서 드러난다.

| 쓰는 값 | 어디서 |
|---|---|
| `COC_API_TOKEN` | `.env` 에서 그대로 |
| `CLAN_TAG` | 게임에서 누구나 보는 값 |
| `ADMIN_PASSWORD` | **로컬 전용으로 새로 만든다.** 운영 비밀번호와 무관하다 |

`apps/rest-api/.dev.vars` 는 `.gitignore` 에 들어 있다. 값은 따옴표로 감싼다 —
`#` 이 주석을 여는 글자라 `CLAN_TAG=#2C8L822LQ` 로 적으면 값이 통째로 사라진다.

### 그래도 로컬에서 못 보는 것

Cloudflare 에만 있는 것 — 배포된 D1 의 실제 자료, 운영 비밀값, 예약 실행. 그런
것은 티켓에 **"배포 뒤 확인할 것"** 으로 적고 릴리즈가 확인한다.

---

## 6. 마이그레이션은 되돌리기 어렵다

`deploy.sh` 가 배포하면서 **아직 안 건 마이그레이션을 건다.** D1 이 `d1_migrations`
표에 무엇을 걸었는지 기록하므로 두 번 걸리지 않는다.

**한 번 나간 마이그레이션은 절대 고치지 않는다.** 새 번호를 붙인 파일을 더한다.
이미 걸린 것을 고쳐도 D1 은 다시 걸지 않으므로, 고친 내용은 아무 데도 반영되지
않고 다음에 새로 만드는 데이터베이스만 달라진다.

SQLite 제약 둘을 기억한다.

- `ALTER TABLE ... ADD CONSTRAINT` 가 없다. CHECK 는 표를 만들 때 넣어야 한다
- CHECK 에 걸린 열은 `DROP COLUMN` 으로 뗄 수 없다. 표를 다시 지어야 한다

### 배포 전에 무엇이 걸릴지 본다

```bash
cd apps/rest-api && npx wrangler@4 d1 migrations list coc-pointer --remote
```

표를 다시 짓는 마이그레이션이면 **지금 배포된 D1 에 자료가 얼마나 있는지** 먼저
본다. 옮길 열과 버릴 열이 맞는지 확인하고 배포한다.

---

## 7. 배포는 작업 폴더에서 나간다

`deploy.sh` 4단계가 `packages/core` 를 복사하는데, 원본이 git 이 아니라 **지금
디스크에 있는 파일**이다. 그래서 이런 일이 가능하다.

- 고치다 만 코드가 배포된다
- 커밋에서 빠뜨린 코드가 배포된다
- **배포된 것과 `main` 이 다르다**

2026-09-16 에 실제로 그랬다. `can_sync` 가 커밋에서 빠졌는데 배포는 멀쩡했고
`main` 만 깨져 있었다.

**배포 전에 `git status` 가 깨끗한지 본다.** 고치는 것은 `TASK-35 배포는 커밋된
것만` 이 맡는다.

---

## 8. 버전은 다섯 자리가 같아야 한다

| 어디 | 무엇 |
|---|---|
| `apps/web/pyproject.toml` | `version` |
| `apps/rest-api/pyproject.toml` | `version` |
| `packages/core/pyproject.toml` | `version` |
| `api/openapi.yaml` | `info.version` |
| `apps/rest-api/wrangler.toml` | `API_VERSION` |

**왜.** `GET /api/health` 가 `API_VERSION` 을 돌려주고 화면 바닥이 `apps/web` 의
판을 적는다. 다섯이 같아야 **지금 도는 것이 저장소의 어느 시점인지** 말할 수 있다.
Workers 에는 시작 로그가 없어 그 엔드포인트가 로그를 대신한다.

버전을 올린 뒤 태그를 달고 릴리즈를 낸다.

```bash
git tag -a v0.7.0 <sha> -m "<한 줄 요약>"
git push --tags
gh release create v0.7.0 --notes "..."
```

---

## 9. 아직 정하지 않은 것 — CD

지금 API 배포는 사람이 명령을 친다. 자동화하는 길이 셋 있다.

| 안 | 언제 나가나 | 평 |
|---|---|---|
| **A** | `main` 에 머지되면 바로 | 가장 빠르다. 마이그레이션도 사람 확인 없이 돈다 |
| **B** | 머지 뒤 사람이 승인하면 | GitHub Environment 승인. 공개 저장소라 무료다. 앱으로 알림이 오고 앱에서 누를 수 있다 |
| **C** | 릴리즈 태그를 달면 | 지금 프로세스와 맞는다 |

무엇을 고르든 **GitHub Actions 가 배포하면 7번 문제가 함께 풀린다.** 깨끗하게 새로
받아서 배포하므로 작업 폴더가 섞이지 않는다.

필요한 것은 `CLOUDFLARE_API_TOKEN` 하나를 GitHub 비밀값으로 넣는 것이다. 토큰에
필요한 권한은 셋 — Workers Scripts(Edit), D1(Edit), Account Settings(Read).

**지금 안 하는 까닭.** 개발 서버가 없어 머지가 곧 운영이다. CI 가 방금 붙어 깨진
코드는 머지되지 않지만, 마이그레이션이 사람 확인 없이 도는 것은 여전히 걸린다.

---

## 되돌리기

| 무엇 | 어떻게 |
|---|---|
| 코드 | 이전 버전을 다시 배포한다. `deploy.sh` 를 그 시점 코드에서 돌린다 |
| **마이그레이션** | **되돌리는 길이 없다.** 새 마이그레이션으로 고친다 |
| 화면 | `gh workflow run collect --ref <이전 태그>` |

마이그레이션이 되돌릴 수 없다는 것이 배포에서 가장 조심할 자리다.

---

## 새 규칙을 더할 때

1. 무엇을 정했는지 한 줄
2. **왜** 그렇게 정했는지. 견준 다른 안이 있으면 그것도
3. 되돌리려면 무엇을 치르는지
