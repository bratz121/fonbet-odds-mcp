from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class EventSummary:
    event_id: int
    name: str
    sport: str | None
    league: str | None
    start_time: int | None
    status: str | None


class FonbetClient:
    def __init__(
        self,
        base_url: str,
        scope_market: str = "1600",
        timeout: float = 20,
        current_line_path: str = "/events/listBase",
        event_view_path: str = "/events/event",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.scope_market = scope_market
        self.timeout = timeout
        self.current_line_path = current_line_path
        self.event_view_path = event_view_path

    async def current_line(self, lang: str = "ru") -> dict[str, Any]:
        return await self._get(
            self.current_line_path.format(lang=lang),
            params={"scopeMarket": self.scope_market, "lang": lang},
        )

    async def event_view(self, event_id: int, lang: str = "ru") -> dict[str, Any]:
        return await self._get(
            self.event_view_path,
            params={"eventId": event_id, "lang": lang, "scopeMarket": self.scope_market},
        )

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"user-agent": "Mozilla/5.0", "referer": "https://fon.bet/"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            response = await client.get(f"{self.base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Fonbet returned a non-object JSON payload")
        return payload


def search_events(payload: dict[str, Any], query: str, limit: int = 20) -> list[EventSummary]:
    needle = query.casefold().strip()
    sports_by_id = _sports_by_id(payload)
    results: list[EventSummary] = []

    for event in _iter_events(payload):
        event_id = event.get("id")
        if not isinstance(event_id, int):
            continue
        name = _event_name(event)
        sport = _sport_name(sports_by_id, event.get("sportId"), prefer_root=True)
        league = _sport_name(sports_by_id, event.get("sportId"), prefer_root=False)
        haystack = " ".join(part for part in [name, league, sport, event.get("place")] if part).casefold()
        if needle and needle not in haystack:
            continue
        results.append(
            EventSummary(
                event_id=event_id,
                name=name,
                sport=sport,
                league=league,
                start_time=event.get("startTime") if isinstance(event.get("startTime"), int) else None,
                status=event.get("place") or event.get("state"),
            )
        )
        if len(results) >= limit:
            break
    return results


def extract_odds(payload: dict[str, Any], event_id: int | None = None) -> dict[str, Any]:
    return extract_markets(payload, event_id=event_id, offset=0, limit=120, query=None, include_raw=False)


def extract_markets(
    payload: dict[str, Any],
    event_id: int | None = None,
    offset: int = 0,
    limit: int = 200,
    query: str | None = None,
    include_raw: bool = False,
) -> dict[str, Any]:
    events = list(_iter_events(payload))
    if event_id is not None:
        event = next((item for item in events if item.get("id") == event_id), events[0] if events else {})
    else:
        event = events[0] if events else {}
        event_id = event.get("id") if isinstance(event.get("id"), int) else None

    factor_blocks = _factor_blocks_by_event(payload)
    factors = factor_blocks.get(event_id, []) if event_id is not None else []
    sports_by_id = _sports_by_id(payload)
    catalog = _factor_type_catalog(payload)
    normalized = [_normalize_factor(factor, catalog, include_raw=include_raw) for factor in factors if isinstance(factor, dict)]

    if query:
        needle = query.casefold().strip()
        normalized = [market for market in normalized if needle in _market_search_text(market).casefold()]

    offset = max(0, offset)
    limit = max(1, min(limit, 500))
    page = normalized[offset : offset + limit]

    return {
        "event": {
            "id": event.get("id"),
            "name": _event_name(event),
            "sport": _sport_name(sports_by_id, event.get("sportId"), prefer_root=True),
            "league": _sport_name(sports_by_id, event.get("sportId"), prefer_root=False),
            "start_time": event.get("startTime"),
            "status": event.get("place"),
        },
        "markets": page,
        "market_count": len(normalized),
        "total_market_count": len(factors),
        "offset": offset,
        "limit": limit,
        "next_offset": offset + limit if offset + limit < len(normalized) else None,
        "packet_version": payload.get("packetVersion"),
    }


def extract_day_specials(
    payload: dict[str, Any],
    query: str = "",
    limit: int = 100,
    include_raw: bool = False,
) -> dict[str, Any]:
    sports_by_id = _sports_by_id(payload)
    catalog = _factor_type_catalog(payload)
    events_by_id = {
        event.get("id"): event
        for event in _iter_events(payload)
        if isinstance(event.get("id"), int)
    }
    base_keywords = [
        "спец",
        "игрок",
        "пенальти",
        "карточ",
        "углов",
        "офсайд",
        "удар",
        "сэйв",
        "гол",
        "тайм",
        "побед",
        "фора",
        "тотал",
    ]
    keywords = [item.casefold() for item in base_keywords]
    query_text = query.casefold().strip()

    results: list[dict[str, Any]] = []
    max_items = max(1, min(limit, 500))
    for event_id, factors in _factor_blocks_by_event(payload).items():
        event = events_by_id.get(event_id, {})
        for factor in factors:
            if not isinstance(factor, dict):
                continue
            market = _normalize_factor(factor, catalog, include_raw=include_raw)
            text = _market_search_text(market).casefold()
            if query_text and query_text not in text:
                continue
            if not query_text and keywords and not any(keyword in text for keyword in keywords):
                continue
            results.append(
                {
                    "event": {
                        "id": event_id,
                        "name": _event_name(event),
                        "sport": _sport_name(sports_by_id, event.get("sportId"), prefer_root=True),
                        "league": _sport_name(sports_by_id, event.get("sportId"), prefer_root=False),
                        "start_time": event.get("startTime"),
                    },
                    "market": market,
                }
            )
            if len(results) >= max_items:
                return {"specials": results, "count": len(results), "limit": max_items}
    return {"specials": results, "count": len(results), "limit": max_items}


def value_check(decimal_odds: float, estimated_probability: float) -> dict[str, float | bool]:
    if decimal_odds <= 1:
        raise ValueError("decimal_odds must be greater than 1")
    if not 0 < estimated_probability < 1:
        raise ValueError("estimated_probability must be between 0 and 1")

    implied_probability = 1 / decimal_odds
    expected_roi = (decimal_odds * estimated_probability) - 1
    return {
        "decimal_odds": decimal_odds,
        "estimated_probability": estimated_probability,
        "implied_probability": implied_probability,
        "edge": estimated_probability - implied_probability,
        "expected_roi": expected_roi,
        "is_value": expected_roi > 0,
    }


def _sports_by_id(payload: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    return {
        item.get("id"): item
        for item in payload.get("sports", [])
        if isinstance(item, dict) and item.get("id") is not None
    }


def _sport_name(sports_by_id: dict[Any, dict[str, Any]], sport_id: Any, prefer_root: bool) -> str | None:
    sport = sports_by_id.get(sport_id)
    if not sport:
        return None
    if not prefer_root:
        return sport.get("name")

    current = sport
    visited: set[Any] = set()
    while current and current.get("id") not in visited:
        visited.add(current.get("id"))
        if current.get("kind") == "sport":
            return current.get("name")
        parent = sports_by_id.get(current.get("parentId"))
        if not parent:
            break
        current = parent
    return sport.get("name")


def _factor_blocks_by_event(payload: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    blocks: dict[int, list[dict[str, Any]]] = {}
    for block in payload.get("customFactors", []):
        if not isinstance(block, dict):
            continue
        event_id = block.get("e")
        factors = block.get("factors")
        if isinstance(event_id, int) and isinstance(factors, list):
            blocks[event_id] = factors
    return blocks


def _iter_events(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    value = payload.get("events", [])
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def _event_name(event: dict[str, Any]) -> str:
    team1 = event.get("team1")
    team2 = event.get("team2")
    if team1 and team2:
        return f"{team1} - {team2}"
    return str(event.get("name") or event.get("caption") or event.get("id") or "unknown")


_KNOWN_FACTOR_NAMES: dict[int, str] = {
    921: "П1",
    922: "Ничья",
    923: "П2",
    924: "1X",
    925: "12",
    1571: "X2",
    927: "Фора 1",
    928: "Фора 2",
    930: "Тотал больше",
    931: "Тотал меньше",
    2820: "П1 с форой 0",
    2821: "П2 с форой 0",
    709: "Обе забьют - да",
    710: "Обе забьют - нет",
}


def _known_factor_label(factor_id: Any, param_text: Any) -> str | None:
    if not isinstance(factor_id, int):
        return None
    name = _KNOWN_FACTOR_NAMES.get(factor_id)
    if not name:
        return None
    if param_text not in (None, "") and name in {"Фора 1", "Фора 2", "Тотал больше", "Тотал меньше"}:
        return f"{name} ({param_text})"
    return name
def _factor_type_catalog(payload: dict[str, Any]) -> dict[Any, dict[str, Any]]:
    catalog: dict[Any, dict[str, Any]] = {}
    for value in payload.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            factor_id = item.get("id") or item.get("f") or item.get("factorId")
            name = item.get("name") or item.get("title") or item.get("caption")
            if factor_id is not None and name:
                catalog[factor_id] = item
    return catalog


def _normalize_factor(factor: dict[str, Any], catalog: dict[Any, dict[str, Any]], include_raw: bool = False) -> dict[str, Any]:
    factor_id = factor.get("f")
    meta = catalog.get(factor_id, {})
    known_label = _known_factor_label(factor_id, factor.get("pt"))
    result: dict[str, Any] = {
        "factor_id": factor_id,
        "label": known_label,
        "name": meta.get("name") or meta.get("title") or meta.get("caption") or known_label,
        "group": factor.get("g") or meta.get("group") or meta.get("groupName"),
        "odds": factor.get("v"),
        "param": factor.get("p"),
        "param_text": factor.get("pt"),
        "score": factor.get("s"),
        "blocked": factor.get("b"),
    }
    if include_raw:
        result["raw"] = factor
        if meta:
            result["metadata"] = meta
    return result


def _market_search_text(market: dict[str, Any]) -> str:
    values = [
        market.get("label"),
        market.get("name"),
        market.get("group"),
        market.get("param"),
        market.get("param_text"),
        market.get("factor_id"),
    ]
    return " ".join(str(value) for value in values if value is not None)
