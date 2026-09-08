from pathlib import Path

from helpers import member, war

from coc_pointer import cli
from coc_pointer.storage import save_war


def write_config(tmp_path: Path) -> Path:
    p = tmp_path / "clan.yaml"
    p.write_text('clan_tag: "#2C8L822LQ"\nelite:\n  - "#P1"\n', encoding="utf-8")
    return p


def test_build_command_writes_site(tmp_path, capsys):
    save_war(war([member("#P1", "도토리", (3, 3))]), tmp_path / "data")
    code = cli.main(
        [
            "build",
            "--data-dir",
            str(tmp_path / "data"),
            "--config",
            str(write_config(tmp_path)),
            "--out",
            str(tmp_path / "site"),
        ]
    )
    assert code == 0
    assert (tmp_path / "site" / "index.html").exists()
    assert "생성" in capsys.readouterr().out


def test_collect_requires_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("COC_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    code = cli.main(
        ["collect", "--data-dir", str(tmp_path / "data"), "--config", str(write_config(tmp_path))]
    )
    assert code == 2
    assert "COC_API_TOKEN" in capsys.readouterr().err


def test_collect_ignores_malformed_elite(tmp_path, monkeypatch, capsys):
    """collect only validates clan_tag, so a bad elite entry must not fail config parsing."""
    monkeypatch.delenv("COC_API_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here
    bad = tmp_path / "clan.yaml"
    bad.write_text('clan_tag: "#2C8L822LQ"\nelite:\n  - "#bad"\n', encoding="utf-8")
    code = cli.main(["collect", "--data-dir", str(tmp_path / "data"), "--config", str(bad)])
    assert code == 2
    assert "COC_API_TOKEN" in capsys.readouterr().err


def test_bad_config_reports_and_fails(tmp_path, capsys):
    bad = tmp_path / "clan.yaml"
    bad.write_text('clan_tag: "#2C8L822LQ"\nelite:\n  - "#bad"\n', encoding="utf-8")
    code = cli.main(
        [
            "build",
            "--data-dir",
            str(tmp_path),
            "--config",
            str(bad),
            "--out",
            str(tmp_path / "site"),
        ]
    )
    assert code == 2
    assert "elite[0]" in capsys.readouterr().err


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("COC_API_TOKEN=from-file\nOTHER=1\n# comment\n", encoding="utf-8")
    monkeypatch.setenv("COC_API_TOKEN", "from-env")
    monkeypatch.delenv("OTHER", raising=False)
    cli.load_dotenv(env)
    import os

    assert os.environ["COC_API_TOKEN"] == "from-env"
    assert os.environ["OTHER"] == "1"
