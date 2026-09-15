"""클랜 조회 경로.

응답 모양은 api/openapi.yaml 이 정하고, 여기서는 스펙에서 생성한 모델을
그대로 쓴다. 그러면 스펙을 고치고 다시 생성하는 것만으로 응답이 따라온다.

식별자와 시각에는 format 을 두지 않는다. format: uuid 나 format: date-time 을
적으면 생성 모델이 UUID·AwareDatetime 이 되는데, 도메인은 둘 다 문자열로
다루므로 경로마다 변환을 끼워야 한다. 클랜원 스펙도 같은 규칙을 따른다.
"""

from __future__ import annotations

from typing import Annotated

from coc_core.clan.models import Clan
from coc_core.clan.service import ClanService
from fastapi import APIRouter, Depends, Request

from adapters.clan_repository import D1ClanRepository
from schemas import Clan as ClanSchema
from schemas import ClanListResponse

router = APIRouter(prefix="/api/v1", tags=["clans"])


def get_clan_service(request: Request) -> ClanService:
    """요청마다 조립한다.

    조회만 하므로 source 를 넘기지 않는다. 동기화는 cli.py 가 따로 조립한다.
    """
    env = request.scope["env"]
    return ClanService(repository=D1ClanRepository(env.DB))


ClanSvc = Annotated[ClanService, Depends(get_clan_service)]


def _to_schema(clan: Clan) -> ClanSchema:
    """도메인 자료형을 스펙이 정한 모양으로."""
    return ClanSchema(
        id=clan.id,
        externalId=clan.external_id,
        displayName=clan.display_name,
        status=clan.status,
        createdAt=clan.created_at,
        updatedAt=clan.updated_at,
    )


@router.get("/clans")
async def list_clans(service: ClanSvc) -> ClanListResponse:
    """우리가 다루는 클랜. 더는 다루지 않는 것(INACTIVE)도 포함한다."""
    return ClanListResponse(clans=[_to_schema(c) for c in await service.find_all()])
