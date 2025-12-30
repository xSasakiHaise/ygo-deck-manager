from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from yugioh_data import get_card_by_name

API_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
USER_AGENT = "YGODecklistTool/price-cache"
PRICE_TTL_DAYS = 14
MAX_REQUESTS_PER_SECOND = 2
MAX_RETRIES = 5
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15


@dataclass(frozen=True)
class PriceConfig:
    cache_path: Path
    name_map_path: Path
    ttl_days: int = PRICE_TTL_DAYS
    force_refresh: bool = False
    max_requests_per_second: int = MAX_REQUESTS_PER_SECOND


class RateLimiter:
    def __init__(self, max_per_second: int) -> None:
        interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._interval = interval
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._interval <= 0:
            return
        now = time.monotonic()
        if self._next_allowed > now:
            time.sleep(self._next_allowed - now)
        self._next_allowed = time.monotonic() + self._interval


def _base_path() -> Path:
    return Path(__file__).resolve().parents[2]


def default_price_cache_path() -> Path:
    return _base_path() / "data" / "prices_ygopro.json"


def default_name_map_path() -> Path:
    return _base_path() / "data" / "ygopro_name_map.json"


def load_price_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        name = value.get("name")
        price = value.get("cardmarket_price")
        updated_at = value.get("updated_at")
        if not isinstance(name, str) or not isinstance(updated_at, str):
            continue
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            continue
        cleaned[key] = {
            "name": name,
            "cardmarket_price": price_value,
            "updated_at": updated_at,
        }
    return cleaned


def save_price_cache_atomic(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_name_cache(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, int] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        try:
            cleaned[key] = int(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def save_name_cache_atomic(path: Path, cache: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _parse_iso8601(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_stale(entry: dict[str, Any], ttl_days: int) -> bool:
    updated_at = entry.get("updated_at") if isinstance(entry, dict) else None
    if not isinstance(updated_at, str):
        return True
    parsed = _parse_iso8601(updated_at)
    if parsed is None:
        return True
    return parsed + timedelta(days=ttl_days) < datetime.now(timezone.utc)


def _request_payload(
    session: requests.Session,
    params: dict[str, Any],
    limiter: RateLimiter,
) -> Optional[dict[str, Any]]:
    backoff = 0.5
    for _attempt in range(MAX_RETRIES):
        limiter.wait()
        try:
            response = session.get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            status = response.status_code
            if status == 429 or status >= 500:
                raise requests.HTTPError(response=response)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return None
        except (requests.Timeout, requests.ConnectionError):
            pass
        except requests.HTTPError as exc:
            if exc.response is not None:
                status = exc.response.status_code
                if status not in {429} and status < 500:
                    return None
        time.sleep(backoff)
        backoff *= 2
    return None


def parse_cardmarket_price(raw: Any) -> Optional[float]:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def fetch_card_price_by_id(
    session: requests.Session,
    card_id: int,
    limiter: RateLimiter,
) -> Optional[tuple[str, float]]:
    payload = _request_payload(session, {"id": card_id}, limiter)
    if not payload or "data" not in payload:
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    card = data[0]
    if not isinstance(card, dict):
        return None
    name = card.get("name")
    if not isinstance(name, str):
        return None
    prices = card.get("card_prices")
    if not isinstance(prices, list) or not prices:
        return None
    price_entry = prices[0] if isinstance(prices[0], dict) else None
    if not price_entry:
        return None
    price_value = parse_cardmarket_price(price_entry.get("cardmarket_price"))
    if price_value is None:
        return None
    return name, price_value


def fetch_card_id_by_name(
    session: requests.Session,
    name: str,
    limiter: RateLimiter,
) -> Optional[tuple[int, str]]:
    payload = _request_payload(session, {"name": name}, limiter)
    if not payload or "data" not in payload:
        return None
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None
    card = data[0]
    if not isinstance(card, dict):
        return None
    card_id = card.get("id")
    card_name = card.get("name")
    if not isinstance(card_id, int) or not isinstance(card_name, str):
        return None
    return card_id, card_name


def resolve_card_id(
    session: requests.Session,
    name: str,
    name_cache: dict[str, int],
    limiter: RateLimiter,
) -> Optional[int]:
    if not name:
        return None
    key = name.strip().lower()
    if not key:
        return None
    cached = name_cache.get(key)
    if cached:
        return cached
    card = get_card_by_name(name)
    if card and isinstance(card.get("id"), int):
        card_id = card["id"]
        name_cache[key] = card_id
        return card_id
    fetched = fetch_card_id_by_name(session, name, limiter)
    if not fetched:
        return None
    card_id, card_name = fetched
    name_cache[key] = card_id
    name_cache.setdefault(card_name.lower(), card_id)
    return card_id


def ensure_prices(
    card_ids: set[int],
    cache: dict[str, dict[str, Any]],
    *,
    ttl_days: int = PRICE_TTL_DAYS,
    force_refresh: bool = False,
    max_requests_per_second: int = MAX_REQUESTS_PER_SECOND,
) -> dict[str, dict[str, Any]]:
    limiter = RateLimiter(max_requests_per_second)
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with requests.Session() as session:
        for card_id in sorted(card_ids):
            key = str(card_id)
            entry = cache.get(key)
            if entry and not force_refresh and not is_stale(entry, ttl_days):
                continue
            fetched = fetch_card_price_by_id(session, card_id, limiter)
            if fetched is None:
                continue
            name, price = fetched
            cache[key] = {
                "name": name,
                "cardmarket_price": price,
                "updated_at": now_iso,
            }
    return cache


__all__ = [
    "PriceConfig",
    "PRICE_TTL_DAYS",
    "MAX_REQUESTS_PER_SECOND",
    "RateLimiter",
    "default_name_map_path",
    "default_price_cache_path",
    "ensure_prices",
    "fetch_card_price_by_id",
    "fetch_card_id_by_name",
    "is_stale",
    "load_name_cache",
    "load_price_cache",
    "parse_cardmarket_price",
    "resolve_card_id",
    "save_name_cache_atomic",
    "save_price_cache_atomic",
]
