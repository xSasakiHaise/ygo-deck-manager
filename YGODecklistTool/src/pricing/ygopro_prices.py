from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
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


def normalize_passcode(raw_id: Any) -> Optional[str]:
    if raw_id is None:
        return None
    if isinstance(raw_id, str):
        text = raw_id.strip()
    else:
        text = str(raw_id).strip()
    if not text or text == "0":
        return None
    try:
        value = int(text)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    return str(value)


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
        cleaned_entry: dict[str, Any] = {
            "name": name,
            "cardmarket_price": price_value,
            "updated_at": updated_at,
        }
        last_error = value.get("last_error")
        if isinstance(last_error, str) and last_error:
            cleaned_entry["last_error"] = last_error
        cleaned[key] = cleaned_entry
    return cleaned


def save_price_cache_atomic(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
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
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
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
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES):
        limiter.wait()
        response: Optional[requests.Response] = None
        try:
            response = session.get(
                API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
            status = response.status_code
            if status != 200:
                last_error = f"HTTP {status}"
                if status == 429 or status >= 500:
                    raise requests.HTTPError(response=response)
                return None, last_error
            try:
                payload = response.json()
            except ValueError:
                return None, "JSON decode error"
            if isinstance(payload, dict):
                return payload, None
            return None, "JSON missing object"
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = repr(exc)
        except requests.HTTPError:
            retry_after = _parse_retry_after(response)
            _sleep_backoff(attempt, retry_after)
            continue
        except requests.RequestException as exc:
            last_error = repr(exc)
        _sleep_backoff(attempt)
    return None, last_error


def _parse_retry_after(response: Optional[requests.Response]) -> Optional[float]:
    if response is None:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        delay = (parsed - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, delay)


def _sleep_backoff(attempt: int, retry_after: Optional[float] = None) -> None:
    if retry_after is not None:
        time.sleep(retry_after)
        return
    delay = 0.5 * (2**attempt) + random.uniform(0, 0.2)
    time.sleep(delay)


def parse_cardmarket_price(raw: Any) -> Optional[float]:
    if raw in (None, "", "N/A"):
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def fetch_card_price_by_id(
    session: requests.Session,
    card_id: str,
    limiter: RateLimiter,
) -> tuple[Optional[tuple[str, float]], Optional[str]]:
    payload, error = _request_payload(session, {"id": card_id}, limiter)
    if not payload:
        return None, error or "Request failed"
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        return None, "JSON missing data"
    card = data[0]
    if not isinstance(card, dict):
        return None, "JSON missing card"
    name = card.get("name")
    if not isinstance(name, str):
        return None, "JSON missing name"
    prices = card.get("card_prices")
    if not isinstance(prices, list) or not prices:
        return None, "JSON missing card_prices"
    price_entry = prices[0] if isinstance(prices[0], dict) else None
    if not price_entry:
        return None, "JSON missing price entry"
    price_value = parse_cardmarket_price(price_entry.get("cardmarket_price"))
    if price_value is None:
        return None, "JSON invalid cardmarket_price"
    return (name, price_value), None


def fetch_card_id_by_name(
    session: requests.Session,
    name: str,
    limiter: RateLimiter,
) -> Optional[tuple[int, str]]:
    payload, _error = _request_payload(session, {"name": name}, limiter)
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
    raw_ids: list[Any],
    cache: dict[str, dict[str, Any]],
    *,
    cache_path: Optional[Path] = None,
    ttl_days: int = PRICE_TTL_DAYS,
    force_refresh: bool = False,
    max_requests_per_second: int = MAX_REQUESTS_PER_SECOND,
) -> "PriceSummary":
    normalized_ids = [normalize_passcode(card_id) for card_id in raw_ids]
    ids_total = len(normalized_ids)
    valid_ids = [card_id for card_id in normalized_ids if card_id is not None]
    ids_valid = len(valid_ids)
    unique_ids = sorted(set(valid_ids))
    ids_requested = 0
    ids_ok = 0
    ids_failed = 0
    failed_diagnostics = 0
    limiter = RateLimiter(max_requests_per_second)
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with requests.Session() as session:
        for card_id in unique_ids:
            entry = cache.get(card_id)
            if entry and not force_refresh and not is_stale(entry, ttl_days):
                continue
            ids_requested += 1
            fetched, error = fetch_card_price_by_id(session, card_id, limiter)
            if fetched is None:
                ids_failed += 1
                should_record_error = failed_diagnostics < 5
                if should_record_error:
                    failed_diagnostics += 1
                if entry:
                    if should_record_error:
                        entry["last_error"] = error or "Request failed"
                else:
                    failure_entry = {
                        "name": "",
                        "cardmarket_price": 0.0,
                        "updated_at": now_iso,
                    }
                    if should_record_error:
                        failure_entry["last_error"] = error or "Request failed"
                    cache[card_id] = failure_entry
                continue
            ids_ok += 1
            name, price = fetched
            cache[card_id] = {
                "name": name,
                "cardmarket_price": price,
                "updated_at": now_iso,
            }
    ids_nonzero = sum(
        1
        for card_id in set(valid_ids)
        if cache.get(card_id, {}).get("cardmarket_price", 0.0) > 0
    )
    summary = PriceSummary(
        ids_total=ids_total,
        ids_valid=ids_valid,
        ids_requested=ids_requested,
        ids_ok=ids_ok,
        ids_nonzero=ids_nonzero,
        ids_failed=ids_failed,
        cache_path=cache_path or default_price_cache_path(),
    )
    print(summary.summary_line)
    return summary


@dataclass(frozen=True)
class PriceSummary:
    ids_total: int
    ids_valid: int
    ids_requested: int
    ids_ok: int
    ids_nonzero: int
    ids_failed: int
    cache_path: Path

    @property
    def summary_line(self) -> str:
        return (
            "YGOPRO prices: "
            f"valid={self.ids_valid}/{self.ids_total} "
            f"requested={self.ids_requested} "
            f"ok={self.ids_ok} "
            f"nonzero={self.ids_nonzero} "
            f"failed={self.ids_failed} "
            f"cache={self.cache_path}"
        )


__all__ = [
    "PriceSummary",
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
    "normalize_passcode",
    "parse_cardmarket_price",
    "resolve_card_id",
    "save_name_cache_atomic",
    "save_price_cache_atomic",
]
