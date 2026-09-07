"""Admin-managed settings loaded from config/clan.yaml.

Tags must be quoted in YAML because ``#`` starts a comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TAG_RE = re.compile(r"^#[0-9A-Z]+$")


class ConfigError(ValueError):
    """Raised when config/clan.yaml is malformed."""


@dataclass(frozen=True)
class ClanConfig:
    clan_tag: str
    elite: frozenset[str] = frozenset()
    alts: frozenset[str] = frozenset()
    excluded: frozenset[str] = frozenset()
    warnings: dict[str, int] = field(default_factory=dict)

    def is_elite(self, tag: str) -> bool:
        return tag in self.elite and tag not in self.alts

    def is_alt(self, tag: str) -> bool:
        return tag in self.alts

    def is_excluded(self, tag: str) -> bool:
        return tag in self.excluded

    def warning_count(self, tag: str) -> int:
        return self.warnings.get(tag, 0)


def _check_tag(value: object, where: str) -> str:
    if not isinstance(value, str) or not TAG_RE.match(value):
        raise ConfigError(
            f"{where}: 잘못된 태그 형식 {value!r}. "
            "태그는 '#'으로 시작하는 대문자·숫자이며 YAML에서 따옴표로 감싸야 합니다."
        )
    return value


def load_config(path: Path) -> ClanConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "clan_tag" not in raw:
        raise ConfigError(f"{path}: clan_tag 항목이 없습니다.")

    def tag_set(key: str) -> frozenset[str]:
        items = raw.get(key) or []
        return frozenset(_check_tag(t, f"{key}[{i}]") for i, t in enumerate(items))

    warnings = {
        _check_tag(t, f"warnings.{t}"): int(n) for t, n in (raw.get("warnings") or {}).items()
    }
    return ClanConfig(
        clan_tag=_check_tag(raw["clan_tag"], "clan_tag"),
        elite=tag_set("elite"),
        alts=tag_set("alts"),
        excluded=tag_set("excluded"),
        warnings=warnings,
    )
