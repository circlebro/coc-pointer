"""클랜원 조회 경로.

응답 모양은 contracts/openapi.yaml 이 정한다. 여기서는 도메인 자료형을
그 모양으로 옮기기만 한다.
"""

from __future__ import annotations

from typing import Annotated, Any

from coc_core.member.models import ClanMember
from coc_core.member.service import MemberService
from fastapi import APIRouter, Depends, Query, Request

from adapters.member_repository import D1MemberRepository

router = APIRouter(prefix="/api/v1", tags=["members"])


def get_member_service(request: Request) -> MemberService:
    """요청마다 조립한다. 스프링 컨테이너가 하던 일을 여기서 직접 한다.

    조회만 하므로 source 를 넘기지 않는다. 동기화는 cli.py 가 따로 조립한다.
    """
    env = request.scope["env"]
    return MemberService(repository=D1MemberRepository(env.DB))


MemberSvc = Annotated[MemberService, Depends(get_member_service)]


def _to_response(member: ClanMember) -> dict[str, Any]:
    """도메인 자료형을 계약이 정한 모양으로. 키는 캐멀케이스다."""
    return {
        "id": member.id,
        "tag": member.tag,
        "name": member.name,
        "role": str(member.role),
        "status": str(member.status),
        "townhall": member.townhall,
        "trophies": member.trophies,
        "donations": member.donations,
        "donationsReceived": member.donations_received,
        "description": member.description,
        "createdAt": member.created_at,
        "updatedAt": member.updated_at,
    }


@router.get("/members")
async def list_members(
    service: MemberSvc,
    tag: Annotated[str | None, Query(description="플레이어 태그로 좁힌다")] = None,
) -> dict[str, Any]:
    """클랜원 목록. 나간 사람(INACTIVE)도 포함한다."""
    if tag is not None:
        found = await service.find_by_tag(tag)
        return {"members": [_to_response(found)] if found else []}
    return {"members": [_to_response(m) for m in await service.find_all()]}
