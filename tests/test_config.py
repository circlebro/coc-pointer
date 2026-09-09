from pathlib import Path

import pytest

from coc_pointer.config import ClanConfig, ConfigError, load_clan_tag, load_config


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


def test_load_clan_tag_ignores_malformed_elite(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nelite:\n  - "#bad"\n')
    assert load_clan_tag(p) == "#2C8L822LQ"


def test_load_clan_tag_still_requires_valid_clan_tag(tmp_path):
    with pytest.raises(ConfigError, match="clan_tag"):
        load_clan_tag(write(tmp_path, "elite: []\n"))


def test_yaml_syntax_error_reports_file(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nelite: [unterminated\n')
    with pytest.raises(ConfigError, match="YAML 문법 오류"):
        load_config(p)


def test_non_mapping_document_is_rejected(tmp_path):
    p = write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ConfigError, match="키-값 목록"):
        load_config(p)


def test_elite_wrong_type_reports_key(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nelite: "#AAA1"\n')
    with pytest.raises(ConfigError, match="elite"):
        load_config(p)


def test_warnings_wrong_type_reports_key(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nwarnings: "#AAA1"\n')
    with pytest.raises(ConfigError, match="warnings"):
        load_config(p)


def test_warnings_value_must_be_int(tmp_path):
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\nwarnings:\n  "#AAA1": true\n')
    with pytest.raises(ConfigError, match=r"warnings\.#AAA1: 경고 횟수는 정수여야 합니다"):
        load_config(p)


def test_bonus_count_defaults_to_eleven_and_can_be_set(tmp_path):
    assert load_config(write(tmp_path, 'clan_tag: "#2C8L822LQ"\n')).bonus_count == 11
    p = write(tmp_path, 'clan_tag: "#2C8L822LQ"\ncwl_bonus_count: 8\n')
    assert load_config(p).bonus_count == 8


def test_bonus_count_must_be_a_positive_integer(tmp_path):
    for bad in ("0", '"열한명"', "true"):
        p = write(tmp_path, f'clan_tag: "#2C8L822LQ"\ncwl_bonus_count: {bad}\n')
        with pytest.raises(ConfigError, match="cwl_bonus_count"):
            load_config(p)
