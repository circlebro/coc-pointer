"""클랜원 경로."""

from __future__ import annotations

import asyncio

import pytest
from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus
from fastapi.testclient import TestClient

from adapters.member_repository import D1MemberRepository
from worker import app

NOW = "2026-09-10T05:30:00Z"


class FakeEnv:
    API_VERSION = "0.5.0"
    COC_API_TOKEN = "test-token"
    CLAN_TAG = "#2C8L822LQ"

    def __init__(self, db) -> None:
        self.DB = db


def _member(external_id: str, name: str, **overrides) -> ClanMember:
    base = {
        "id": f"uuid-{external_id.lstrip('#')}",
        "external_id": external_id,
        "name": name,
        "role": ClanRole.MEMBER,
        "status": MemberStatus.ACTIVE,
        "grade": MemberGrade.COMPETING,
        "grade_reason": None,
        "warnings": 0,
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donations_received": 50,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


@pytest.fixture
def client(fake_db):
    """실제 Workers 처럼 scope 에 env 를 넣어 주는 얇은 래퍼로 앱을 감싼다."""
    env = FakeEnv(fake_db)

    async def with_env(scope, receive, send):
        scope["env"] = env
        await app(scope, receive, send)

    return TestClient(with_env)


def _seed(fake_db, members):
    asyncio.run(D1MemberRepository(fake_db).upsert_many(members))


def test_아무도_없으면_빈_목록(client):
    body = client.get("/api/v1/members").json()

    assert body == {"members": []}


def test_이름_순으로_돌려준다(client, fake_db):
    _seed(fake_db, [_member("#B", "히로"), _member("#A", "도토리")])

    body = client.get("/api/v1/members").json()

    assert [m["name"] for m in body["members"]] == ["도토리", "히로"]


def test_스펙대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", role=ClanRole.ADMIN)])

    member = client.get("/api/v1/members").json()["members"][0]

    assert member["externalId"] == "#A"
    assert member["role"] == "ADMIN"
    assert member["status"] == "ACTIVE"
    assert member["donationsReceived"] == 50
    assert member["createdAt"] == NOW
    assert "donations_received" not in member


def test_외부_식별자로_좁힌다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    body = client.get("/api/v1/members", params={"externalId": "#B"}).json()

    assert [m["name"] for m in body["members"]] == ["히로"]


def test_없는_식별자면_빈_목록(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.get("/api/v1/members", params={"externalId": "#없음"}).json()

    assert body == {"members": []}


def test_우리_식별자로_한_명을_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    response = client.get("/api/v1/members/uuid-B")

    assert response.status_code == 200
    assert response.json()["name"] == "히로"


def test_없는_식별자면_404(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.get("/api/v1/members/uuid-없음")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_등급을_고친다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.patch(
        "/api/v1/members/uuid-A",
        json={"grade": "FIXED", "gradeReason": "길드장"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["grade"] == "FIXED"
    assert body["gradeReason"] == "길드장"
    assert client.get("/api/v1/members/uuid-A").json()["grade"] == "FIXED"


def test_보내지_않은_값은_그대로다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", description="부캐 아님")])

    body = client.patch("/api/v1/members/uuid-A", json={"warnings": 2}).json()

    assert body["warnings"] == 2
    assert body["description"] == "부캐 아님"


def test_null_을_보내면_비운다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", grade_reason="길드장")])

    body = client.patch("/api/v1/members/uuid-A", json={"gradeReason": None}).json()

    assert body["gradeReason"] is None


def test_고친_뒤_갱신_시각이_올라간다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.patch("/api/v1/members/uuid-A", json={"warnings": 1}).json()

    assert body["updatedAt"] > NOW
    assert body["createdAt"] == NOW


def test_CoC_가_주인인_값은_고칠_수_없다(client, fake_db):
    """이름을 보내도 무시한다. 받아 주면 다음 동기화가 되돌려 놓는다."""
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.patch(
        "/api/v1/members/uuid-A",
        json={"grade": "FIXED", "name": "바뀐이름"},
    ).json()

    assert body["grade"] == "FIXED"
    assert body["name"] == "도토리"


def test_아는_값이_하나도_없으면_400(client, fake_db):
    """이름만 보낸 요청은 고칠 것이 없는 요청과 같다."""
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"name": "바뀐이름"}).status_code == 400


def test_고칠_값을_하나도_안_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={}).status_code == 400


def test_비울_수_없는_값에_null_을_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"grade": None}).status_code == 400
    assert client.patch("/api/v1/members/uuid-A", json={"warnings": None}).status_code == 400


def test_경고_횟수가_음수면_422(client, fake_db):
    """스펙이 minimum: 0 이라 생성 모델이 먼저 거른다."""
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"warnings": -1}).status_code == 422


def test_모르는_등급이면_422(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"grade": "RESERVE"}).status_code == 422


def test_없는_사람을_고치면_404(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.patch("/api/v1/members/uuid-없음", json={"grade": "FIXED"})

    assert response.status_code == 404
