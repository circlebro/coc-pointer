#!/usr/bin/env bash
# 로컬 실테스트에 쓸 apps/rest-api/.dev.vars 를 만든다.
#
#   ./scripts/dev-vars.sh
#
# 개발 서버가 따로 없어 배포하면 곧바로 운영이다. 그래서 PR 을 올리기 전에
# 로컬에서 진짜 Worker 를 띄워 진짜 CoC 를 불러 봐야 한다. 그때 필요한 값을
# 여기서 모은다.
#
# 담기는 값
#   COC_API_TOKEN    .env 에서 그대로 가져온다
#   CLAN_TAG         게임에서 누구나 보는 값이라 비밀이 아니다
#   ADMIN_PASSWORD   로컬에서만 쓰는 임시 값을 새로 만든다.
#                    Cloudflare 에 올라간 운영 비밀번호와 아무 상관이 없다
#
# 만들어진 파일은 .gitignore 에 들어 있다. 화면에 값을 찍지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "✘ .env 가 없습니다. COC_API_TOKEN 이 거기 있어야 합니다." >&2
  exit 1
fi

OUT="apps/rest-api/.dev.vars"

python3 - "$OUT" <<'PY'
import secrets
import sys
from pathlib import Path

out = Path(sys.argv[1])

token = ""
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    key, _, value = line.partition("=")
    if key.strip() == "COC_API_TOKEN":
        token = value.strip().strip('"').strip("'")

if not token:
    print("✘ .env 에 COC_API_TOKEN 이 없습니다.", file=sys.stderr)
    raise SystemExit(1)

# 로컬 전용 비밀번호. ASCII 만 쓴다 — HTTP 헤더에 담기기 때문이다.
password = secrets.token_urlsafe(16)

# 값을 따옴표로 감싼다. .dev.vars 에서 '#' 은 주석을 여는 글자라,
# CLAN_TAG=#2C8L822LQ 로 적으면 값이 통째로 사라진다. config/clan.yaml 이
# 같은 이유로 태그를 따옴표로 감싸고 있다.
out.write_text(
    f'COC_API_TOKEN="{token}"\n'
    f'CLAN_TAG="#2C8L822LQ"\n'
    f'ADMIN_PASSWORD="{password}"\n',
    encoding="utf-8",
)
out.chmod(0o600)
PY

echo "✔ $OUT 를 만들었습니다."
echo
echo "로컬에서 띄우려면:"
echo "  cd apps/rest-api"
echo "  npx wrangler@4 d1 migrations apply coc-pointer --local   # 처음 한 번"
echo "  npm run dev"
echo
echo "운영 표면을 부를 때 쓸 비밀번호는 그 파일의 ADMIN_PASSWORD 에 있습니다."
echo "Cloudflare 에 올라간 운영 비밀번호와는 아무 상관이 없습니다."
