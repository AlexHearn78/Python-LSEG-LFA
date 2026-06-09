"""Forward-curve extraction and decomposition.

Replaces:
- `interpolate_rate` duplicated byte-for-byte in equity_forward_extraction.py:31-62
  and batch_forward_extraction.py:16-43.
- `extract_forward_data` (single-RIC) and `extract_forward_data_batch` —
  consolidated into one batch-aware function with a single-RIC convenience wrapper.
- `decompose_forwards` — the F = S * exp((r - q) * T) inversion that lives inline
  in equity_forward_extraction.py:127-174 and batch_forward_extraction.py:111-216.

Important caveats (preserved from equity_forward_extraction.py:328-332):
- For ETFs, implied q embeds expense-ratio drag, distribution timing, and any
  FX/borrow wedge — it is NOT the underlying basket dividend yield directly.
- For ADRs, implied q embeds borrow cost, foreign withholding tax, and AR/ordinary
  spread dynamics. Cross-check with the foreign primary listing where it matters.
- For non-USD underlyings, the OIS curve returned is in the underlying's native
  currency (TONA, ESTR, SONIA, etc.). Implied q is therefore native-currency
  discounted; do NOT translate to USD-equivalent without explicit FX-and-cross-currency
  basis adjustment.
- `low_confidence=True` rows (T < 18 days) are mathematically fine for F(T) but the
  q decomposition is unstable. Treat those as forwards-only.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from dateutil import parser as date_parser

from lseg_quant.sdk import eq_volatility as ev_helpers

logger = logging.getLogger(__name__)

# Below this T, the implied-q decomposition is unstable.
LOW_CONFIDENCE_T_YEARS = 0.05


# --------------------------------------------------------------------------- #
# Pure-math helpers (unit-testable without the SDK)
# --------------------------------------------------------------------------- #

def interpolate_rate(discount_curve: list[dict], t_years: float) -> float:
    """Linear interpolation of zero rate at `t_years` along an OIS curve.

    `discount_curve` is the list of points returned under
    `interestRateCurve.multiCurve.OIS`, each with `startDate`, `endDate`, `ratePercent`.
    Returns a decimal rate (0.04 = 4%).
    """
    if not discount_curve:
        return 0.0

    sorted_curve = sorted(discount_curve, key=lambda x: x["endDate"])
    val_date = date_parser.parse(sorted_curve[0]["startDate"])

    for curr, nxt in zip(sorted_curve[:-1], sorted_curve[1:]):
        curr_t = (date_parser.parse(curr["endDate"]) - val_date).days / 365.0
        next_t = (date_parser.parse(nxt["endDate"]) - val_date).days / 365.0
        if curr_t <= t_years <= next_t:
            r1 = curr["ratePercent"] / 100.0
            r2 = nxt["ratePercent"] / 100.0
            if next_t == curr_t:  # degenerate; return left endpoint
                return r1
            return r1 + (r2 - r1) * (t_years - curr_t) / (next_t - curr_t)

    # Extrapolate (flat) from the last point.
    return sorted_curve[-1]["ratePercent"] / 100.0


def decompose_forwards(
    spot: float,
    valuation_date: dt.datetime,
    forwards: list[tuple[dt.datetime, float]],
    discount_curve: list[dict],
    *,
    extra_columns: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Invert F = S * exp((r - q) * T) to recover implied q (and carry = r - q).

    Returns a long-form DataFrame with one row per (instrument, expiry).
    `extra_columns` is merged into every row (use it to attach RIC, region, etc.).
    """
    rows: list[dict[str, Any]] = []
    extras = extra_columns or {}

    for fwd_date, fwd_price in forwards:
        t_years = (fwd_date - valuation_date).days / 365.0
        r = interpolate_rate(discount_curve, t_years)

        if t_years > 0 and spot > 0 and fwd_price > 0:
            ln_term = np.log(fwd_price / spot)
            q = r - ln_term / t_years
            carry = r - q
            fwd_premium_pct = (fwd_price / spot - 1.0) * 100.0
        else:
            q = carry = fwd_premium_pct = np.nan

        rows.append({
            **extras,
            "valuation_date": valuation_date.strftime("%Y-%m-%d"),
            "expiry_date": fwd_date.strftime("%Y-%m-%d"),
            "T_years": round(t_years, 4),
            "spot": round(spot, 4),
            "F": round(fwd_price, 4),
            "forward_premium_pct": _round_or_nan(fwd_premium_pct, 4),
            "r_pct": round(r * 100, 4),
            "implied_q_pct": _round_or_nan(q * 100, 4),
            "carry_pct": _round_or_nan(carry * 100, 4),
            "low_confidence": t_years < LOW_CONFIDENCE_T_YEARS,
        })

    return pd.DataFrame(rows)


def _round_or_nan(x: float, ndigits: int) -> float:
    return round(x, ndigits) if not np.isnan(x) else np.nan


