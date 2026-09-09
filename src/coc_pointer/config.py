"""Admin-managed settings loaded from config/clan.yaml.

Tags must be quoted in YAML because ``#`` starts a comment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TAG_RE = re.compile(r"^#[0-9A-Z]+$")
DEFAULT_BONUS_COUNT = 11  # CWL bonus medals go to this many members


class ConfigError(ValueError):
    """Raised when config/clan.yaml is malformed."""


@dataclass(frozen=True)
class ClanConfig:
    clan_tag: str
    elite: frozenset[str] = frozenset()
    alts: frozenset[str] = frozenset()
    excluded: frozenset[str] = frozenset()
    warnings: dict[str, int] = field(default_factory=dict)
    bonus_count: int = DEFAULT_BONUS_COUNT

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


def _load_raw(path: Path) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise ConfigError(f"{path}: YAML 문법 오류: {err}") from err
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: 최상위는 키-값 목록이어야 합니다")
    return raw


def _tag_list(raw: dict, key: str) -> list:
    items = raw.get(key)
    if items is None:
        return []
    if not isinstance(items, list):
        raise ConfigError(f"{key}: 목록이어야 합니다 ({items!r})")
    return items


def _load_clan_tag(raw: dict, path: Path) -> str:
    if "clan_tag" not in raw:
        raise ConfigError(f"{path}: clan_tag 항목이 없습니다.")
    return _check_tag(raw["clan_tag"], "clan_tag")


def load_clan_tag(path: Path) -> str:
    """Read ``path`` and return only the validated ``clan_tag`` (used by ``collect``)."""
    raw = _load_raw(path)
    return _load_clan_tag(raw, path)


def load_config(path: Path) -> ClanConfig:
    raw = _load_raw(path)
    clan_tag = _load_clan_tag(raw, path)

    def tag_set(key: str) -> frozenset[str]:
        items = _tag_list(raw, key)
        return frozenset(_check_tag(t, f"{key}[{i}]") for i, t in enumerate(items))

    raw_warnings = raw.get("warnings")
    if raw_warnings is None:
        raw_warnings = {}
    elif not isinstance(raw_warnings, dict):
        raise ConfigError(f"warnings: 키-값 목록이어야 합니다 ({raw_warnings!r})")

    def warning_count(tag: str, n: object) -> int:
        if isinstance(n, bool):
            raise ConfigError(f"warnings.{tag}: 경고 횟수는 정수여야 합니다 ({n!r})")
        try:
            return int(n)
        except TypeError, ValueError:
            raise ConfigError(f"warnings.{tag}: 경고 횟수는 정수여야 합니다 ({n!r})") from None

    warnings = {
        _check_tag(t, f"warnings.{t}"): warning_count(t, n) for t, n in raw_warnings.items()
    }
    bonus = raw.get("cwl_bonus_count", DEFAULT_BONUS_COUNT)
    if isinstance(bonus, bool) or not isinstance(bonus, int) or bonus < 1:
        raise ConfigError(f"cwl_bonus_count: 1 이상의 정수여야 합니다 ({bonus!r})")

    return ClanConfig(
        clan_tag=clan_tag,
        bonus_count=bonus,
        elite=tag_set("elite"),
        alts=tag_set("alts"),
        excluded=tag_set("excluded"),
        warnings=warnings,
    )
