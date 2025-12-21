from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _get_base_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        settings_dir = Path(appdata) / "YGODecklistTool"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / "settings.json"
    return _get_base_path() / "assets" / "settings.json"


def load_settings() -> Dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_settings(settings: Dict[str, Any]) -> None:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
