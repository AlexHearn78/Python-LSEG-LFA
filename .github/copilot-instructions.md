# GitHub Copilot — repo instructions

This is a quant analytics codebase over the LSEG `lseg-analytics` and `lseg-data` SDKs.

## Project layout

- `src/lseg_quant/` — library code. Importable.
- `workflows/` — CLI entry-point scripts. ~80 LOC, delegate to library.
- `data/reference/` — checked-in inputs.
- `data/outputs/` — gitignored, run-stamped results.

## Coding rules

1. **Don't rebuild boilerplate.** Use `lseg_quant.sdk.eq_volatility.build_surface_parameters(as_of, **overrides)` for vol-surface params; `build_request_item(ric, params, outputs=...)` for request items; `extract_forward_components(item)` to pull spot/forwards/OIS off a response.
2. **Don't hardcode dates.** Use `lseg_quant.config.settings.default_calculation_date` or a CLI `--as-of` arg.
3. **Don't hardcode RIC suffix lookups.** Use `lseg_quant.universe.ric_resolver.resolve_identifier(ident, hint_exchange=...)`.
4. **Don't write `print()` in library code.** Use `logging.getLogger(__name__)`.
5. **Write CSVs only via `lseg_quant.io.exports.write_run_outputs(domain, ...)`** which stamps a run directory under `data/outputs/`.
6. Always include `from __future__ import annotations` and full type hints on public functions.
7. SDK response keys are camelCase (`forwardCurve.dataPoints`, `underlyingSpot`, `interestRateCurve.multiCurve.OIS`). The `interest_rate_curves` zero rate is in **percent** (`.rate.value / 100`).

## Files to ignore for suggestions

`forward_curve_test*.py`, `forward_discovery_test.py`, `fwd_predictive_test.py`, `eq_vol_surface_test.py`, and any `*_v2.py` / `*_final.py` are legacy. They are scheduled for deletion. Don't model new code on them.

See `LSEG_PLATFORM_AUDIT.md` and `docs/ARCHITECTURE.md` for the full design.
