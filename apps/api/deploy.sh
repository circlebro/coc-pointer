#!/usr/bin/env bash
# API 서버를 Cloudflare에 올린다.
#
#   ./apps/api/deploy.sh
#
# 인증은 저장소 루트 .env 의 CLOUDFLARE_API_TOKEN 으로 한다. Terraform 이 AWS
# 프로파일을 쓰는 것과 같은 방식이라, 한 번 발급해 넣어 두면 그다음부터는
# 브라우저 로그인 없이 돈다. .env 는 git 에 올리지 않는다.
#
# 처음 실행하면 데이터베이스를 만들고 표를 넣은 뒤 배포한다.
# 두 번째부터는 공용 코드를 새로 복사해 배포만 다시 한다.
set -euo pipefail
cd "$(dirname "$0")"

WRANGLER="npx --yes wrangler@4"

echo "== 1/5 Cloudflare 자격 확인 =="
ENV_FILE="../../.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  cat <<'GUIDE'
CLOUDFLARE_API_TOKEN 이 없습니다. 한 번만 발급해 두면 그다음부터는 자동으로 됩니다.

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
GUIDE
  exit 1
fi

export CLOUDFLARE_API_TOKEN
[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ] && export CLOUDFLARE_ACCOUNT_ID

if ! $WRANGLER whoami >/dev/null 2>&1; then
  echo "토큰으로 인증하지 못했습니다. 값과 권한을 확인해 주세요."
  echo "권한 세 줄이 모두 있어야 합니다: Workers Scripts(Edit), D1(Edit), Account Settings(Read)"
  exit 1
fi
echo "토큰으로 인증했습니다. 브라우저 로그인은 필요 없습니다."

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
echo "끝났습니다. 위에 보이는 주소 뒤에 두 곳을 붙여 열어 보세요."
echo
echo "  /api/health         coc_core 가 ok 이고 표 여덟 개가 보이면 성공"
echo "  /api/health/crypto  비밀번호 해시를 무료 플랜으로 할 수 있는지 판정"
