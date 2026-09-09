"""Builders for War/WarMember used across tests."""

from datetime import UTC, datetime, timedelta

from coc_pointer.models import Attack, War, WarMember


def member(tag: str, name: str, stars: tuple[int, ...] = (), townhall: int = 16) -> WarMember:
    return WarMember(
        tag=tag,
        name=name,
        townhall=townhall,
        attacks=tuple(Attack(order=i, stars=s) for i, s in enumerate(stars, start=1)),
    )


def war(
    members: list[WarMember] | tuple[WarMember, ...],
    war_type: str = "regular",
    end: str = "2026-09-05T14:30:00Z",
    opponent_tag: str = "#OPP1",
    opponent_name: str = "상대",
    in_progress: bool = False,
) -> War:
    end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return War(
        war_type=war_type,
        start_time=end_dt - timedelta(days=1),
        end_time=end_dt,
        team_size=len(members),
        attacks_per_member=2 if war_type == "regular" else 1,
        opponent_tag=opponent_tag,
        opponent_name=opponent_name,
        members=tuple(members),
        in_progress=in_progress,
    )