# --------------------------------------------------------------------------- #
# SDK-coupled extraction (batch-aware; single-RIC is a wrapper over batch=1)
# --------------------------------------------------------------------------- #

@dataclass
class ForwardExtractionResult:
    """One per input instrument. `error` is set iff extraction failed."""
    meta: dict[str, Any]
    spot: float = 0.0
    valuation_date: dt.datetime | None = None
    forwards: list[tuple[dt.datetime, float]] | None = None
    ois_curve: list[dict] | None = None
    error: str | None = None


def extract_forwards_batch(
    instruments: list[dict[str, Any]],
    as_of: dt.datetime,
    *,
    batch_size: int = 10,
) -> list[ForwardExtractionResult]:
    """Pull forward components for many instruments via batched calculate() calls.

    Each `instruments` entry must include a `ric` key; everything else is carried
    through into result.meta and (eventually) the output rows.
    """
    results: list[ForwardExtractionResult] = []
    params = ev_helpers.build_surface_parameters(as_of)

    for batch_start in range(0, len(instruments), batch_size):
        batch = instruments[batch_start : batch_start + batch_size]

        request_items = [
            ev_helpers.build_request_item(
                meta["ric"],
                params,
                outputs=("Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve"),
                tag=f"{meta['ric']}_batch",
            )
            for meta in batch
        ]

        try:
            response = ev_helpers.calculate(request_items)
        except Exception as exc:  # SDK can raise many specific exceptions
            logger.warning("Batch failed entirely (%s): %s", len(batch), exc)
            results.extend(ForwardExtractionResult(meta=m, error=str(exc)) for m in batch)
            continue

        data = response.get("data", []) if hasattr(response, "get") else getattr(response, "data", [])
        for i, meta in enumerate(batch):
            if i >= len(data):
                results.append(ForwardExtractionResult(meta=meta, error="No data in response"))
                continue
            try:
                comps = ev_helpers.extract_forward_components(data[i])
                results.append(ForwardExtractionResult(
                    meta=meta,
                    spot=comps["spot"],
                    valuation_date=comps["valuation_date"],
                    forwards=comps["forwards"],
                    ois_curve=comps["ois_curve"],
                ))
            except Exception as exc:
                results.append(ForwardExtractionResult(meta=meta, error=str(exc)))

    return results


def extract_forwards_for_ric(ric: str, as_of: dt.datetime) -> ForwardExtractionResult:
    """Convenience: single-RIC wrapper around extract_forwards_batch."""
    out = extract_forwards_batch([{"ric": ric}], as_of=as_of, batch_size=1)
    return out[0]


# --------------------------------------------------------------------------- #
# Top-level orchestration: extract + decompose into one DataFrame
# --------------------------------------------------------------------------- #

def build_forwards_long_df(
    results: list[ForwardExtractionResult],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Turn extraction results into (long_df, summary_df, failures).

    Output schemas match `forwards_output/forwards_long.csv` and
    `forwards_output/forwards_summary.csv` produced by batch_forward_extraction.py
    so a parity diff is straightforward.
    """
    rows: list[dict] = []
    summaries: list[dict] = []
    failures: list[dict] = []

    for r in results:
        if r.error or r.valuation_date is None or not r.forwards:
            failures.append({"ric": r.meta.get("ric"), **r.meta, "error": r.error or "no forwards"})
            continue

        per_inst = decompose_forwards(
            spot=r.spot,
            valuation_date=r.valuation_date,
            forwards=r.forwards,
            discount_curve=r.ois_curve or [],
            extra_columns=r.meta,
        )
        rows.extend(per_inst.to_dict(orient="records"))

        valid_q = per_inst["implied_q_pct"].dropna().tolist()
        if valid_q and len(per_inst) > 1:
            slope = float(np.polyfit(per_inst["T_years"], per_inst["implied_q_pct"].fillna(0), 1)[0])
        else:
            slope = float("nan")

        summaries.append({
            "ric": r.meta.get("ric"),
            **{k: v for k, v in r.meta.items() if k != "ric"},
            "spot": r.spot,
            "valuation_date": r.valuation_date.strftime("%Y-%m-%d"),
            "n_tenors": len(per_inst),
            "max_T": float(per_inst["T_years"].max()) if len(per_inst) else 0.0,
            "min_q_pct": _round_or_nan(min(valid_q), 4) if valid_q else float("nan"),
            "median_q_pct": _round_or_nan(float(np.median(valid_q)), 4) if valid_q else float("nan"),
            "max_q_pct": _round_or_nan(max(valid_q), 4) if valid_q else float("nan"),
            "slope_q_per_year": _round_or_nan(slope, 4),
        })

    long_df = pd.DataFrame(rows)
    summary_df = pd.DataFrame(summaries)
    return long_df, summary_df, failures
