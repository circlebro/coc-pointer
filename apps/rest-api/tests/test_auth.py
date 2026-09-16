"""운영 표면을 지키는 검사.

임시 조치다. 제대로 된 로그인이 오면 auth.py 를 갈아 끼우고 이 파일도 함께
다시 쓴다. 그때까지 지켜야 할 것을 여기 적어 둔다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from worker import app

PASSWORD = "test-password"  # 테스트에서만 쓰는 값. 실제 값은 Worker 비밀값에 있다


class FakeEnv:
    API_VERSION = "0.7.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"
    ADMIN_PASSWORD = PASSWORD

    def __init__(self, db) -> None:
        self.DB = db


def _client(fake_db, **overrides) -> TestClient:
    env = FakeEnv(fake_db)
    for key, value in overrides.items():
        setattr(env, key, value)

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    return TestClient(with_env)


# 운영 표면의 모든 경로. 새 경로가 늘면 여기도 늘려야 한다 —
# test_route_member.py 가 공개 표면에 고치는 경로가 없는지 따로 본다.
ADMIN_CALLS = [
    ("patch", "/api/v1/admin/members/아무거나"),
    ("post", "/api/v1/admin/members:sync"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
def test_비밀번호_없이는_막는다(fake_db, method: str, path: str) -> None:
    response = _client(fake_db).request(method, path, json={"warnings": 1})

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
def test_틀린_비밀번호도_막는다(fake_db, method: str, path: str) -> None:
    """틀린 값은 ASCII 로 적는다. HTTP 헤더에 한글을 담을 수 없기 때문이다 —
    비밀번호도 같은 제약을 받는다는 뜻이고, 아래 테스트가 그것을 지킨다."""
    response = _client(fake_db).request(
        method, path, json={"warnings": 1}, headers={"X-Admin-Password": "wrong"}
    )

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_CALLS)
def test_비밀값이_없으면_모두_막는다(fake_db, method: str, path: str) -> None:
    """열어 두는 쪽으로 기울면, 설정을 빠뜨린 배포가 조용히 운영 표면을 공개한다."""
    client = _client(fake_db, ADMIN_PASSWORD=None)

    response = client.request(
        method, path, json={"warnings": 1}, headers={"X-Admin-Password": PASSWORD}
    )

    assert response.status_code == 503
    assert "비밀번호가 설정되지" in response.json()["detail"]


def test_맞는_비밀번호는_통과한다(fake_db) -> None:
    """401 이 아니면 검사를 지난 것이다. 그 뒤 결과는 경로마다 다르다."""
    response = _client(fake_db).patch(
        "/api/v1/admin/members/없는-uuid",
        json={"warnings": 1},
        headers={"X-Admin-Password": PASSWORD},
    )

    assert response.status_code == 404  # 검사는 지났고, 그런 클랜원이 없을 뿐이다


def test_공개_표면은_비밀번호를_묻지_않는다(fake_db) -> None:
    assert _client(fake_db).get("/api/v1/public/members").status_code == 200


def test_비밀번호는_ASCII_여야_한다(fake_db) -> None:
    """HTTP 헤더는 ASCII 만 담는다.

    한글 비밀번호를 정하면 브라우저가 요청을 보내지도 못한다. 서버가 거부하는
    것이 아니라 아예 나가지 않으므로, 쓰는 사람은 무엇이 잘못됐는지 알 길이
    없다. 화면 쪽에서도 같은 것을 막는다.
    """
    client = _client(fake_db, ADMIN_PASSWORD="비밀번호")

    with pytest.raises(Exception, match="ascii|encode|Header"):
        client.post(
            "/api/v1/admin/members:sync",
            headers={"X-Admin-Password": "비밀번호"},
        )
