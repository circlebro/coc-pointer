"""클랜 조회 경로.

응답 모양은 api/openapi.yaml 이 정하고, 여기서는 스펙에서 생성한 모델을
그대로 쓴다. 클랜원 경로(routes/member.py)는 그러지 못하고 사전을 손수
만드는데, 스펙이 id 를 format: uuid 로, 시각을 format: date-time 으로
선언해 생성 모델이 UUID·AwareDatetime 이 되는 반면 도메인은 둘 다 문자열로
다루기 때문이다. 클랜 스펙은 그 format 을 두지 않아 전부 str 로 생성된다.

모델을 쓰면 스펙을 고치고 다시 생성하는 것만으로 응답이 따라온다. 사전을
손으로 만들면 그러지 않는다.
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
