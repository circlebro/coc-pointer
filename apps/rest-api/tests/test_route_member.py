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
        "display_name": None,
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
        "synced_at": NOW,
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

    body = client.get("/api/v1/members", params={"includes": "profile"}).json()

    assert [m["profile"]["name"] for m in body["members"]] == ["도토리", "히로"]


def test_스펙대로_캐멀케이스로_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", role=ClanRole.ADMIN)])

    member = client.get("/api/v1/members", params={"includes": "profile"}).json()["members"][0]

    assert member["externalId"] == "#A"
    assert member["status"] == "ACTIVE"
    assert member["createdAt"] == NOW
    assert member["profile"]["role"] == "ADMIN"
    assert member["profile"]["donationsReceived"] == 50
    assert "donations_received" not in member["profile"]


def test_외부_식별자로_좁힌다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    body = client.get("/api/v1/members", params={"externalId": "#B"}).json()

    assert [m["externalId"] for m in body["members"]] == ["#B"]


def test_없는_식별자면_빈_목록(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.get("/api/v1/members", params={"externalId": "#없음"}).json()

    assert body == {"members": []}


def test_우리_식별자로_한_명을_준다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리"), _member("#B", "히로")])

    response = client.get("/api/v1/members/uuid-B")

    assert response.status_code == 200
    assert response.json()["externalId"] == "#B"


def test_없는_식별자면_404(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.get("/api/v1/members/uuid-없음")

    assert response.status_code == 404
    assert "detail" in response.json()


def test_표기를_고친다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.patch(
        "/api/v1/members/uuid-A",
        json={"displayName": "도토리형", "description": "부캐 아님"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["displayName"] == "도토리형"
    assert body["description"] == "부캐 아님"
    assert client.get("/api/v1/members/uuid-A").json()["displayName"] == "도토리형"


def test_보내지_않은_값은_그대로다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", description="부캐 아님")])

    body = client.patch("/api/v1/members/uuid-A", json={"warnings": 2}).json()

    assert body["warnings"] == 2
    assert body["description"] == "부캐 아님"


def test_null_을_보내면_비운다(client, fake_db):
    """표기를 지우면 화면은 CoC 이름으로 돌아간다."""
    _seed(fake_db, [_member("#A", "도토리", display_name="도토리형")])

    body = client.patch("/api/v1/members/uuid-A", json={"displayName": None}).json()

    assert body["displayName"] is None


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
        params={"includes": "profile"},
        json={"warnings": 1, "name": "바뀐이름"},
    ).json()

    assert body["warnings"] == 1
    assert body["profile"]["name"] == "도토리"


def test_아는_값이_하나도_없으면_400(client, fake_db):
    """이름만 보낸 요청은 고칠 것이 없는 요청과 같다."""
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"name": "바뀐이름"}).status_code == 400


def test_고칠_값을_하나도_안_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={}).status_code == 400


def test_비울_수_없는_값에_null_을_보내면_400(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"warnings": None}).status_code == 400


def test_경고_횟수가_음수면_422(client, fake_db):
    """스펙이 minimum: 0 이라 생성 모델이 먼저 거른다."""
    _seed(fake_db, [_member("#A", "도토리")])

    assert client.patch("/api/v1/members/uuid-A", json={"warnings": -1}).status_code == 422


def test_등급은_고칠_수_없다(client, fake_db):
    """등급은 그달 점수가 정하는 값이라 수정 본문에 자리가 없다.

    모르는 키라 조용히 무시되고, 남은 값이 없으므로 400 이 된다.
    """
    _seed(fake_db, [_member("#A", "도토리", grade=MemberGrade.COMPETING)])

    assert client.patch("/api/v1/members/uuid-A", json={"grade": "FIXED"}).status_code == 400


def test_없는_사람을_고치면_404(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.patch("/api/v1/members/uuid-없음", json={"warnings": 1})

    assert response.status_code == 404


def test_기본_응답에는_profile_이_없다(client, fake_db):
    """키 자체가 없어야 한다. null 로 채우면 묻지 않은 것과 값이 없는 것이 같아 보인다."""
    _seed(fake_db, [_member("#A", "도토리")])

    member = client.get("/api/v1/members").json()["members"][0]

    assert "profile" not in member
    assert set(member) == {
        "id",
        "externalId",
        "displayName",
        "status",
        "warnings",
        "description",
        "createdAt",
        "updatedAt",
    }


def test_profile_을_부르면_CoC_값이_실린다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리", role=ClanRole.ADMIN)])

    member = client.get("/api/v1/members", params={"includes": "profile"}).json()["members"][0]

    assert member["profile"] == {
        "name": "도토리",
        "role": "ADMIN",
        "townhall": 16,
        "trophies": 4200,
        "donations": 100,
        "donationsReceived": 50,
        "fetchedAt": NOW,
    }


def test_한_명을_부를_때도_profile_을_고른다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    without = client.get("/api/v1/members/uuid-A").json()
    with_profile = client.get("/api/v1/members/uuid-A", params={"includes": "profile"}).json()

    assert "profile" not in without
    assert with_profile["profile"]["name"] == "도토리"


def test_고친_뒤에도_profile_을_고른다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.patch(
        "/api/v1/members/uuid-A",
        params={"includes": "profile"},
        json={"displayName": "도토리형"},
    ).json()

    assert body["displayName"] == "도토리형"
    assert body["profile"]["name"] == "도토리"


def test_모르는_includes_는_400(client, fake_db):
    """조용히 버리면 오타인지 값이 없는 것인지 부르는 쪽이 알 수 없다."""
    _seed(fake_db, [_member("#A", "도토리")])

    response = client.get("/api/v1/members", params={"includes": "standing"})

    assert response.status_code == 400
    assert "standing" in response.json()["detail"]


def test_빈_includes_는_기본_응답과_같다(client, fake_db):
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.get("/api/v1/members", params={"includes": ""}).json()

    assert "profile" not in body["members"][0]


def test_동기화_시각과_갱신_시각은_따로_움직인다(client, fake_db):
    """등급만 고쳤는데 'CoC 에서 방금 받았다'로 보이면 안 된다."""
    _seed(fake_db, [_member("#A", "도토리")])

    body = client.patch(
        "/api/v1/members/uuid-A",
        params={"includes": "profile"},
        json={"warnings": 1},
    ).json()

    assert body["updatedAt"] > NOW
    assert body["profile"]["fetchedAt"] == NOW
