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

uv run ruff format apps/api/src/schemas.py >/dev/null

echo "== 프론트 타입 (TypeScript) =="
mkdir -p apps/web/src/api
npx --yes openapi-typescript@7 "$CONTRACT" -o apps/web/src/api/schema.d.ts
echo "  → apps/web/src/api/schema.d.ts"

echo
echo "생성이 끝났습니다. 바뀐 것이 있으면 함께 커밋하세요."
