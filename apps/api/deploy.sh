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
