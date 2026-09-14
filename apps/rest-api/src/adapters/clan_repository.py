"""클랜 저장소를 D1 으로 구현한다.

클랜 질의는 이 파일에만 둔다. 도메인은 SQL 을 모르고, 저장소를 갈아 끼우면
여기만 바뀐다.

D1 은 SQLite 라서 표준 SQL 이 그대로 돈다. 다만 부르는 모양이 다르다.

    await db.prepare(SQL).bind(값).all()     # 여러 행. 결과는 .results
    await db.prepare(SQL).bind(값).first()   # 한 행. 없으면 None
    await db.prepare(SQL).bind(값).run()     # 쓰기
"""

from __future__ import annotations

from typing import Any

from coc_core.clan.models import Clan, ClanStatus

_COLUMNS = "id, external_id, display_name, status, created_at, updated_at"

# 이름이 없는 클랜은 뒤로 보낸다. NULL 을 그냥 정렬하면 SQLite 는 맨 앞에 둔다.
_FIND_ALL = f"SELECT {_COLUMNS} FROM clans ORDER BY display_name IS NULL, display_name"

_FIND_BY_EXTERNAL_ID = f"SELECT {_COLUMNS} FROM clans WHERE external_id = ?"

# created_at 은 갱신하지 않는다. 처음 본 시각은 지나간 사실이라 덮으면 안 된다.
# display_name 은 갱신한다. 우리가 붙인 이름을 지키는 판단은 서비스가 이미
# 했고, 여기로 온 값은 그 결과다.
_UPSERT = """
INSERT INTO clans (id, external_id, display_name, status, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(external_id) DO UPDATE SET
  display_name = excluded.display_name,
  status       = excluded.status,
  updated_at   = excluded.updated_at
"""


def _to_clan(row: Any) -> Clan:
    return Clan(
        id=row.id,
        external_id=row.external_id,
        display_name=row.display_name,
        status=ClanStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class D1ClanRepository:
    """ClanRepository 를 D1 으로 구현한다."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def find_all(self) -> list[Clan]:
        result = await self._db.prepare(_FIND_ALL).all()
        return [_to_clan(row) for row in result.results]

    async def find_by_external_id(self, external_id: str) -> Clan | None:
        row = await self._db.prepare(_FIND_BY_EXTERNAL_ID).bind(external_id).first()
        return _to_clan(row) if row is not None else None

    async def upsert(self, clan: Clan) -> None:
        await (
            self._db.prepare(_UPSERT)
            .bind(
                clan.id,
                clan.external_id,
                clan.display_name,
                str(clan.status),
                clan.created_at,
                clan.updated_at,
            )
            .run()
        )
