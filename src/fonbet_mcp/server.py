from __future__ import annotations

import os
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

from fonbet_mcp.config import load_settings
from fonbet_mcp.fonbet import FonbetClient, extract_odds, search_events, value_check

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
        "Read Fonbet sports events and decimal odds. Use value checks only as analytical "
        "signals, not as betting guarantees."
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
    """Get event details and odds markets for a Fonbet event id."""
    payload = await client.event_view(event_id=event_id, lang=lang)
    return extract_odds(payload, event_id=event_id)


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
