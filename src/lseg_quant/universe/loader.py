"""Universe CSV loader — format-agnostic.

Accepts a CSV with any subset of these columns (case-insensitive):
  ric, ticker, isin, cusip, bloomberg, name, currency, region, type, exchange

Produces a list of `UniverseEntry` dicts where `ric_candidates` is the priority-
ordered list of RICs to try against the SDK. Subsequent workflows iterate over
the candidates until one succeeds, then record which one worked for caching.

This replaces:
- The 4-line block format parsed in eq_vol_surface_pull_universe.py:142-154
  and run_ivm_real_coverage.py:56-82.
- The CSV-with-fixed-columns approach in batch_forward_extraction.py:220-253.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from lseg_quant.universe.ric_resolver import (
    KNOWN_INDEX_RICS,
    SUFFIX_TO_RIC,
    load_overrides,
    resolve_identifier,
)


# Column-name aliases — we accept whatever case / form the user supplies.
_COLUMN_ALIASES: dict[str, str] = {
    "ric": "ric",
    "ticker": "ticker",
    "isin": "isin",
    "cusip": "cusip",
    "bloomberg": "bloomberg",
    "bbg": "bloomberg",
    "instrument name": "bloomberg",  # client_volatility_coverage_*.csv uses this
    "name": "name",
    "long_name": "name",
    "longname": "name",
    "currency": "currency",
    "ccy": "currency",
    "region": "region",
    "type": "type",
    "exchange": "exchange",
    "country": "exchange",
}

# Identifier columns ranked by resolution priority (best → worst).
_IDENT_PRIORITY: list[str] = ["ric", "bloomberg", "ticker", "isin", "cusip"]


def load_universe_csv(
    path: str | Path,
    *,
    overrides_path: str | Path | None = None,
    skip_summary_rows: bool = True,
) -> list[dict[str, Any]]:
    """Load a CSV and produce a list of universe entries with RIC candidates.

    Each returned entry has at least:
      - 'ric_candidates': priority-ordered list of RICs to try
      - 'source_identifier': the value used to build the candidates
      - all original columns (lowercased, alias-resolved)

    `overrides_path` (defaults to `<repo>/data/reference/ric_overrides.csv` if it
    exists) lets you short-circuit resolution for known troublesome inputs.
    """
    df = pd.read_csv(path)
    df = _normalise_columns(df)

    if skip_summary_rows:
        # Tolerate the "SUMMARY: x/y instruments available" footer that
        # client_volatility_coverage_*.csv carries.
        if "bloomberg" in df.columns:
            mask = ~df["bloomberg"].astype(str).str.startswith("SUMMARY", na=False)
            df = df[mask].copy()

    overrides = load_overrides(overrides_path) if overrides_path else {}

    entries: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        identifier, candidates = _resolve_row(row, overrides)
        if not candidates:
            continue
        entry: dict[str, Any] = {col: row.get(col) for col in df.columns}
        entry["source_identifier"] = identifier
        entry["ric_candidates"] = candidates
        # Convenience: the first candidate is what most workflows will try first.
        entry["ric"] = candidates[0]
        entries.append(entry)
    return entries


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        renamed[col] = _COLUMN_ALIASES.get(key, key)
    return df.rename(columns=renamed)


def _resolve_row(row: pd.Series, overrides: dict[str, str]) -> tuple[str, list[str]]:
    """Pick the best identifier for this row and return (identifier, candidates)."""
    hint = _coerce_str(row.get("exchange")) or _coerce_str(row.get("region"))

    for col in _IDENT_PRIORITY:
        if col not in row:
            continue
        val = _coerce_str(row[col])
        if not val:
            continue
        candidates = resolve_identifier(val, hint_exchange=hint, overrides=overrides)
        if candidates:
            return val, candidates

    # Last resort: try the row's name.
    name = _coerce_str(row.get("name"))
    if name:
        return name, resolve_identifier(name, hint_exchange=hint, overrides=overrides)

    return "", []


def _coerce_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    return str(val).strip()


# Re-exports for callers that just want the constants.
__all__ = [
    "load_universe_csv",
    "KNOWN_INDEX_RICS",
    "SUFFIX_TO_RIC",
]
