"""Fetch finished wars from the API and persist them under ``data/``.

Finished (``warEnded``) and running (``inWar``) wars are saved; a running war is marked
``in_progress`` and refreshed each run. Regular-war member attacks disappear from the API
as soon as the next war's preparation starts, which is why this runs on a schedule.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from coc_pointer.api import CocApiError
from coc_pointer.config import ClanConfig
from coc_pointer.models import Attack, ClanMember, ClanSnapshot, War, WarMember
from coc_pointer.storage import save_clan_snapshot, save_war

_API_TIME = "%Y%m%dT%H%M%S.%fZ"
REGULAR_ATTACKS = 2
CWL_ATTACKS = 1
EMPTY_WAR_TAG = "#0"
SAVED_STATES = ("warEnded", "inWar")


class WarLogPrivateError(Exception):
    """The clan's war log is private, so the API refuses war details."""


class ApiLike(Protocol):
    def clan(self, tag: str) -> dict[str, Any]: ...
    def current_war(self, tag: str) -> dict[str, Any]: ...
    def league_group(self, tag: str) -> dict[str, Any] | None: ...
    def cwl_war(self, war_tag: str) -> dict[str, Any]: ...


def parse_api_time(text: str) -> datetime:
    return datetime.strptime(text, _API_TIME).replace(tzinfo=UTC)


def _member(raw: dict[str, Any]) -> WarMember:
    attacks = sorted(
        (Attack(order=a["order"], stars=a["stars"]) for a in raw.get("attacks", [])),
        key=lambda a: a.order,
    )
    return WarMember(
        tag=raw["tag"], name=raw["name"], townhall=raw["townhallLevel"], attacks=tuple(attacks)
    )


def _build_war(
    payload: dict[str, Any], war_type: str, ours: dict[str, Any], theirs: dict[str, Any], apm: int
) -> War:
    return War(
        war_type=war_type,
        start_time=parse_api_time(payload["startTime"]),
        end_time=parse_api_time(payload["endTime"]),
        team_size=payload["teamSize"],
        attacks_per_member=apm,
        opponent_tag=theirs["tag"],
        opponent_name=theirs["name"],
        members=tuple(_member(m) for m in ours.get("members", [])),
        in_progress=payload.get("state") != "warEnded",
    )


def war_from_regular(payload: dict[str, Any]) -> War:
    apm = payload.get("attacksPerMember") or REGULAR_ATTACKS
    return _build_war(payload, "regular", payload["clan"], payload["opponent"], apm)


def war_from_cwl(payload: dict[str, Any], our_tag: str) -> War | None:
    clan, opponent = payload["clan"], payload["opponent"]
    if clan["tag"] == our_tag:
        return _build_war(payload, "cwl", clan, opponent, CWL_ATTACKS)
    if opponent["tag"] == our_tag:
        return _build_war(payload, "cwl", opponent, clan, CWL_ATTACKS)
    return None


def clan_snapshot_from_payload(payload: dict[str, Any], fetched_at: datetime) -> ClanSnapshot:
    return ClanSnapshot(
        fetched_at=fetched_at,
        name=payload["name"],
        tag=payload["tag"],
        members=tuple(
            ClanMember(
                tag=m["tag"],
                name=m["name"],
                role=m["role"],
                townhall=m["townHallLevel"],
                trophies=m["trophies"],
                donations=m["donations"],
                donations_received=m["donationsReceived"],
            )
            for m in payload.get("memberList", [])
        ),
    )


def collect(
    api: ApiLike,
    config: ClanConfig,
    data_dir: Path,
    now: datetime | None = None,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Snapshot the clan, save new finished wars, and refresh any war still running.

    Returns only the newly finished war files; running wars live in ``data/in-progress/``
    and are rewritten every run, so counting them as "new" would be misleading.
    """
    tag = config.clan_tag
    fetched_at = now or datetime.now(UTC)
    saved: list[Path] = []
    running: list[Path] = []

    save_clan_snapshot(clan_snapshot_from_payload(api.clan(tag), fetched_at), data_dir)
    log("클랜원 목록 갱신")

    try:
        current = api.current_war(tag)
    except CocApiError as err:
        if err.status == 403:
            raise WarLogPrivateError(
                "클랜전 정보를 조회할 수 없습니다. 클랜 전적을 공개로 설정해 주세요."
            ) from err
        raise
    if current.get("state") in SAVED_STATES:
        war = war_from_regular(current)
        if path := save_war(war, data_dir):
            if war.in_progress:
                running.append(path)
                progress = f"{war.attacks_made}/{war.attack_slots} 공격"
                log(f"일반 클랜전 진행 중: {path.name} ({progress})")
            else:
                saved.append(path)
                log(f"일반 클랜전 저장: {path.name}")
    else:
        log(f"일반 클랜전 상태: {current.get('state')} (저장 안 함)")

    group = api.league_group(tag)
    if group:
        for round_ in group.get("rounds", []):
            for war_tag in round_.get("warTags", []):
                if war_tag == EMPTY_WAR_TAG:
                    continue
                payload = api.cwl_war(war_tag)
                if payload.get("state") not in SAVED_STATES:
                    continue
                war = war_from_cwl(payload, tag)
                if war is None:
                    continue
                if path := save_war(war, data_dir):
                    if war.in_progress:
                        running.append(path)
                        progress = f"{war.attacks_made}/{war.attack_slots} 공격"
                        log(f"리그전 진행 중: {path.name} ({progress})")
                    else:
                        saved.append(path)
                        log(f"리그전 저장: {path.name}")
    else:
        log("리그전 진행 중 아님")

    log(f"새로 저장한 클랜전: {len(saved)}개 (진행 중 {len(running)}개 갱신)")
    return saved
