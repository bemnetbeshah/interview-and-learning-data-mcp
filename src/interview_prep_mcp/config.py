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


def load_settings() -> Settings:
    db_path = Path(os.getenv("INTERVIEW_PREP_DB_PATH", "data/interview_prep.sqlite3"))
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
    return Settings(db_path=db_path, transport=transport, host=host, port=port)
