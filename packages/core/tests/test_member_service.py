"""클랜원 서비스.

가짜 대역을 클래스로 만들어 넣는다. 모킹 라이브러리를 쓰지 않는다.
"""

from __future__ import annotations

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberProfile, MemberStatus
from coc_core.member.service import MemberService

NOW = "2026-09-10T05:30:00Z"
LATER = "2026-09-14T09:00:00Z"


class FakeSource:
    """CoC API 대역. 받아 온 그대로의 값을 흉내낸다."""

    def __init__(self, raw: list[dict]) -> None:
        self.raw = raw

    async def fetch_members(self) -> list[dict]:
        return self.raw


class FakeProfiles:
    """현황을 읽어 오는 곳의 대역."""

    def __init__(self, profiles: dict[str, MemberProfile] | None = None) -> None:
        self.profiles = profiles or {}
        self.asked: list[str] = []

    async def read_clan_profiles(self) -> dict[str, MemberProfile]:
        return dict(self.profiles)

    async def read_profile(self, external_id: str) -> MemberProfile | None:
        self.asked.append(external_id)
        return self.profiles.get(external_id)


class FakeRepository:
    """저장소 대역. 태그를 열쇠로 담아 둔다."""

    def __init__(self, existing: list[ClanMember] | None = None) -> None:
        self.rows: dict[str, ClanMember] = {m.external_id: m for m in (existing or [])}
        self.marked_inactive: list[str] = []

    async def find_all(self) -> list[ClanMember]:
        return list(self.rows.values())

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        return next((m for m in self.rows.values() if m.id == member_id), None)

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        return self.rows.get(external_id)

    async def register_many(self, members: list[ClanMember]) -> int:
        """실제 저장소처럼 status 와 시각만 올린다.

        사람이 적은 값을 함께 덮으면, 서비스가 그것을 건드려도 테스트가
        알아채지 못한다.
        """
        added = 0
        for m in members:
            before = self.rows.get(m.external_id)
            if before is None:
                added += 1
                self.rows[m.external_id] = m
                continue
            self.rows[m.external_id] = ClanMember(
                **{
                    **before.__dict__,
                    "status": m.status,
                    "updated_at": m.updated_at,
                    "synced_at": m.synced_at,
                }
            )
        return added

    async def update_managed(self, member: ClanMember) -> None:
        """실제 저장소처럼 사람이 정하는 값과 갱신 시각만 덮는다."""
        before = self.rows[member.external_id]
        self.rows[member.external_id] = ClanMember(
            **{
                **before.__dict__,
                "display_name": member.display_name,
                "warnings": member.warnings,
                "description": member.description,
                "updated_at": member.updated_at,
            }
        )

    async def mark_inactive(self, tags: list[str], now: str) -> int:
        for tag in tags:
            row = self.rows.get(tag)
            if row is not None:
                self.rows[tag] = ClanMember(**{**row.__dict__, "status": MemberStatus.INACTIVE})
                self.marked_inactive.append(tag)
        return len(tags)


def _raw(tag: str, name: str, role: str = "member") -> dict:
    """CoC 가 준 그대로. 바깥 표기라 tag 를 쓴다 — 우리 이름은 external_id 다."""
    return {
        "tag": tag,
        "name": name,
        "role": role,
        "townHallLevel": 16,
        "trophies": 4200,
        "donations": 100,
        "donationsReceived": 50,
    }


def _member(**overrides) -> ClanMember:
    """저장소에 이미 담겨 있는 클랜원 한 명."""
    base = {
        "id": "uuid-1",
        "external_id": "#A",
        "display_name": None,
        "status": MemberStatus.ACTIVE,
        "warnings": 0,
        "description": None,
        "created_at": NOW,
        "updated_at": NOW,
        "synced_at": NOW,
    }
    base.update(overrides)
    return ClanMember(**base)


def _profile(tag: str = "#A", name: str = "도토리") -> MemberProfile:
    return MemberProfile(
        external_id=tag,
        name=name,
        role=ClanRole.MEMBER,
        townhall=16,
        trophies=4200,
        donations=100,
        donations_received=50,
        fetched_at=LATER,
    )


# ---------------------------------------------------------------- 동기화


async def test_처음_보는_사람을_등록한다():
    repository = FakeRepository()
    source = FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")])

    result = await MemberService(repository, source).sync(now=NOW)

    assert result.total == 2
    assert result.added == 2
    assert sorted(repository.rows) == ["#A", "#B"]


async def test_이미_있는_사람은_다시_세지_않는다():
    repository = FakeRepository([_member()])
    source = FakeSource([_raw("#A", "도토리")])

    result = await MemberService(repository, source).sync(now=LATER)

    assert result.added == 0
    assert repository.rows["#A"].created_at == NOW  # 처음 본 시각은 한 번만 정해진다
    assert repository.rows["#A"].synced_at == LATER


