"""RIC resolution.

Consolidates:
- `KNOWN_INDEX_RICS` (29 entries) duplicated in run_ivm_real_coverage.py:25-54
  and historical_basket_stage1.py:34-63.
- `SUFFIX_TO_RIC` (~30 entries) duplicated in the same two files plus a
  partially-overlapping `EXCHANGE_SUFFIXES` dict in eq_vol_surface_pull_universe.py:94-126.
- `FALLBACK_SUFFIXES` from eq_vol_surface_pull_universe.py:122-126.
- The candidate-generation logic from eq_vol_surface_pull_universe.py:157-171
  (now generalised to handle ISIN/CUSIP/ticker inputs, not just Bloomberg-style names).
- The override-loading logic from run_ivm_real_coverage.py:85-101.

Public API:
- `resolve_identifier(ident, *, hint=None)` — main entry point. Pass any of
  ISIN / CUSIP / RIC / Bloomberg ticker / plain ticker; returns an ordered
  list of candidate RICs to try against the SDK.
- `load_overrides(path)` — load a CSV mapping arbitrary keys to canonical RICs.
- `apply_override(ident, overrides)` — short-circuit resolution if the input
  has a manual mapping.
"""
from __future__ import annotations

import re
from pathlib import Path

# --------------------------------------------------------------------------- #
# Reference data (single source of truth)
# --------------------------------------------------------------------------- #

KNOWN_INDEX_RICS: dict[str, str] = {
    "SPX": ".SPX@RIC",
    "NDX": ".NDX@RIC",
    "RTY": ".RUT@RIC",
    "DAX": ".GDAXI@RIC",
    "CAC": ".FCHI@RIC",
    "UKX": ".FTSE@RIC",
    "SX5E": ".STOXX50E@RIC",
    "SXXP": ".STOXX@RIC",
    "NKY": ".N225@RIC",
    "TPX": ".TOPX@RIC",
    "HSI": ".HSI@RIC",
    "HSCEI": ".HSCE@RIC",
    "AS51": ".AXJO@RIC",
    "SMI": ".SSMI@RIC",
    "N225": ".N225@RIC",
    "IBEX": ".IBEX@RIC",
    "KOSPI": ".KS11@RIC",
    "NSEI": ".NSEI@RIC",
    "OMX": ".OMXS30@RIC",
    "STOXX50E": ".STOXX50E@RIC",
    "ESX5": ".STOXX50E@RIC",
    "EUROSTOXX": ".STOXX50E@RIC",
    "EUX": ".STOXX50E@RIC",
    "FTMIB": ".FTMIB@RIC",
    "CCMP": ".IXIC@RIC",
    "DJI": ".DJI@RIC",
    "JKSE": ".JKSE@RIC",
    "SSEC": ".SSEC@RIC",
}

# Bloomberg-style country/exchange suffix → priority-ordered list of RIC suffixes.
SUFFIX_TO_RIC: dict[str, list[str]] = {
    "US": [".P@RIC", "@RIC", ".K@RIC", ".O@RIC", ".N@RIC"],
    "LN": [".L@RIC"],
    "GB": [".L@RIC"],
    "GR": [".DE@RIC"],
    "DE": [".DE@RIC"],
    "FP": [".PA@RIC"],
    "FR": [".PA@RIC"],
    "NA": [".AS@RIC"],
    "NL": [".AS@RIC"],
    "SM": [".MC@RIC"],
    "ES": [".MC@RIC"],
    "IM": [".MI@RIC"],
    "IT": [".MI@RIC"],
    "SW": [".S@RIC"],
    "CH": [".SW@RIC"],
    "HK": [".HK@RIC"],
    "JP": [".T@RIC"],
    "AU": [".AX@RIC"],
    "CN": [".SS@RIC", ".SZ@RIC"],
    "CA": [".TO@RIC", ".CN@RIC"],
    "KR": [".KS@RIC"],
    "IN": [".NS@RIC"],
    "ID": [".JK@RIC"],
    "PL": [".WA@RIC"],
    "SE": [".ST@RIC"],
    "NO": [".OL@RIC"],
    "DK": [".CO@RIC"],
    "FI": [".HE@RIC"],
    "BE": [".BB@RIC"],
}

# Last-resort suffixes when no exchange hint is available.
FALLBACK_SUFFIXES: list[str] = [
    ".O@RIC", ".N@RIC", ".P@RIC", ".K@RIC",  # US first
    ".L@RIC", ".DE@RIC", ".PA@RIC", ".AS@RIC", ".MC@RIC", ".MI@RIC",
    ".SW@RIC", ".HK@RIC", ".T@RIC", ".AX@RIC",
    ".SS@RIC", ".SZ@RIC", ".KS@RIC", ".TO@RIC", ".OL@RIC", ".ST@RIC",
]


