"""Runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    transport: str
    host: str
    port: int
    bearer_token: str | None
    public_base_url: str
    resource_server_url: str


def load_settings() -> Settings:
    db_path = Path(_env("INTERVIEW_PREP_DB_PATH", "data/interview_prep.sqlite3"))
    transport = _env("MCP_TRANSPORT", "stdio")
    host = _env("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    bearer_token = _env("MCP_BEARER_TOKEN", "")
    public_base_url = _env("MCP_PUBLIC_BASE_URL", f"http://{host}:{port}")
    resource_server_url = _env("MCP_RESOURCE_SERVER_URL", f"{public_base_url.rstrip('/')}/mcp")
    return Settings(
        db_path=db_path,
        transport=transport,
        host=host,
        port=port,
        bearer_token=bearer_token or None,
        public_base_url=public_base_url,
        resource_server_url=resource_server_url,
    )


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()
