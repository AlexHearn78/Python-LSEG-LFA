# Claude / Cowork instructions

Read `docs/ARCHITECTURE.md` before suggesting code in this repo. Then:

1. Library code goes in `src/lseg_quant/`. Workflow scripts go in `workflows/`.
2. Use the existing helpers in `lseg_quant.sdk.eq_volatility`, `lseg_quant.analytics.forwards`, `lseg_quant.universe.ric_resolver`, `lseg_quant.io.exports`. Do not rebuild boilerplate that already exists.
3. Never write `dt.datetime(2026, 5, 10)` literals — use `settings.default_calculation_date` or a CLI arg.
4. Never write `ev.EtiSurfaceParameters(...)` directly — use `lseg_quant.sdk.eq_volatility.build_surface_parameters(as_of, **overrides)`.
5. Workflow output goes to `data/outputs/<timestamp>_<domain>/` via `lseg_quant.io.exports.write_run_outputs`. Never write CSVs into repo root.
6. Top-level scripts named like `*_v2.py`, `*_final.py`, `*_test.py` are legacy. Don't model new code on them. The audit at `LSEG_PLATFORM_AUDIT.md` says which to keep.
7. Type-hint public functions. Use `from __future__ import annotations` at the top of every file.
8. Use `logging` not `print` in library code.

When you finish a non-trivial change, run `python -m py_compile $(find src workflows -name "*.py")` and report any failures.
