from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    base_url: str
    current_line_path: str
    event_view_path: str
    scope_market: str
    timeout: float


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        base_url=os.getenv("FONBET_BASE_URL", "https://line-lb51.bk6bba-resources.com").rstrip("/"),
        current_line_path=os.getenv("FONBET_CURRENT_LINE_PATH", "/events/listBase"),
        event_view_path=os.getenv("FONBET_EVENT_VIEW_PATH", "/events/event"),
        scope_market=os.getenv("FONBET_SCOPE_MARKET", "1600"),
        timeout=float(os.getenv("FONBET_TIMEOUT", "20")),
    )
