# Fonbet MCP

MCP server for reading Fonbet sports events and odds.

Important: Fonbet does not provide a stable public API contract for this use case. Use this server only where it complies with local law, the bookmaker rules, and request limits. Betting forecasts are not financial guarantees: the server helps analyze odds, probability, and value, but it cannot promise profit.

## Local install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

## Local SSE run

```powershell
$env:MCP_TRANSPORT="sse"
$env:MCP_HOST="127.0.0.1"
$env:MCP_PORT="8000"
python -m fonbet_mcp.server
```

Local endpoint:

```text
http://127.0.0.1:8000/sse
```

## Render Free deploy

This repo includes `render.yaml`.

1. Push this folder to a GitHub repository.
2. Open Render: https://render.com
3. New + -> Blueprint.
4. Connect the GitHub repository.
5. Render will read `render.yaml` and create `fonbet-odds-mcp`.
6. After deploy, use this ChatGPT connector URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com/sse
```

If you create a Web Service manually instead of Blueprint:

- Build command: `pip install -e .`
- Start command: `python -m fonbet_mcp.server`
- Environment variables:
  - `MCP_TRANSPORT=sse`
  - `MCP_HOST=0.0.0.0`
  - `MCP_SSE_PATH=/sse`
  - `MCP_MESSAGE_PATH=/messages/`
  - `MCP_DNS_REBINDING_PROTECTION=false`
  - `FONBET_BASE_URL=https://line-lb51.bk6bba-resources.com`
  - `FONBET_CURRENT_LINE_PATH=/events/listBase`
  - `FONBET_EVENT_VIEW_PATH=/events/event`
  - `FONBET_SCOPE_MARKET=1600`
  - `FONBET_TIMEOUT=20`

## MCP tools

- `fonbet_search_events` - search events by team, league, or sport.
- `fonbet_event_odds` - get markets and odds by `event_id`.
- `fonbet_value_check` - simple value-bet check from your estimated probability.

## Current Fonbet endpoints

- `GET /events/listBase?scopeMarket=1600&lang=ru`
- `GET /events/event?eventId=...&scopeMarket=1600&lang=ru`

Odds are read from `customFactors[].factors[]`; `f` is the factor id and `v` is the decimal odds value.
