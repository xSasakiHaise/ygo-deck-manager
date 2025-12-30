import json
import sys
from pathlib import Path
from typing import Optional

import requests

URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
LANGUAGE_CODES = {
    "en": None,
    "de": "de",
}


def _fetch_cards(language_code: Optional[str]) -> dict:
    params = {}
    if language_code:
        params["language"] = language_code
    response = requests.get(URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "data" not in data:
        raise ValueError("YGOPRODeck payload missing 'data' key")
    return data


def main() -> int:
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for language, code in LANGUAGE_CODES.items():
        data = _fetch_cards(code)
        suffix = "" if language == "en" else f"_{language}"
        target = assets_dir / f"cards{suffix}.json"
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {language} card database to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
