"""엔드포인트가 올바른 응답을 내는지 확인한다.

Workers 런타임 없이 FastAPI 만 띄워 확인한다. D1 자리에는 Task 1 의 가짜를,
환경 변수 자리에는 아래 FakeEnv 를 끼운다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from worker import app, get_db, get_env


class FakeEnv:
    API_VERSION = "0.5.0"


@pytest.fixture
def client(fake_db):
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_env] = lambda: FakeEnv()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_는_표_목록과_판을_알려준다(client):
    body = client.get("/api/health").json()

    assert body["version"] == "0.5.0"
    assert body["coc_core"] == "ok"
    assert "monthly_scores" in body["tables"]


def test_health_는_공용_코드가_도는지_확인한다(client):
    body = client.get("/api/health").json()

    # 점수 규칙을 실제로 읽어 왔다면 개수가 0 이 아니다
    assert body["rules"] > 0
    # 한국 시간이 계산되었다면 날짜 모양이다
    assert len(body["kst_now"]) == 16


def test_점수가_없는_달은_빈_목록(client):
    body = client.get("/api/scores/2026-09").json()

    assert body == {"month": "2026-09", "members": []}


def test_점수를_높은_순으로_돌려준다(client, fake_db):
    import asyncio

    async def seed():
        for tag, name, attacks, stars, score in [
            ("#AAA", "도토리", 10, 25, 87.5),
            ("#BBB", "히로", 12, 30, 93.75),
        ]:
            await (
                fake_db.prepare(
                    "INSERT INTO monthly_scores "
                    "(month, tag, name, attacks, stars, score, computed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)"
                )
                .bind("2026-09", tag, name, attacks, stars, score, "2026-09-10T00:00:00Z")
                .run()
            )

    asyncio.run(seed())

    body = client.get("/api/scores/2026-09").json()

    assert [m["name"] for m in body["members"]] == ["히로", "도토리"]


def test_뽑지_않은_달은_drawn_이_거짓(client):
    body = client.get("/api/draws/2026-09").json()

    assert body == {"month": "2026-09", "drawn": False}
