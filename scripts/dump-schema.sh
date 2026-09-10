#!/usr/bin/env bash
# 마이그레이션을 적용한 결과를 apps/api/database/schema.sql 로 뽑는다.
#
#   ./scripts/dump-schema.sh
#
# schema.sql 은 손으로 쓰지 않는다. 마이그레이션이 유일한 원본이고 이 파일은
# 현재 구조를 한눈에 보기 위한 사본이다. 둘이 어긋나면 테스트가 잡는다.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

for f in apps/api/database/migrations/*.sql; do
  sqlite3 "$TMP" < "$f"
done

{
  echo "-- 이 파일은 마이그레이션에서 생성되었다. 손으로 고치지 마라."
  echo "-- 고치려면 apps/api/database/migrations/ 에 파일을 더하고"
  echo "-- ./scripts/dump-schema.sh 를 돌린다."
  echo
  sqlite3 "$TMP" .schema | grep -v '^CREATE TABLE sqlite_'
} > apps/api/database/schema.sql

echo "apps/api/database/schema.sql 갱신됨"
