"""클랜원 서비스.

가짜 대역을 클래스로 만들어 넣는다. 모킹 라이브러리를 쓰지 않는다.
"""

from __future__ import annotations

import pytest

from coc_core.member.models import ClanMember, ClanRole, MemberGrade, MemberStatus
from coc_core.member.service import MemberService

NOW = "2026-09-10T05:30:00Z"


class FakeSource:
    """CoC API 대역. 받아 온 그대로의 값을 흉내낸다."""

    def __init__(self, raw: list[dict]) -> None:
        self.raw = raw

    async def fetch_members(self) -> list[dict]:
        return self.raw


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

    async def update_managed(self, member: ClanMember) -> None:
        """실제 저장소처럼 사람이 정하는 값과 갱신 시각만 덮는다.

        CoC 가 주인인 열을 함께 덮으면, 서비스가 그것을 건드려도 테스트가
        알아채지 못한다.
        """
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

    async def upsert_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            if m.external_id not in self.rows:
                added += 1
            self.rows[m.external_id] = m
        return added

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


async def test_처음_동기화하면_모두_새로_들어온다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.added == 2
    assert result.left == 0
    assert len(await service.find_all()) == 2


async def test_모르는_직책이_와도_나머지는_저장된다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리", "veteran"), _raw("#B", "히로", "member")]),
    )

    result = await service.sync(now=NOW)

    assert result.total == 2
    assert result.unknown_roles == {"veteran": 1}
    by_tag = {m.external_id: m for m in await service.find_all()}
    assert by_tag["#A"].role == ClanRole.UNKNOWN
    assert by_tag["#B"].role == ClanRole.MEMBER


async def test_목록에서_사라지면_INACTIVE_로_내린다():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)

    service_after = MemberService(repository=repository, source=FakeSource([]))
    result = await service_after.sync(now=NOW)

    assert result.left == 1
    assert repository.rows["#A"].status == MemberStatus.INACTIVE
    assert repository.rows["#A"].external_id == "#A"  # 지우지 않는다


async def test_돌아온_사람은_다시_ACTIVE():
    repository = FakeRepository()
    service = MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")]))
    await service.sync(now=NOW)
    await MemberService(repository=repository, source=FakeSource([])).sync(now=NOW)

    await MemberService(repository=repository, source=FakeSource([_raw("#A", "도토리")])).sync(
        now=NOW
    )

    assert repository.rows["#A"].status == MemberStatus.ACTIVE


async def test_태그로_한_명을_찾는다():
    service = MemberService(
        repository=FakeRepository(),
        source=FakeSource([_raw("#A", "도토리"), _raw("#B", "히로")]),
    )
    await service.sync(now=NOW)

    found = await service.find_by_external_id("#B")

    assert found is not None
    assert found.name == "히로"
    assert await service.find_by_external_id("#없음") is None


async def test_동기화가_등급을_덮지_않는다():
    """운영진이 매긴 확정·사유·경고는 우리가 정한 값이다.

    CoC 는 이런 것을 모르므로, 30분마다 도는 동기화가 덮으면 매길 때마다
    지워진다. 관리자 메모(description)와 같은 규칙이다.
    """
    before = ClanMember(
        id="uuid-1",
        external_id="#A",
        display_name=None,
        name="도토리",
        role=ClanRole.MEMBER,
        status=MemberStatus.ACTIVE,
        grade=MemberGrade.FIXED,
        grade_reason="길드장",
        warnings=2,
        townhall=16,
        trophies=4200,
        donations=100,
        donations_received=50,
        description=None,
        created_at=NOW,
        updated_at=NOW,
        synced_at=NOW,
    )
    repository = FakeRepository([before])
    source = FakeSource([_raw("#A", "도토리")])

    await MemberService(repository, source).sync(now=NOW)

    after = repository.rows["#A"]
    assert after.grade is MemberGrade.FIXED
    assert after.grade_reason == "길드장"
    assert after.warnings == 2


async def test_처음_보는_사람은_경쟁이다():
    repository = FakeRepository()
    source = FakeSource([_raw("#A", "도토리")])

    await MemberService(repository, source).sync(now=NOW)

    added = repository.rows["#A"]
    assert added.grade is MemberGrade.COMPETING
    assert added.grade_reason is None
    assert added.warnings == 0


def _member(**overrides) -> ClanMember:
    """저장소에 이미 담겨 있는 클랜원 한 명."""
    base = {
        "id": "uuid-1",
        "external_id": "#A",
        "display_name": None,
        "name": "도토리",
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


LATER = "2026-09-14T09:00:00Z"


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


async def test_CoC_가_주인인_값은_건드리지_않는다():
    """이름과 직책은 동기화가 맡는다. 수정이 함께 덮으면 두 자리가 같은 값을 쓴다."""
    repository = FakeRepository([_member(name="도토리", trophies=4200)])

    await MemberService(repository).update_managed("uuid-1", LATER, display_name="도토리형")

    saved = repository.rows["#A"]
    assert saved.name == "도토리"
    assert saved.role is ClanRole.MEMBER
    assert saved.trophies == 4200


async def test_등급은_수정으로_바뀌지_않는다():
    """등급은 그달 점수가 정하는 값이라 사람이 손대는 자리가 없다."""
    repository = FakeRepository([_member(grade=MemberGrade.FIXED, grade_reason="길드장")])

    await MemberService(repository).update_managed("uuid-1", LATER, warnings=1)

    saved = repository.rows["#A"]
    assert saved.grade is MemberGrade.FIXED
    assert saved.grade_reason == "길드장"



async def test_없는_식별자면_None():
    repository = FakeRepository([_member()])

    assert await MemberService(repository).update_managed("없는-uuid", LATER) is None


async def test_경고_횟수는_음수가_될_수_없다():
    repository = FakeRepository([_member()])

    with pytest.raises(ValueError):
        await MemberService(repository).update_managed("uuid-1", LATER, warnings=-1)

    assert repository.rows["#A"].warnings == 0


async def test_동기화는_사람이_정한_표기를_채우지도_덮지도_않는다():
    """채우면 사람이 정한 것인지 동기화가 쓴 것인지 구분할 수 없다."""
    repository = FakeRepository([_member(display_name="도토리형")])
    source = FakeSource([_raw("#A", "도토리")])

    await MemberService(repository, source).sync(now=NOW)

    assert repository.rows["#A"].display_name == "도토리형"


async def test_처음_보는_사람의_표기는_비어_있다():
    repository = FakeRepository()
    source = FakeSource([_raw("#A", "도토리")])

    await MemberService(repository, source).sync(now=NOW)

    added = repository.rows["#A"]
    assert added.display_name is None
    assert added.name == "도토리"
