# Architecture — read this first

This file is the single anchor any AI assistant (Claude, Copilot, GPT) should read before suggesting code in this repo. Keep it under one page so it stays cheap to load.

## What this repo computes

Quant analytics over LSEG market data: equity vol surfaces, equity forward curves and implied dividend yields, OIS zero rates, SocGen COFBox post-analysis, and Starmine credit-risk screening.

## Library vs application split

```
src/lseg_quant/      <-- the library. Importable. Reusable. Pure-ish.
workflows/           <-- entry-point CLI scripts. Thin orchestrators.
examples/            <-- minimal canonical snippets, one per domain (to add).
notebooks/           <-- exploration only; never imported from (to add).
tests/               <-- pytest; @live tests gated on LSEG_LIVE=1 (to add).
data/reference/      <-- checked-in inputs (universe CSVs, ric_overrides.csv).
data/outputs/        <-- gitignored, run-stamped folders per workflow invocation.
```

Anything in `src/lseg_quant/` is library code. If it has `print()` or hardcoded paths, it's in the wrong place. Anything in `workflows/` is a single-purpose CLI; keep these under ~80 LOC by delegating to the library.

## Which SDK is canonical

- `lseg_analytics.*` — for pricing/analytics. Used by ~95% of code. Modules: `pricing.market_data.eq_volatility`, `pricing.market_data.interest_rate_curves`, `socgen.cof_box._functions` (private — wrap via `lseg_quant.sdk.cofbox`).
- `lseg.data` — for Starmine fields and tabular fundamentals only. Limited to `lseg_quant.sdk.data_library` (to be added).

Do not mix the two SDKs inside one module.

## The five library modules an AI should know exist

| Module | Responsibility |
|---|---|
| `lseg_quant.config` | `settings` singleton. Default `as_of` date, IRC template UUIDs, output paths. Override via env vars (`LSEG_*`) or `.env`. |
| `lseg_quant.sdk.eq_volatility` | `build_surface_parameters`, `build_request_item`, `parse_surface_response`, `extract_forward_components`. Replaces the 16+ duplicated boilerplate blocks. |
| `lseg_quant.analytics.forwards` | `interpolate_rate`, `decompose_forwards`, `extract_forwards_batch`, `build_forwards_long_df`. Replaces the byte-identical `interpolate_rate` in two files and the inline q/carry math. |
| `lseg_quant.universe.ric_resolver` | `resolve_identifier(ident, hint_exchange=...)`. Accepts any of: RIC, ISIN, CUSIP, Bloomberg `TICKER EXCHANGE`, plain ticker. Returns priority-ordered RIC candidates. |
| `lseg_quant.universe.loader` | `load_universe_csv(path)`. Format-agnostic — accepts whichever identifier columns are present. |
| `lseg_quant.io.exports` | `make_run_dir`, `write_run_outputs`, `write_run_log`, `write_run_metadata`. Every workflow's outputs land under `data/outputs/<timestamp>_<domain>/`. |

## Cross-cutting rules

- Use `logging.getLogger(__name__)` in library code, never `print()`.
- Never hardcode a calculation date in a script; read `settings.default_calculation_date` or take an `--as-of` CLI arg.
- Never hardcode a RIC suffix list; use `lseg_quant.universe.ric_resolver`.
- Never co-locate outputs with source; write to a run dir from `make_run_dir(domain)`.
- Type-hint every public function. Type hints are the highest-leverage AI hint per character.

## What NOT to touch yet

These remain in place during migration:
- `equity_forward_extraction.py`, `batch_forward_extraction.py` (replaced by `workflows/forward_extraction.py` — keep until parity is verified).
- `pull_cof_data_*.py`, `weekly_loop.py`, `sanity_check.py`, all `eq_vol_surface_*.py` (next sprints).
- The `forward_curve_test*.py` / `forward_discovery_test.py` / `fwd_predictive_test.py` cluster (delete in Sprint 3 after harvesting docs/COMMON_ERRORS.md entries).
