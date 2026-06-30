from __future__ import annotations

import os
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from fonbet_mcp.config import load_settings
from fonbet_mcp.fonbet import (
    FonbetClient,
    extract_day_specials,
    extract_markets,
    extract_odds,
    search_events,
    value_check,
)

settings = load_settings()
client = FonbetClient(
    base_url=settings.base_url,
    scope_market=settings.scope_market,
    timeout=settings.timeout,
    current_line_path=settings.current_line_path,
    event_view_path=settings.event_view_path,
)
allowed_hosts = [item.strip() for item in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if item.strip()]
dns_rebinding_protection = os.getenv("MCP_DNS_REBINDING_PROTECTION", "false").lower() == "true"
server_port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))

mcp = FastMCP(
    "fonbet",
    instructions=(
        "Read Fonbet sports events and decimal odds. Use paginated market tools when a match "
        "has many markets. Treat value checks only as analytical signals, not betting guarantees."
    ),
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=server_port,
    streamable_http_path=os.getenv("MCP_PATH", "/mcp"),
    sse_path=os.getenv("MCP_SSE_PATH", "/sse"),
    message_path=os.getenv("MCP_MESSAGE_PATH", "/messages/"),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=dns_rebinding_protection,
        allowed_hosts=allowed_hosts,
    ),
)


@mcp.tool()
async def fonbet_search_events(query: str, limit: int = 20, lang: str = "ru") -> list[dict[str, Any]]:
    """Search Fonbet line events by team, league, or sport name."""
    payload = await client.current_line(lang=lang)
    return [event.__dict__ for event in search_events(payload, query=query, limit=limit)]


@mcp.tool()
async def fonbet_event_odds(event_id: int, lang: str = "ru") -> dict[str, Any]:
    """Get event details and the first page of odds markets for a Fonbet event id."""
    payload = await client.event_view(event_id=event_id, lang=lang)
    return extract_odds(payload, event_id=event_id)


@mcp.tool()
async def get_event_odds(
    event_id: int,
    offset: int = 0,
    limit: int = 200,
    query: str = "",
    include_raw: bool = False,
    lang: str = "ru",
) -> dict[str, Any]:
    """Get paginated Fonbet markets for one event. Use next_offset to request the next page."""
    payload = await client.event_view(event_id=event_id, lang=lang)
    return extract_markets(
        payload,
        event_id=event_id,
        offset=offset,
        limit=limit,
        query=query or None,
        include_raw=include_raw,
    )


@mcp.tool()
async def get_special_bets(
    query: str = "",
    limit: int = 100,
    include_raw: bool = False,
    lang: str = "ru",
) -> dict[str, Any]:
    """Search the current Fonbet day line for special/player/stat-style markets."""
    payload = await client.current_line(lang=lang)
    return extract_day_specials(payload, query=query, limit=limit, include_raw=include_raw)


@mcp.tool()
async def get_same_game_parlay(
    event_id: int,
    query: str = "",
    limit: int = 200,
    lang: str = "ru",
) -> dict[str, Any]:
    """Return same-event markets that can be inspected for a same-game parlay idea."""
    payload = await client.event_view(event_id=event_id, lang=lang)
    return extract_markets(payload, event_id=event_id, offset=0, limit=limit, query=query or None, include_raw=False)


@mcp.tool()
async def get_cross_match_specials(
    query: str = "",
    limit: int = 100,
    lang: str = "ru",
) -> dict[str, Any]:
    """Return special-style markets across the current Fonbet line for cross-match analysis."""
    payload = await client.current_line(lang=lang)
    return extract_day_specials(payload, query=query, limit=limit, include_raw=False)


@mcp.tool()
async def fonbet_value_check(decimal_odds: float, estimated_probability: float) -> dict[str, Any]:
    """Check whether decimal odds have positive expected value for your estimated probability."""
    return value_check(decimal_odds=decimal_odds, estimated_probability=estimated_probability)


def main() -> None:
    transport = cast(
        Literal["stdio", "sse", "streamable-http"],
        os.getenv("MCP_TRANSPORT", "sse"),
    )
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
