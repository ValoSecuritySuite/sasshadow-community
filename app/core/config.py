"""Application configuration with environment variable support (Community Edition)."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    edition: Literal["community"] = Field(
        default="community",
        description="Build edition (Community Edition only in this repository).",
    )

    rules_path: Path = Field(
        default=Path(__file__).parent.parent / "rules" / "default_yml_rule.yml",
        description="Path to YAML rules file",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    rate_limit: str = Field(
        default="100/minute",
        description="Default rate limit (e.g., 100/minute)",
    )
    rules_cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description="Seconds to cache rules (0=disabled)",
    )
    scan_history_db_path: Path = Field(
        default=Path("data/scans.db"),
        description="SQLite database path for scan history (created if missing)",
    )

    # ── Basic dashboard ───────────────────────────────────────────────────
    dashboard_enabled: bool = Field(
        default=True,
        description=(
            "When false, every /dashboard/* endpoint returns 404. Useful "
            "to disable the dashboard in restricted deployments."
        ),
    )
    dashboard_cache_ttl_seconds: int = Field(
        default=30,
        ge=0,
        description=(
            "Seconds the dashboard aggregator caches results. Set 0 to "
            "always recompute (useful for tests / seeded demos)."
        ),
    )
    dashboard_default_window: str = Field(
        default="7d",
        description=(
            "Default window for dashboard queries when no ?window= is "
            "supplied. Accepts '24h', '7d', '30d', '90d', 'all'."
        ),
    )


settings = Settings()
