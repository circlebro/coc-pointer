#!/usr/bin/env bash
# 리그전 보상 추첨 서버를 Cloudflare에 올린다.
#
#   ./apps/api/deploy.sh
#
# 처음 실행하면 브라우저가 열려 Cloudflare 로그인을 묻고, 저장소(KV)를 만들고,
# 서버를 배포한 뒤 비밀번호를 물어본다. 두 번째부터는 배포만 다시 한다.
set -euo pipefail
cd "$(dirname "$0")"

WRANGLER="npx --yes wrangler@4"

echo "== 1/4 Cloudflare 로그인 확인 =="
if ! $WRANGLER whoami >/dev/null 2>&1; then
  echo "브라우저가 열립니다. Cloudflare 계정으로 허용해 주세요."
  $WRANGLER login
fi
$WRANGLER whoami | grep -i "account" || true

echo
echo "== 2/4 저장소(KV) 준비 =="
if grep -q "PUT_KV_ID_HERE" wrangler.toml; then
  echo "coc-draws 저장소를 만듭니다."
  # 출력에서 id를 뽑아 wrangler.toml에 채워 넣는다.
  created=$($WRANGLER kv namespace create DRAWS 2>&1 | tee /dev/stderr)
  kv_id=$(printf '%s' "$created" | grep -oE '"?id"?[[:space:]]*[:=][[:space:]]*"[0-9a-f]{32}"' | grep -oE '[0-9a-f]{32}' | head -1)
  if [ -z "$kv_id" ]; then
    echo
    echo "저장소 id를 자동으로 찾지 못했습니다. 위 출력에서 32자리 id를 복사해"
    echo "apps/api/wrangler.toml의 PUT_KV_ID_HERE 자리에 넣고 다시 실행해 주세요."
    exit 1
  fi
  perl -pi -e "s/PUT_KV_ID_HERE/$kv_id/" wrangler.toml
  echo "저장소 id를 wrangler.toml에 기록했습니다: $kv_id"
else
  echo "이미 준비되어 있습니다."
fi

echo
echo "== 3/4 서버 배포 =="
$WRANGLER deploy

echo
echo "== 4/4 비밀번호 설정 =="
echo "추첨과 다시 뽑기에 쓸 비밀번호를 정합니다. 화면에 보이지 않게 입력됩니다."
echo "이미 정해 두었고 그대로 두려면 Ctrl+C로 빠져나오세요."
$WRANGLER secret put ADMIN_PASSWORD

echo
echo "끝났습니다. 위에 보이는 https://coc-draw.....workers.dev 주소를 알려 주세요."
