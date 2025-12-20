import json
import sys
from pathlib import Path

import requests

URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"


def main() -> int:
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "data" not in data:
        raise ValueError("YGOPRODeck payload missing 'data' key")

    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / "cards.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved card database to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
