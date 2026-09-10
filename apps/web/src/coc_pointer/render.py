"""Turn stored data into the static site under ``site/``."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from coc_pointer.config import ClanConfig
from coc_pointer.models import ClanMember, ClanSnapshot, War
from coc_pointer.rewards import cwl_is_settled
from coc_pointer.scoring import (
    KST,
    RULES,
    MemberMonth,
    RankedMember,
    RewardSplit,
    aggregate_month,
    group_wars_by_month,
    month_key,
    rank_month,
    roster,
    sort_key,
    split_rewards,
)
from coc_pointer.storage import load_clan_snapshot, load_wars

ROLE_KO = {"leader": "대표", "coLeader": "공동 대표", "admin": "장로", "member": "멤버"}
ROLE_ORDER = {"leader": 0, "coLeader": 1, "admin": 2, "member": 3}


@dataclass(frozen=True)
class MonthView:
    key: str
    label: str
    wars: list[War]
    ranked: list[RankedMember]
    roster: list[RankedMember]
    regular_wars: list[War]
    cwl_wars: list[War]
    regular_grid: list[tuple[RankedMember, list[str]]]  # participants only
    cwl_grid: list[tuple[RankedMember, list[str]]]  # participants only
    cwl_participants: list[MemberMonth]  # actual CWL roster this month, CWL record only
    cwl_roster: list[MemberMonth]  # the same people, ordered the way the roster is drawn up
    rewards: RewardSplit
    reward_status: dict[str, str]  # player tag -> 확정 / 추첨
    cwl_settled: bool  # scores are final, so the bonus slots can be drawn
    next_label: str  # month whose CWL roster this month's scores decide


def war_status(war: War) -> str:
    """Korean marker for a war that has not finished yet; empty once it has."""
    if not war.in_progress:
        return ""
    return "완료 대기" if war.attacks_made >= war.attack_slots else "진행중"


def war_cell(war: War, tag: str) -> str:
    """``"3/2"`` for attacks made, ``x`` for each missed attack, ``""`` if not in the war."""
    for m in war.members:
        if m.tag == tag:
            stars = [str(a.stars) for a in m.attacks]
            stars += ["x"] * (war.attacks_per_member - len(stars))
            return "/".join(stars)
    return ""


def month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{year}년 {int(month)}월"


def next_month_label(key: str) -> str:
    year, month = (int(x) for x in key.split("-"))
    if month == 12:
        year, month = year + 1, 1
    else:
        month += 1
    return f"{year}년 {month}월"


def build_month_view(
    key: str, wars: list[War], config: ClanConfig, clan_members: Iterable[ClanMember] = ()
) -> MonthView:
    ranked = rank_month(aggregate_month(wars, clan_members), config)
    participants = sorted(
        aggregate_month([w for w in wars if w.war_type == "cwl"], war_types=frozenset({"cwl"})),
        key=sort_key,
    )
    rewards = split_rewards(participants, config.bonus_count)
    regular_wars = [w for w in wars if w.war_type == "regular"]
    cwl_wars = [w for w in wars if w.war_type == "cwl"]
    return MonthView(
        key=key,
        label=month_label(key),
        wars=wars,
        ranked=ranked,
        roster=roster(ranked),
        regular_wars=regular_wars,
        cwl_wars=cwl_wars,
        regular_grid=_participant_grid(ranked, regular_wars),
        cwl_grid=_participant_grid(ranked, cwl_wars),
        cwl_participants=participants,
        cwl_roster=sorted(participants, key=lambda m: (-m.townhall, m.name)),
        rewards=rewards,
        reward_status=_reward_status(rewards),
        cwl_settled=cwl_is_settled(cwl_wars),
        next_label=next_month_label(key),
    )


def _participant_grid(
    ranked: list[RankedMember], wars: list[War]
) -> list[tuple[RankedMember, list[str]]]:
    """One row per member who was on the roster of at least one of ``wars``."""
    rows = []
    for r in ranked:
        cells = [war_cell(w, r.member.tag) for w in wars]
        if any(cells):
            rows.append((r, cells))
    return rows


def _reward_status(rewards: RewardSplit) -> dict[str, str]:
    """Label every bonus candidate: certain, or still to be drawn for."""
    status = {m.tag: "확정" for m in rewards.guaranteed}
    for m in rewards.contested:
        status[m.tag] = "추첨"
    return status


def _kst(dt: datetime, fmt: str) -> str:
    return dt.astimezone(KST).strftime(fmt)


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("coc_pointer", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["kst"] = _kst
    env.filters["role_ko"] = lambda role: ROLE_KO.get(role, role)
    env.filters["war_status"] = war_status
    return env


def _sorted_members(snapshot: ClanSnapshot | None) -> list[ClanMember]:
    if snapshot is None:
        return []
    return sorted(snapshot.members, key=lambda m: (ROLE_ORDER.get(m.role, 9), -m.trophies, m.name))


def build_site(
    data_dir: Path, config: ClanConfig, out_dir: Path, now: datetime | None = None
) -> list[Path]:
    """Render one tabbed page per month (data months plus the current month) and members."""
    now = now or datetime.now(UTC)
    wars = load_wars(data_dir)
    snapshot = load_clan_snapshot(data_dir)
    clan_members = snapshot.members if snapshot else ()
    grouped = group_wars_by_month(wars)
    current_key = month_key(now)
    keys = sorted(set(grouped) | {current_key})
    months = [build_month_view(k, grouped.get(k, []), config, clan_members) for k in keys]
    by_key = {m.key: m for m in months}
    generated_at = _kst(now, "%Y-%m-%d %H:%M")
    clan_name = snapshot.name if snapshot else "클랜"

    css_src = resources.files("coc_pointer").joinpath("templates/style.css")
    css_bytes = css_src.read_bytes()
    # Browsers (notably mobile Safari) cache style.css; a content hash in the URL forces a refetch.
    asset_version = hashlib.sha256(css_bytes).hexdigest()[:8]

    env = _env()
    common = {
        "asset_version": asset_version,
        "months": months,
        "months_desc": list(reversed(months)),
        "rules": RULES,
        "generated_at": generated_at,
        "clan_name": clan_name,
        "snapshot": snapshot,
        "members": _sorted_members(snapshot),
        "config": config,
    }
    written: list[Path] = []

    def write(rel: str, template: str, **ctx: object) -> None:
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(template).render(**common, **ctx), encoding="utf-8")
        written.append(path)

    # The root page is the current month, so "/" always opens on today's data.
    write("index.html", "month.html", root="", view=by_key[current_key], current_key=current_key)
    for view in months:
        write(f"{view.key}/index.html", "month.html", root="../", view=view, current_key=view.key)
    write("members/index.html", "members.html", root="../", current_key=current_key)
    css_dst = out_dir / "style.css"
    css_dst.write_bytes(css_bytes)
    written.append(css_dst)
    return written
