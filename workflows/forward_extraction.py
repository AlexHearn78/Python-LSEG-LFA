"""Forward extraction workflow.

Replaces:
- `equity_forward_extraction.py` (single-RIC variant; ~250 LOC)
- `batch_forward_extraction.py` (batched variant reading from CSV; ~370 LOC)

Now ~80 LOC because every reusable bit lives in `lseg_quant.*`.

Run from repo root:

    python workflows/forward_extraction.py \
        --universe data/reference/client_volatility_coverage_may6_2026.csv \
        --as-of 2026-05-10

Outputs land in `data/outputs/<timestamp>_forwards/` as:
    long.csv          — one row per (instrument, expiry)
    summary.csv       — one row per instrument
    failures.json     — entries that couldn't be extracted
    run_log.txt       — wall-clock + counts + caveats
    metadata.json     — inputs / git sha / package version
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from pathlib import Path

# Make `src/` importable when running this file directly (without `pip install -e .`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lseg_quant import __version__  # noqa: E402
from lseg_quant.analytics.forwards import build_forwards_long_df, extract_forwards_batch  # noqa: E402
from lseg_quant.config import settings  # noqa: E402
from lseg_quant.io.exports import (  # noqa: E402
    make_run_dir,
    write_run_log,
    write_run_metadata,
    write_run_outputs,
)
from lseg_quant.universe.loader import load_universe_csv  # noqa: E402

logger = logging.getLogger("forward_extraction")


CAVEATS = """\
Caveats (from analytics.forwards docstring):
- ETF implied q embeds expense-ratio drag, distribution timing, FX/borrow wedge.
- ADR implied q embeds borrow cost, foreign withholding tax, AR/ordinary spread.
- Non-USD underlyings: OIS curve is in native currency (TONA/ESTR/SONIA/...).
  Implied q figures are native-currency-discounted.
- low_confidence=True rows (T < ~18 days) — treat as forwards-only.
"""


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    run_dir = make_run_dir("forwards")
    logger.info("Run directory: %s", run_dir)

    # --- Load and resolve the universe ---
    overrides_path = args.overrides or (settings.reference_root / "ric_overrides.csv")
    entries = load_universe_csv(args.universe, overrides_path=overrides_path)
    logger.info("Loaded %d universe entries from %s", len(entries), args.universe)

    # --- Pull forwards (batched) ---
    as_of = args.as_of or settings.default_calculation_date
    t0 = time.time()
    results = extract_forwards_batch(entries, as_of=as_of, batch_size=args.batch_size)
    elapsed = time.time() - t0

    long_df, summary_df, failures = build_forwards_long_df(results)

    # --- Write outputs ---
    write_run_outputs(
        "forwards",
        run_dir=run_dir,
        long=long_df if not long_df.empty else None,
        summary=summary_df if not summary_df.empty else None,
        failures=failures or None,
    )
    write_run_log(
        run_dir,
        _format_run_log(
            as_of=as_of,
            n_universe=len(entries),
            n_success=len(summary_df),
            n_failed=len(failures),
            n_tenors=int(summary_df["n_tenors"].sum()) if not summary_df.empty else 0,
            elapsed_s=elapsed,
        ),
    )
    write_run_metadata(
        run_dir,
        {
            "package_version": __version__,
            "as_of": as_of.isoformat(),
            "universe_path": str(args.universe),
            "overrides_path": str(overrides_path) if Path(overrides_path).exists() else None,
            "batch_size": args.batch_size,
            "n_universe": len(entries),
            "n_success": len(summary_df),
            "n_failed": len(failures),
            "elapsed_seconds": round(elapsed, 1),
        },
    )

    logger.info(
        "Done. success=%d failed=%d wall=%.1fs → %s",
        len(summary_df), len(failures), elapsed, run_dir,
    )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract equity forward curves and decompose into implied q.")
    p.add_argument(
        "--universe", required=True, type=Path,
        help="Path to universe CSV. Accepts any of: ric, ticker, isin, cusip, bloomberg columns.",
    )
    p.add_argument(
        "--as-of", type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
        default=None, help="Calculation date (YYYY-MM-DD). Defaults to latest business day.",
    )
    p.add_argument(
        "--overrides", type=Path, default=None,
        help="Optional path to RIC overrides CSV (defaults to data/reference/ric_overrides.csv).",
    )
    p.add_argument("--batch-size", type=int, default=10)
    return p.parse_args(argv)


def _format_run_log(*, as_of: dt.datetime, n_universe: int, n_success: int,
                    n_failed: int, n_tenors: int, elapsed_s: float) -> str:
    return (
        "Forward Curve Extraction Run Log\n"
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Calculation date: {as_of.strftime('%Y-%m-%d')}\n"
        f"Universe size:    {n_universe}\n"
        f"Successful:       {n_success}\n"
        f"Failed:           {n_failed}\n"
        f"Total tenors:     {n_tenors}\n"
        f"Wall time:        {elapsed_s:.1f}s\n\n"
        + CAVEATS
    )


if __name__ == "__main__":
    raise SystemExit(main())
