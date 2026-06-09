"""Equity vol-surface SDK helpers.

Replaces the 9-keyword `EtiSurfaceParameters(...)` block that was duplicated
~16 times across the codebase (see LSEG_PLATFORM_AUDIT.md §1.3a).

Public API:
- `build_surface_parameters(as_of, **overrides)` — defaults match the
  most-used preset (IMPLIED + SSVI + SPOT + MID + STRIKE x DATE).
- `build_request_item(ric, params, *, outputs, tag)` — handles the
  dict-style `outputs` assignment (the discovery from forward_curve_test_final.py).
- `parse_surface_response(resp)` — returns (DataFrame, spot) for one item.
- `extract_forward_components(resp_item)` — returns spot / forwards / OIS curve
  for one response item; consumed by analytics.forwards.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd
from dateutil import parser as date_parser

# Import path follows lseg_analytics 2.x. If LSEG ever renames this we change it
# in ONE place (here) instead of 16+ scripts.
try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
except ImportError as exc:  # pragma: no cover - import-time SDK guard
    raise ImportError(
        "lseg_analytics is not installed in the current environment. "
        "Run `pip install lseg-analytics` (or `pip install -e .[dev]` from repo root)."
    ) from exc


# Tags accepted by the API today (per forward_curve_test_final.py findings).
# See docs/COMMON_ERRORS.md for what is NOT accepted (e.g. dividend-named outputs).
VALID_OUTPUTS = (
    "Data",
    "UnderlyingSpot",
    "InterestRateCurve",
    "ForwardCurve",
    "SurfaceInformation",
)


def build_surface_parameters(
    as_of: dt.datetime,
    **overrides: Any,
) -> "ev.EtiSurfaceParameters":
    """Build an EtiSurfaceParameters with the canonical defaults.

    The 8 defaults (IMPLIED / SSVI / SPOT / MID / STRIKE / DATE / DEFAULT timestamp)
    were duplicated across forward_curve_test*.py, eq_vol_surface_*.py,
    equity_forward_extraction.py, and batch_forward_extraction.py.

    Pass any keyword to `overrides` to deviate from a default — e.g.
    `build_surface_parameters(as_of, volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SVI)`.
    """
    defaults: dict[str, Any] = dict(
        calculation_date=as_of,
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    defaults.update(overrides)
    return ev.EtiSurfaceParameters(**defaults)


def build_request_item(
    ric: str,
    params: "ev.EtiSurfaceParameters",
    *,
    outputs: tuple[str, ...] | list[str] | None = None,
    tag: str | None = None,
) -> "ev.EtiVolatilitySurfaceRequestItem":
    """Build one EtiVolatilitySurfaceRequestItem.

    `outputs` enriches the response with extras like ForwardCurve / InterestRateCurve.
    Note (per forward_curve_test_final.py): `outputs` must be assigned via
    `request_item['outputs'] = [...]` (dict-style) — it is NOT a constructor kwarg.
    """
    item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=tag or _default_tag(ric),
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_parameters=params,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    if outputs:
        # dict-style assignment is required by the SDK today.
        item["outputs"] = list(outputs)
    return item


def calculate(universe: list["ev.EtiVolatilitySurfaceRequestItem"]) -> Any:
    """Thin pass-through to `ev.calculate` so callers don't import `ev` directly."""
    return ev.calculate(universe=universe)


def parse_surface_response(resp: Any) -> tuple[pd.DataFrame, float]:
    """Convert one calculate() response into (surface_df, spot).

    Surface frame is indexed by expiry (rows) with strikes as columns.
    Consolidates the parsing variants from eq_vol_surface_pull_universe.py:183-205
    and the (broken) eq_vol_surface_test.py:109-128.
    """
    if not resp or not getattr(resp, "data", None):
        raise ValueError("No response data returned")
    item = resp.data[0]
    if item.surface is None:
        raise ValueError("No surface returned for this instrument")

    surface = item.surface
    headers = item.headers
    expiry_dates = item.expiry_dates

    if headers is None or expiry_dates is None:
        # Matrix-only branch: first row is expiries, first column is strikes.
        if not isinstance(surface, list) or not surface or not isinstance(surface[0], list):
            raise ValueError("Unable to parse surface matrix")
        expiry_dates = surface[0][1:]
        strikes = [float(row[0]) for row in surface[1:] if row and len(row) > 1]
        data = [row[1:] for row in surface[1:] if row and len(row) > 1]
        surface_df = pd.DataFrame(data, index=strikes, columns=expiry_dates).T
    else:
        surface_df = pd.DataFrame(surface, index=expiry_dates, columns=headers)

    spot = float(item.underlying_spot) if item.underlying_spot is not None else float("nan")
    return surface_df, spot


def extract_forward_components(data_item: dict[str, Any]) -> dict[str, Any]:
    """Extract spot / forwards / OIS curve from one response item.

    Centralises the field-name lookups (`underlyingSpot`, `forwardCurve.dataPoints`,
    `interestRateCurve.multiCurve.OIS`) that previously appeared in
    equity_forward_extraction.py:94-122 and batch_forward_extraction.py:78-92.

    Returns a dict with keys: spot, valuation_date, forwards, ois_curve.
    `forwards` is a list of (datetime, float) sorted by date.
    """
    spot = float(data_item.get("underlyingSpot") or 0.0)
    forward_curve = data_item.get("forwardCurve") or {}
    interest_curve = data_item.get("interestRateCurve") or {}

    ois_curve = (interest_curve.get("multiCurve") or {}).get("OIS") or []

    valuation_date: dt.datetime | None = None
    if ois_curve:
        valuation_date = date_parser.parse(ois_curve[0]["startDate"])

    forwards: list[tuple[dt.datetime, float]] = []
    data_points = forward_curve.get("dataPoints") or {}
    for date_str, fwd_price in data_points.items():
        forwards.append((date_parser.parse(date_str), float(fwd_price)))
    forwards.sort(key=lambda t: t[0])

    return {
        "spot": spot,
        "valuation_date": valuation_date,
        "forwards": forwards,
        "ois_curve": ois_curve,
    }


def _default_tag(ric: str) -> str:
    """Build a stable surface_tag from a RIC."""
    return ric.replace("@RIC", "").replace(".", "_")