async def test_명단에서_사라지면_INACTIVE_로_내린다():
    """지우지 않는다. 과거 기록에 그 사람이 남아 있기 때문이다."""
    repository = FakeRepository([_member(), _member(id="uuid-2", external_id="#B")])
    source = FakeSource([_raw("#A", "도토리")])

    result = await MemberService(repository, source).sync(now=LATER)

    assert result.left == 1
    assert repository.marked_inactive == ["#B"]
    assert repository.rows["#B"].status is MemberStatus.INACTIVE


async def test_이미_내려간_사람을_또_내리지_않는다():
    repository = FakeRepository([_member(status=MemberStatus.INACTIVE)])
    source = FakeSource([])

    result = await MemberService(repository, source).sync(now=LATER)

    assert result.left == 0
    assert repository.marked_inactive == []


async def test_동기화는_사람이_적은_값을_덮지_않는다():
    """표기·경고·메모는 사람이 적는 값이다. 30분마다 도는 동기화가 덮으면 지워진다."""
    repository = FakeRepository(
        [_member(display_name="도토리형", warnings=2, description="부캐 아님")]
    )
    source = FakeSource([_raw("#A", "바뀐이름")])

    await MemberService(repository, source).sync(now=LATER)

    after = repository.rows["#A"]
    assert after.display_name == "도토리형"
    assert after.warnings == 2
    assert after.description == "부캐 아님"


async def test_처음_보는_사람의_표기는_비어_있다():
    """동기화가 CoC 이름으로 채우면, 사람이 정한 것인지 구분할 수 없다."""
    repository = FakeRepository()
    source = FakeSource([_raw("#A", "도토리")])

    await MemberService(repository, source).sync(now=NOW)

    assert repository.rows["#A"].display_name is None


async def test_source_없이_동기화하면_막는다():
    with pytest.raises(RuntimeError):
        await MemberService(FakeRepository()).sync(now=NOW)


# ---------------------------------------------------------------- 현황


async def test_클랜_현황은_한_번에_받는다():
    profiles = FakeProfiles({"#A": _profile()})
    service = MemberService(FakeRepository(), profiles=profiles)

    got = await service.read_clan_profiles()

    assert got["#A"].name == "도토리"
    assert profiles.asked == []  # 한 명씩 묻지 않는다


async def test_한_명의_현황을_묻는다():
    profiles = FakeProfiles({"#A": _profile()})
    service = MemberService(FakeRepository(), profiles=profiles)

    got = await service.read_profile("#A")

    assert got is not None
    assert got.name == "도토리"
    assert profiles.asked == ["#A"]


async def test_계정이_사라졌으면_None():
    """없는 이름을 지어내지 않는다."""
    service = MemberService(FakeRepository(), profiles=FakeProfiles())

    assert await service.read_profile("#없음") is None


async def test_profiles_없이_현황을_청하면_막는다():
    with pytest.raises(RuntimeError):
        await MemberService(FakeRepository()).read_clan_profiles()


# ---------------------------------------------------------------- 수정


async def test_보낸_값만_바꾼다():
    """경고만 올리는 요청이 관리자 메모까지 지우면 안 된다."""
    repository = FakeRepository([_member(description="부캐 아님", display_name="도토리형")])

    after = await MemberService(repository).update_managed("uuid-1", LATER, warnings=2)

    assert after is not None
    assert after.warnings == 2
    assert after.description == "부캐 아님"
    assert after.display_name == "도토리형"
    assert after.updated_at == LATER


async def test_None_을_보내면_비운다():
    """'안 보냈다'와 '비워 달라'는 다른 요청이다."""
    repository = FakeRepository([_member(display_name="도토리형")])

    after = await MemberService(repository).update_managed("uuid-1", LATER, display_name=None)

    assert after is not None
    assert after.display_name is None


async def test_고친_값이_저장소에_남는다():
    repository = FakeRepository([_member()])

    await MemberService(repository).update_managed(
        "uuid-1", LATER, display_name="도토리형", description="쉬는 계정"
    )

    saved = repository.rows["#A"]
    assert saved.display_name == "도토리형"
    assert saved.description == "쉬는 계정"


async def test_수정은_동기화_시각을_건드리지_않는다():
    """메모만 고쳤는데 'CoC 에서 방금 받았다'로 보이면 안 된다."""
    repository = FakeRepository([_member()])

    after = await MemberService(repository).update_managed("uuid-1", LATER, warnings=1)

    assert after is not None
    assert after.updated_at == LATER
    assert after.synced_at == NOW


async def test_없는_식별자면_None():
    repository = FakeRepository([_member()])

    assert await MemberService(repository).update_managed("없는-uuid", LATER) is None


async def test_경고_횟수는_음수가_될_수_없다():
    repository = FakeRepository([_member()])

    with pytest.raises(ValueError):
        await MemberService(repository).update_managed("uuid-1", LATER, warnings=-1)

    assert repository.rows["#A"].warnings == 0
