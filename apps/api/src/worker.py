"""리그전 보상 추첨과 점수 조회를 맡는 API 서버.

Cloudflare Python Workers 위에서 돈다. FastAPI 앱을 ``asgi.entrypoint`` 로 감싸면
Workers 가 들어온 요청을 그대로 넘겨주고, 바인딩과 비밀값은 요청의
``scope["env"]`` 에 붙어 온다.

점수 규칙은 여기 없다. 규칙은 packages/core 의 ``coc_core.scoring`` 한 곳에만 있다.
배포할 때 deploy.sh 가 coc_core 를 src/ 로 복사한다.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Path, Request
from fastapi.middleware.cors import CORSMiddleware

import db

app = FastAPI(
    title="coc-pointer API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://circlebro.github.io", "http://localhost:8000"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def get_env(request: Request) -> Any:
    """Workers 가 넘겨준 환경. 바인딩과 비밀값이 여기 붙어 있다.

    테스트에서는 dependency_overrides 로 가짜를 끼운다.
    """
    return request.scope["env"]


def get_db(request: Request) -> Any:
    """D1 바인딩."""
    return request.scope["env"].DB


# 의존성은 Annotated 로 적는다. Depends() 를 인자 기본값에 그대로 두면
# ruff 의 B008(인자 기본값에서 함수를 부르지 말 것)에 걸리기 때문이다.
Env = Annotated[Any, Depends(get_env)]
Db = Annotated[Any, Depends(get_db)]

# "YYYY-MM" 모양이 아니면 FastAPI 가 422 로 거른다. draws.month 가 기본 키라,
# 형식이 아닌 값이 그대로 키가 되는 것을 여기서 막는다. 두 경로가 같은 별칭을
# 쓴다.
Month = Annotated[str, Path(pattern=r"^\d{4}-\d{2}$")]


@app.get("/api/health")
async def health(env: Env, database: Db) -> dict:
    """배포가 제대로 되었는지 한 번에 확인한다.

    Pyodide 위에서 공용 코드가 도는지, 시간대 자료가 있는지, D1 이 붙었는지를
    각각 확인해 돌려준다. 하나라도 실패하면 그 자리에 이유가 적힌다.
    """
    result: dict = {"version": getattr(env, "API_VERSION", "unknown")}

    try:
        from coc_core.scoring import KST, RULES

        result["coc_core"] = "ok"
        result["rules"] = len(RULES)
        result["kst_now"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    except Exception as exc:  # 무엇이 왜 실패했는지 그대로 보여준다
        result["coc_core"] = f"실패: {type(exc).__name__}: {exc}"

    try:
        result["tables"] = await db.list_tables(database)
    except Exception as exc:
        result["tables"] = f"실패: {type(exc).__name__}: {exc}"

    return result


@app.get("/api/health/crypto")
async def health_crypto() -> dict:
    """비밀번호 해시에 쓸 방법이 이 환경에서 되는지 확인한다.

    비밀번호는 원문을 저장하지 않고 해시로 담는데, 안전한 해시는 일부러 느린
    계산을 수만 번 되풀이한다. 무료 플랜은 요청 한 건에 CPU 10밀리초뿐이라
    그 계산이 들어갈지 알 수 없다. 두 갈래를 재 본다.

    - ``js_crypto``: Workers 가 주는 브라우저 표준 암호 기능. 계산을 런타임이
      대신하므로 빠르다. 쓸 수 있으면 무료 플랜으로 간다
    - ``pbkdf2_100k_ms``: 파이썬만으로 10만 번 돌렸을 때 걸린 밀리초.
      10 이하면 파이썬 계산으로도 된다

    사용자 관리(TASK-23) 착수 전에 판정하려고 둔 임시 경로다. 판정한 뒤 지운다.
    """
    result: dict = {}

    try:
        import js

        result["js_crypto"] = hasattr(js.crypto, "subtle")
    except Exception as exc:  # 무엇이 왜 실패했는지 그대로 보여준다
        result["js_crypto"] = f"실패: {type(exc).__name__}: {exc}"

    try:
        import hashlib
        import time

        started = time.monotonic()
        hashlib.pbkdf2_hmac("sha256", b"test", b"salt", 100_000)
        result["pbkdf2_100k_ms"] = round((time.monotonic() - started) * 1000, 1)
    except Exception as exc:
        result["pbkdf2_100k_ms"] = f"실패: {type(exc).__name__}: {exc}"

    return result


@app.get("/api/scores/{month}")
async def get_scores(month: Month, database: Db) -> dict:
    """그달 점수표. 수집할 때 미리 계산해 둔 것을 읽기만 한다."""
    return {"month": month, "members": await db.get_monthly_scores(database, month)}


@app.get("/api/draws/{month}")
async def get_draw(month: Month, database: Db) -> dict:
    """그달 추첨 결과. 아직 뽑지 않았으면 ``drawn`` 이 거짓이다."""
    drawn = await db.get_draw(database, month)
    if drawn is None:
        return {"month": month, "drawn": False}
    return {"drawn": True, **drawn}


if sys.platform == "emscripten":
    # Pyodide(Workers 런타임) 위에서만 sys.platform 이 "emscripten" 이다. asgi
    # 모듈은 그 런타임에만 있으므로 여기서만 불러온다. 이 안에서 실패하면
    # 감싸지 않고 그대로 터뜨린다 — 감싸면 Default = None 인 채로 "배포 성공"
    # 이 되고, 그 뒤 모든 요청이 핸들러 없음으로 조용히 죽는다(C-1 이 재발한
    # 모습과 같다). 배포 로그에 실패가 시끄럽게 남아야 원인을 바로 안다.
    import asgi

    Default = asgi.entrypoint(app)
else:
    # 로컬(pytest, uv run 등)에는 asgi 모듈이 없다. FastAPI 앱만 쓰고
    # Default 는 만들지 않는다.
    Default = None
