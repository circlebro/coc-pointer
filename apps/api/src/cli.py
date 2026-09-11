"""명령줄에서 도는 일.

지금은 클랜원 동기화 하나뿐이다. 예약 실행(Cron)은 클랜전 수집을 옮길 때
함께 붙인다.

    cd apps/api && uv run python src/cli.py refresh-members

이 앱은 pyproject.toml 이 package = false 라 설치되지 않는다. Cloudflare
Workers 번들로 배포되기 때문이다. 그래서 진입점을 등록할 수 없고 파일을
직접 가리켜 부른다.

서버가 요청을 받아 조립하는 것과 같은 일을 여기서 한다. 조립하는 자리가
두 곳이 되지 않게 이 파일이 그 몫을 맡는다.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Any

import httpx
from coc_core.member.service import MemberService, SyncResult

from adapters.coc_api import CocApi
from adapters.member_repository import D1MemberRepository


async def refresh_members(
    db: Any,
    token: str,
    clan_tag: str,
    now: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SyncResult:
    """CoC API 에서 클랜원을 받아 D1 에 맞춘다."""
    coc_api = CocApi(token=token, clan_tag=clan_tag, transport=transport)
    try:
        service = MemberService(
            repository=D1MemberRepository(db),
            source=coc_api,
        )
        return await service.sync(now=now)
    finally:
        await coc_api.aclose()


def _now() -> str:
    """지금 시각. D1 연결이 정해지면 main 이 refresh_members 에 넘긴다."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    """진입점.

    D1 에 붙는 방법은 아직 정하지 않았다. 로컬에서는 wrangler 를 거치고
    Workers 안에서는 바인딩을 쓴다. 지금은 안내만 하고 빠진다.
    """
    if len(sys.argv) < 2 or sys.argv[1] != "refresh-members":
        print("쓰임: uv run python src/cli.py refresh-members")
        return 2

    token = os.environ.get("COC_API_TOKEN")
    if not token:
        print("COC_API_TOKEN 이 없습니다. 저장소 루트 .env 에 넣어 주세요.")
        return 1

    print("이 명령은 D1 연결이 필요합니다.")
    print("로컬 D1 로 시험하려면:")
    print("  cd apps/api && uv run pywrangler dev")
    print("배포된 D1 에 넣으려면 Cron 이 붙은 뒤에 서버가 스스로 합니다 (TASK-21).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
