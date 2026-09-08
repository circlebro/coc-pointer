"""Read and write the ``data/`` directory (the repository is the database)."""

from __future__ import annotations

import json
from pathlib import Path

from coc_pointer.models import ClanSnapshot, War

WARS_DIR = "wars"
CLAN_FILE = "clan.json"


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_war(war: War, data_dir: Path) -> Path | None:
    """Write ``war`` as JSON. Return the path, or ``None`` if it already existed."""
    path = data_dir / WARS_DIR / war.file_name
    if path.exists():
        return None
    _dump(path, war.to_dict())
    return path


def load_wars(data_dir: Path) -> list[War]:
    folder = data_dir / WARS_DIR
    if not folder.is_dir():
        return []
    wars = [War.from_dict(json.loads(p.read_text(encoding="utf-8"))) for p in folder.glob("*.json")]
    return sorted(wars, key=lambda w: w.end_time)


def save_clan_snapshot(snapshot: ClanSnapshot, data_dir: Path) -> Path:
    path = data_dir / CLAN_FILE
    _dump(path, snapshot.to_dict())
    return path


def load_clan_snapshot(data_dir: Path) -> ClanSnapshot | None:
    path = data_dir / CLAN_FILE
    if not path.exists():
        return None
    return ClanSnapshot.from_dict(json.loads(path.read_text(encoding="utf-8")))
