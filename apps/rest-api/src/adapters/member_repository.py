"""클랜원 저장소를 D1 으로 구현한다.

클랜원 질의는 이 파일에만 둔다. 도메인은 SQL 을 모르고, 저장소를 갈아 끼우면
여기만 바뀐다.

이 표는 우리가 만들어 낸 값만 담는다. 이름·직책·홀·트로피는 CoC 가 주인이라
담지 않고, 필요할 때 coc_api 어댑터가 CoC 에 묻는다.

D1 은 SQLite 라서 표준 SQL 이 그대로 돈다. 다만 부르는 모양이 다르다.

    await db.prepare(SQL).bind(값).all()     # 여러 행. 결과는 .results
    await db.prepare(SQL).bind(값).first()   # 한 행. 없으면 None
    await db.prepare(SQL).bind(값).run()     # 쓰기
"""

from __future__ import annotations

from typing import Any

from coc_core.member.models import ClanMember, MemberStatus

_COLUMNS = (
    "id, external_id, display_name, status, warnings, description, "
    "created_at, updated_at, synced_at"
)

# 이름이 없으므로 이름순으로 정렬할 수 없다. 처음 본 순서로 돌려주고, 무엇으로
# 줄 세울지는 부르는 쪽이 정한다. 표기와 CoC 이름 가운데 무엇으로 정렬할지는
# 화면이 정할 일이다.
_FIND_ALL = f"SELECT {_COLUMNS} FROM clan_members ORDER BY created_at, external_id"

_FIND_BY_ID = f"SELECT {_COLUMNS} FROM clan_members WHERE id = ?"

_FIND_BY_EXTERNAL_ID = f"SELECT {_COLUMNS} FROM clan_members WHERE external_id = ?"

_COUNT_BY_EXTERNAL_ID = "SELECT COUNT(*) AS n FROM clan_members WHERE external_id = ?"

# 이미 있는 사람은 status 와 시각만 올린다. 표기·경고·메모와 처음 본 시각은
# 사람이 정하거나 한 번만 정해지는 값이라 동기화가 덮으면 안 된다.
# 그 값들을 바꾸는 일은 _UPDATE_MANAGED 가 따로 맡는다.
_REGISTER = """
INSERT INTO clan_members (
  id, external_id, display_name, status, warnings, description,
  created_at, updated_at, synced_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(external_id) DO UPDATE SET
  status     = excluded.status,
  updated_at = excluded.updated_at,
  synced_at  = excluded.synced_at
"""

# 거꾸로 여기서는 사람이 정하는 값만 덮는다. status 나 synced_at 을 함께 적으면
# 동기화와 이 경로가 같은 열을 두 자리에서 쓰게 되고, 나중에 어느 쪽이 마지막
# 값을 넣었는지 알 수 없게 된다.
_UPDATE_MANAGED = """
UPDATE clan_members
   SET display_name = ?, warnings = ?, description = ?, updated_at = ?
 WHERE id = ?
"""

_MARK_INACTIVE = "UPDATE clan_members SET status = 'INACTIVE', updated_at = ? WHERE external_id = ?"


def _to_member(row: Any) -> ClanMember:
    return ClanMember(
        id=row.id,
        external_id=row.external_id,
        display_name=row.display_name,
        status=MemberStatus(row.status),
        warnings=row.warnings,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        synced_at=row.synced_at,
    )


class D1MemberRepository:
    """MemberRepository 를 D1 으로 구현한다."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def find_all(self) -> list[ClanMember]:
        result = await self._db.prepare(_FIND_ALL).all()
        return [_to_member(row) for row in result.results]

    async def find_by_id(self, member_id: str) -> ClanMember | None:
        row = await self._db.prepare(_FIND_BY_ID).bind(member_id).first()
        return _to_member(row) if row is not None else None

    async def find_by_external_id(self, external_id: str) -> ClanMember | None:
        row = await self._db.prepare(_FIND_BY_EXTERNAL_ID).bind(external_id).first()
        return _to_member(row) if row is not None else None

    async def register_many(self, members: list[ClanMember]) -> int:
        added = 0
        for m in members:
            existing = await self._db.prepare(_COUNT_BY_EXTERNAL_ID).bind(m.external_id).first()
            if existing is None or existing.n == 0:
                added += 1
            await (
                self._db.prepare(_REGISTER)
                .bind(
                    m.id,
                    m.external_id,
                    m.display_name,
                    str(m.status),
                    m.warnings,
                    m.description,
                    m.created_at,
                    m.updated_at,
                    m.synced_at,
                )
                .run()
            )
        return added

    async def update_managed(self, member: ClanMember) -> None:
        await (
            self._db.prepare(_UPDATE_MANAGED)
            .bind(
                member.display_name,
                member.warnings,
                member.description,
                member.updated_at,
                member.id,
            )
            .run()
        )

    async def mark_inactive(self, external_ids: list[str], now: str) -> int:
        for external_id in external_ids:
            await self._db.prepare(_MARK_INACTIVE).bind(now, external_id).run()
        return len(external_ids)