# --------------------------------------------------------------------------- #
# Identifier shape detection
# --------------------------------------------------------------------------- #

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")
_CUSIP_RE = re.compile(r"^[0-9A-Z]{8}\d$")
_RIC_RE = re.compile(r"^.+@RIC$")
_BBG_NAME_RE = re.compile(r"^([A-Z0-9.\-]+)\s+([A-Z]{2,4})$")  # e.g. "AAPL US", ".SPX US"


def looks_like_isin(s: str) -> bool:
    return bool(_ISIN_RE.match(s.strip().upper()))


def looks_like_cusip(s: str) -> bool:
    return bool(_CUSIP_RE.match(s.strip().upper()))


def looks_like_ric(s: str) -> bool:
    return bool(_RIC_RE.match(s.strip()))


def parse_bloomberg_name(s: str) -> tuple[str, str] | None:
    """Parse 'TICKER EXCHANGE' (e.g. 'AAPL US', 'SHEL LN'). Returns (ticker, suffix) or None."""
    m = _BBG_NAME_RE.match(s.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

def resolve_identifier(
    ident: str,
    *,
    hint_exchange: str | None = None,
    overrides: dict[str, str] | None = None,
) -> list[str]:
    """Return an ordered list of candidate RICs to try against the SDK.

    The dispatch order:
    1. If the identifier has an explicit override → return it alone.
    2. If it already looks like a RIC → return it alone.
    3. If it's a known index ticker (SPX, NKY, etc.) → use KNOWN_INDEX_RICS.
    4. If it parses as 'TICKER EXCHANGE' (Bloomberg-style) → use SUFFIX_TO_RIC[exchange].
    5. If `hint_exchange` is provided → use SUFFIX_TO_RIC[hint_exchange].
    6. If it looks like an ISIN → return as-is (LSEG resolves some ISINs natively).
    7. If it looks like a CUSIP → return as-is, but the caller should expect
       failures and fall through to fallback suffixes if upstream resolution is wired in.
    8. Otherwise → ticker + FALLBACK_SUFFIXES.

    Always end with the bare `{ident}@RIC` form as a last-resort attempt.
    """
    s = ident.strip()
    overrides = overrides or {}

    # 1. Manual overrides win.
    if s in overrides:
        return [overrides[s]]

    # 2. Already a RIC.
    if looks_like_ric(s):
        return [s]

    # 3. Known index ticker (case-insensitive match).
    upper = s.upper()
    if upper in KNOWN_INDEX_RICS:
        return [KNOWN_INDEX_RICS[upper]]

    # 4. Bloomberg-style "TICKER EXCHANGE".
    parsed = parse_bloomberg_name(s)
    if parsed is not None:
        ticker, exchange = parsed
        candidates: list[str] = []
        for suffix in SUFFIX_TO_RIC.get(exchange, []):
            candidates.append(f"{ticker}{suffix}")
        if not candidates:
            candidates.append(f"{ticker}@RIC")
        return _dedupe(candidates + _fallback_candidates(ticker))

    # 5. Caller-provided exchange hint.
    if hint_exchange and hint_exchange in SUFFIX_TO_RIC:
        return _dedupe(
            [f"{s}{suffix}" for suffix in SUFFIX_TO_RIC[hint_exchange]]
            + _fallback_candidates(s)
        )

    # 6. ISIN — pass through; LSEG can resolve some natively.
    if looks_like_isin(s):
        return [s, f"{s}@RIC"]

    # 7. CUSIP — pass through with a fallback.
    if looks_like_cusip(s):
        return [s, f"{s}@RIC"]

    # 8. Plain ticker — try all fallback suffixes.
    return _dedupe(_fallback_candidates(s))


def _fallback_candidates(ticker: str) -> list[str]:
    return [f"{ticker}{suffix}" for suffix in FALLBACK_SUFFIXES] + [f"{ticker}@RIC"]


def _dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# --------------------------------------------------------------------------- #
# Override file loading
# --------------------------------------------------------------------------- #

def load_overrides(path: str | Path) -> dict[str, str]:
    """Load a CSV mapping `key,override_ric[,note]` into a dict.

    Compatible with the existing `ric_overrides.csv` format used by
    run_ivm_real_coverage.py:85-101. Missing file returns {} (not an error).
    """
    p = Path(path)
    if not p.exists():
        return {}

    overrides: dict[str, str] = {}
    with p.open("r", encoding="utf-8") as f:
        first = True
        for line in f:
            if first:
                first = False
                continue  # header row
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(",", 2)
            if len(parts) < 2:
                continue
            key = parts[0].strip()
            override = parts[1].strip()
            if key and override:
                overrides[key] = override
    return overrides
