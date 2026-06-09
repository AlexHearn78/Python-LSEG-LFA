"""Single source of truth for configuration.

Today this carries:
- `DEFAULT_CALCULATION_DATE` — replaces the 16+ hardcoded `dt.datetime(2025, 4, 18)` /
  `dt.datetime(2026, 5, 10)` literals scattered across scripts.
- IRC template UUIDs — previously duplicated in `sanity_check.py` and `weekly_loop.py`.
- Output root — where workflow outputs land.

Override any setting via environment variables (prefix `LSEG_`) or a `.env` file at
repo root. See `.env.example` (when added) for the full list.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _latest_business_day(today: dt.date | None = None) -> dt.datetime:
    """Return the most recent weekday (Mon–Fri) at midnight UTC.

    Used as the default `as_of` date when the caller doesn't pass one explicitly.
    Replaces hardcoded literals like `dt.datetime(2026, 5, 10)`.
    """
    today = today or dt.date.today()
    # If today is Sat/Sun, walk back to Friday.
    while today.weekday() >= 5:
        today -= dt.timedelta(days=1)
    return dt.datetime(today.year, today.month, today.day)


class Settings(BaseSettings):
    """Application settings, loaded from env vars or .env."""

    model_config = SettingsConfigDict(
        env_prefix="LSEG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Auth (handled by the SDKs; we don't read the key here, just document it) ---
    # LSEG_APP_KEY              — set in env, consumed by lseg-data / lseg-analytics SDKs
    # LSEG_PROFILE              — optional; named profile from ~/.lseg/credentials.ini

    # --- Date defaults ---
    default_calculation_date: dt.datetime = _latest_business_day()

    # --- IRC template UUIDs (today hardcoded in sanity_check.py / weekly_loop.py) ---
    eur_ois_template_id: str = "c7a3eff1-abe8-4061-9f5e-83a76c09ee09"
    usd_ois_template_id: str = "ce157336-e0c3-49e4-8b23-c1489bfb3c19"

    # --- Paths ---
    repo_root: Path = Path(__file__).resolve().parents[2]

    @property
    def output_root(self) -> Path:
        return self.repo_root / "data" / "outputs"

    @property
    def reference_root(self) -> Path:
        return self.repo_root / "data" / "reference"


# Module-level singleton — import this, don't construct your own.
settings = Settings()
