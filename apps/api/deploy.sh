#!/usr/bin/env bash
# API 서버를 Cloudflare에 올린다.
#
#   ./apps/api/deploy.sh
#
# FastAPI 는 서드파티 패키지라, 그냥 `wrangler deploy` 로는 번들에 들어가지
# 않는다(런타임에서 import fastapi 가 실패한다). pyproject.toml 의 의존성을
# 읽어 번들에 넣는 `pywrangler`(devDependency `workers-py`)를 거쳐야 한다.
# `uv run pywrangler` 가 내부적으로 항상 `npx --yes wrangler` 를 부르므로,
# 버전을 고정하려면 package.json 에 wrangler 를 못 박고 npm install 로
# node_modules 에 받아 둬야 한다 — npx 는 로컬 설치본을 우선한다.
#
# 처음 실행하면 데이터베이스를 만들고 표를 넣은 뒤 배포한다.
# 두 번째부터는 공용 코드를 새로 복사해 배포만 다시 한다.
set -euo pipefail
cd "$(dirname "$0")"

WRANGLER="uv run pywrangler"

echo "== 1/5 Cloudflare 자격 확인 =="
ENV_FILE="../../.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  # API 토큰: CI/자동 배포용. AWS 로 치면 정적 자격 증명에 해당한다.
  export CLOUDFLARE_API_TOKEN
  [ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ] && export CLOUDFLARE_ACCOUNT_ID
  if ! $WRANGLER whoami >/dev/null 2>&1; then
    echo "토큰으로 인증하지 못했습니다. 값과 권한을 확인해 주세요."
    echo "권한 세 줄이 모두 있어야 합니다: Workers Scripts(Edit), D1(Edit), Account Settings(Read)"
    exit 1
  fi
  echo ".env 의 API 토큰으로 인증했습니다."
elif $WRANGLER whoami >/dev/null 2>&1; then
  # wrangler login 으로 이미 인증된 상태. AWS 로 치면 `aws sso login` 이 남겨
  # 둔 자격 증명에 해당한다 — ~/.config/.wrangler/ 에 저장되어 있으면 그대로
  # 쓰인다. 토큰을 새로 만들 필요가 없어 지금 단계에서는 이쪽이 더 간단하다.
  echo "이미 로그인되어 있습니다."
else
  echo "인증된 것이 없습니다."
  if [ -t 0 ] && [ -t 1 ]; then
    cat <<'GUIDE'

두 가지 방법이 있습니다.

  A. wrangler login — 지금 당장은 이쪽이 더 간단합니다. 브라우저가 열리고
     승인하면 끝입니다. 웹에서 권한을 골라 토큰을 만들 필요가 없습니다.
  B. CLOUDFLARE_API_TOKEN — GitHub Actions 처럼 브라우저가 없는 곳에서
     자동으로 배포하게 되면 이쪽이 필요합니다. 발급 방법은 아래와 같습니다.

       1. https://dash.cloudflare.com/profile/api-tokens 를 연다
       2. Create Token → Create Custom Token 을 고른다
       3. 이름은 아무거나 (예: coc-pointer-deploy)
       4. Permissions 에 세 줄을 넣는다
            Account | Workers Scripts  | Edit
            Account | D1               | Edit
            Account | Account Settings | Read
       5. Account Resources 는 본인 계정만 고른다
       6. 만들어진 토큰을 복사해 저장소 루트 .env 에 이 줄로 넣는다
            CLOUDFLARE_API_TOKEN=복사한값
       7. 이 스크립트를 다시 실행한다

     계정이 여러 개면 CLOUDFLARE_ACCOUNT_ID 도 함께 넣는다.
     .env 는 git 에 올라가지 않는다.

지금 wrangler login 을 실행합니다. 브라우저가 열립니다.
GUIDE
    $WRANGLER login
    if ! $WRANGLER whoami >/dev/null 2>&1; then
      echo "로그인에 실패했습니다. 다시 실행해 주세요."
      exit 1
    fi
    echo "로그인했습니다."
  else
    cat <<'GUIDE'
브라우저를 열 수 없는 환경이라 wrangler login 을 자동으로 실행하지 않습니다.

  대화형 터미널에서 이 스크립트를 다시 실행해 wrangler login 을 하거나,
  CLOUDFLARE_API_TOKEN 을 저장소 루트 .env 에 넣어 주세요.
GUIDE
    exit 1
  fi
fi

echo
echo "== 2/5 데이터베이스 준비 =="
if grep -q "PUT_D1_ID_HERE" wrangler.toml; then
  echo "coc-pointer 데이터베이스를 만듭니다."
  created=$($WRANGLER d1 create coc-pointer 2>&1 | tee /dev/stderr)
  d1_id=$(printf '%s' "$created" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
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
# D1 이 어디까지 적용했는지 스스로 기록한다(d1_migrations 표). 이미 적용한
# 파일은 건너뛰므로 여러 번 돌려도 안전하다.
# 확인을 묻는 단계가 있지만 -y 같은 플래그는 없다. 사람이 지켜보는 터미널이
# 아니면 wrangler 가 그 단계를 알아서 건너뛴다. 적용한 뒤에는 백업이 남는다.
$WRANGLER d1 migrations apply coc-pointer --remote

echo
echo "== 4/5 공용 코드 복사 =="
# coc_core 는 PyPI 에 없는 로컬 전용 패키지라 pywrangler 가 대신 받아 줄 수
# 없으므로 소스를 그대로 복사해 올린다. (fastapi 같은 PyPI 패키지는
# pywrangler deploy 가 pyproject.toml 을 읽어 알아서 번들에 넣는다.)
rm -rf src/coc_core
cp -R ../../packages/core/src/coc_core src/coc_core
echo "packages/core → src/coc_core"

echo
echo "== 5/5 배포 =="
if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
  # wrangler 버전을 package.json 에 못 박아 두었다. pywrangler 가 부르는
  # `npx --yes wrangler` 는 로컬 node_modules 를 우선하므로, 미리 받아 두면
  # 매번 레지스트리에서 최신판을 새로 받는 대신 고정된 버전이 쓰인다.
  npm install --silent
fi
$WRANGLER deploy

# 번들에 실렸으므로 로컬에 남길 이유가 없다. 남아 있으면 테스트가 이 사본을
# 진짜 소스로 착각한다(pythonpath 에 apps/api/src 가 들어가기 때문).
rm -rf src/coc_core

echo
echo "끝났습니다. 위에 보이는 주소 뒤에 두 곳을 붙여 열어 보세요."
echo
echo "  /api/health         coc_core 가 ok 이고 표 여덟 개가 보이면 성공"
echo "  /api/health/crypto  비밀번호 해시를 무료 플랜으로 할 수 있는지 판정"

if ! git diff --quiet -- wrangler.toml 2>/dev/null; then
  echo
  echo "!! apps/api/wrangler.toml 의 database_id 가 바뀌었습니다."
  echo "!! 커밋하지 않으면 다음 클론이나 다른 워크트리가 데이터베이스를 새로 만듭니다."
  echo "!! git add apps/api/wrangler.toml 로 커밋해 주세요."
fi
