"""Application settings via pydantic-settings, loaded from HERMESFY_* env vars."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Hermesfy Studio V5 configuration.

    All values can be set via environment variables prefixed with HERMESFY_.
    """

    model_config = SettingsConfigDict(
        env_prefix="HERMESFY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Paths ────────────────────────────────────────────────────────────────
    data_dir: str = str(Path.home() / ".hermes" / "hermesfy")
    db_path: str = ""  # derived from data_dir if empty

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"

    # ── Auth ─────────────────────────────────────────────────────────────────
    auth_token: Optional[str] = None  # if set, all mutating endpoints require this

    # ── Budget defaults ──────────────────────────────────────────────────────
    default_budget_usd: float = 0.07
    max_budget_usd: float = 5.0

    # ── Hermes agent ────────────────────────────────────────────────────────
    hermes_binary: str = "hermes"
    hermes_profile: str = "hermesfy"
    hermes_skill: str = "hermesfy-agent"
    hermes_timeout_soft: int = 120  # seconds
    hermes_timeout_hard: int = 300  # seconds
    hermes_max_concurrent: int = 2

    # ── DB ───────────────────────────────────────────────────────────────────
    db_timeout: float = 5.0  # SQLite busy timeout

    @property
    def resolved_db_path(self) -> str:
        """Return the resolved DB path, creating the directory if needed."""
        if self.db_path:
            return self.db_path
        p = Path(self.data_dir) / "hermesfy_v5.db"
        p.parent.mkdir(parents=True, exist_ok=True)
        return str(p)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    return Settings()
