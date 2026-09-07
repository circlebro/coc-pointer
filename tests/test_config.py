from pathlib import Path

import pytest

from coc_pointer.config import ClanConfig, ConfigError, load_config


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "clan.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_full_config(tmp_path):
    p = write(
        tmp_path,
        """
clan_tag: "#2C8L822LQ"
elite:
  - "#AAA1"
  - "#BBB2"
alts:
  - "#BBB2"
excluded:
  - "#CCC3"
warnings:
  "#DDD4": 2
""",
    )
    cfg = load_config(p)
    assert cfg.clan_tag == "#2C8L822LQ"
    assert cfg.is_elite("#AAA1")
    assert not cfg.is_elite("#BBB2"), "alts can never be elite"
    assert cfg.is_alt("#BBB2")
    assert cfg.is_excluded("#CCC3")
    assert cfg.warning_count("#DDD4") == 2
    assert cfg.warning_count("#AAA1") == 0


def test_missing_lists_default_to_empty(tmp_path):
    cfg = load_config(write(tmp_path, 'clan_tag: "#2C8L822LQ"\n'))
    assert cfg == ClanConfig(clan_tag="#2C8L822LQ")


def test_invalid_tag_reports_location(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nelite:\n  - "#ok1"\n')
    with pytest.raises(ConfigError, match=r"elite\[0\]"):
        load_config(p)


def test_missing_clan_tag(tmp_path):
    with pytest.raises(ConfigError, match="clan_tag"):
        load_config(write(tmp_path, "elite: []\n"))
