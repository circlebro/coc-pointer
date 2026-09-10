"""리그전 보상 추첨과 점수 조회를 맡는 API 서버.

Cloudflare Python Workers 위에서 돈다. FastAPI 앱을 ``asgi.entrypoint`` 로 감싸면
Workers 가 들어온 요청을 그대로 넘겨주고, 바인딩과 비밀값은 요청의
``scope["env"]`` 에 붙어 온다.

점수 규칙은 여기 없다. 규칙은 packages/core 의 ``coc_core.scoring`` 한 곳에만 있다.
배포할 때 deploy.sh 가 coc_core 를 src/ 로 복사한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Request
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


@app.middleware("http")
async def stamp_version(request: Request, call_next):
    """어느 배포본이 답했는지 응답만 보고 알 수 있게 한다."""
    response = await call_next(request)
    env = request.scope.get("env")
    response.headers["X-Api-Version"] = getattr(env, "API_VERSION", "unknown")
    return response


@app.get("/api/health")
async def health(env: Any = Depends(get_env), database: Any = Depends(get_db)) -> dict:
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
    except Exception as exc:  # noqa: BLE001 - 무엇이 왜 실패했는지 그대로 보여준다
        result["coc_core"] = f"실패: {type(exc).__name__}: {exc}"

    try:
        result["tables"] = await db.list_tables(database)
    except Exception as exc:  # noqa: BLE001
        result["tables"] = f"실패: {type(exc).__name__}: {exc}"

    return result


@app.get("/api/scores/{month}")
async def get_scores(month: str, database: Any = Depends(get_db)) -> dict:
    """그달 점수표. 수집할 때 미리 계산해 둔 것을 읽기만 한다."""
    return {"month": month, "members": await db.get_monthly_scores(database, month)}


@app.get("/api/draws/{month}")
async def get_draw(month: str, database: Any = Depends(get_db)) -> dict:
    """그달 추첨 결과. 아직 뽑지 않았으면 ``drawn`` 이 거짓이다."""
    drawn = await db.get_draw(database, month)
    if drawn is None:
        return {"month": month, "drawn": False}
    return {"drawn": True, **drawn}


try:  # Workers 런타임에서만 있는 모듈이라 로컬 테스트에서는 건너뛴다
    import asgi

    Default = asgi.entrypoint(app)
except ImportError:  # pragma: no cover - 로컬에서는 FastAPI 앱만 쓴다
    Default = None
