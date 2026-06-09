# LSEG Quant Analytics Repository — Architectural Audit & Migration Plan

**Author:** Principal-engineer review (Claude)
**Date:** 2026-05-10
**Scope:** `PythonLSEGV2/` — 43 `.py` files, ~6,766 LOC, flat top-level layout, single `.venv`, no `pyproject.toml`, no VCS metadata, no tests.

This is grounded in the actual files in this folder. Every weakness and recommendation cites code by filename and line number. It is a structural and AI-workflow audit, not a clean-up checklist.

---

## 0. Executive summary (the truth)

You don't have an analytics codebase yet. You have **~40 single-purpose scripts that share a copy-pasted SDK boilerplate**, plus a `.venv` and a pile of CSV/PNG outputs co-located with source. The business logic that matters — implied dividend yield decomposition, OIS-curve interpolation, vol-surface coverage scanning, RIC resolution, COFBox post-analysis — is real and works, but it lives inline in scripts and is duplicated across 3–6 places each.

The single biggest leverage you have right now is **not** rewriting analytics. It's **extracting four to six small modules** that the existing scripts can keep importing, and putting the project under a real `pyproject.toml` with a package layout. Everything else flows from that.

A flat folder of 100+ artefacts also actively hurts AI-assisted development: every Copilot/Claude/GPT chat re-discovers the same boilerplate, repeats the same wrong guesses about the SDK shape, and re-explains things that should be in a stable `ARCHITECTURE.md`. The token tax on this is real and recurring.

Top three findings, by leverage:

1. **One canonical `EtiSurfaceParameters` block** is duplicated verbatim **16+ times** (see Phase 1 §3a). One helper kills most of the duplication in this repo.
2. **Two parallel SDKs** are in use (`lseg_analytics.*` and `lseg.data`) with different auth models. There is no central session module, no env config, and no decision recorded about which is canonical.
3. **Multiple draft "test" files (`forward_curve_test`, `_v2`, `_v3`, `_final`) are versioned by filename**, not git. Each is a one-shot SDK probe that should be a single notebook entry or a single discovery script — they are now permanent context-bloat for any AI assistant.

---

# PHASE 1 — Repository analysis

## 1.1 High-level architectural assessment

| Dimension | State | Evidence |
|---|---|---|
| Layout | Flat — 101 entries at top level | `ls /PythonLSEGV2` |
| Package structure | None | No `pyproject.toml`, no `src/`, no `__init__.py` outside `.venv` |
| Tests | None | Files named `*_test.py` are SDK probes, not pytests; no `tests/` dir |
| Config | Inline constants, hardcoded UUIDs and dates | `sanity_check.py:5-6`, `weekly_loop.py:7-8` (same UUIDs); 16+ hardcoded `calculation_date` literals |
| Auth/session | Implicit for `lseg_analytics`, explicit `ld.open_session()` for `lseg.data` only in `ninety_one_credit_screen.py:101-108` | Inconsistent |
| I/O | CSVs/PNGs/logs co-located with source | `cof_*.csv`, `fwd_cof_*.png`, `coverage_results*.csv`, `*_run.log`, `grep_*.txt` all at top level |
| Cross-module reuse | Only via accidental same-cwd imports | `eq_vol_surface_full_coverage.py:2` does `from eq_vol_surface_pull_universe import get_surface_info` — works only because cwd is workspace |
| Versioning | By filename suffix | `forward_curve_test.py`, `_v2.py`, `_v3.py`, `_final.py`; `chart_term_structure.py` + `_v2.py`; `bbg_to_ric.csv` + `_v2.csv` + `_may6_2026.csv`; `coverage_results.csv` + `_v2.csv` + `_may6_2026.csv` |
| Dependency management | Three lines in `requirements.txt`, ignored thereafter | `requirements.txt` lists `lseg-data` only; actual code imports `lseg_analytics` (different SDK) and never installs from this file |

The repository's organising principle is currently *chronology* — files accumulate as new tasks arrive, with `_v2`/`_final`/`_may6_2026` suffixes substituting for source control. That's the central pathology.

## 1.2 Folder-by-folder

There is one folder, plus `.venv`, `__pycache__`, and `forwards_output/`.

- `./` — everything
- `./forwards_output/` — output of `batch_forward_extraction.py` (`forwards_failures.csv`, `forwards_run_log.txt`). The only file that writes into a subfolder. Other scripts dump CSVs at top level.
- `./.venv/` — local venv. Should not be in source control; is currently the only Python install record.
- `./__pycache__/` — leftover compiled artefacts in workspace root.

There is nothing else to analyse folder-by-folder, which is itself the finding.

## 1.3 Duplication, dead code, anti-patterns

### a) The duplicated `EtiSurfaceParameters` block (highest-impact duplication)

This 9-keyword constructor call is repeated **at least 16 times** with the same defaults and only the `calculation_date` varying:

```python
ev.EtiSurfaceParameters(
    calculation_date=...,
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)
```

Confirmed locations: `batch_forward_extraction.py:51-60`, `eq_vol_surface_pull_universe.py:128-137`, `eq_vol_surface_test.py:87-96`, `equity_forward_extraction.py:68-77`, `forward_curve_test.py:88-96` and `:209-217` and `:339-347`, `forward_curve_test_final.py:16-24`, `forward_curve_test_v2.py:22-31`, `forward_curve_test_v3.py:16-24`, `forward_discovery_test.py:32` and `:213`, `test_forward_default.py:12`, `test_outputs.py:7`, `validate_ric_rewrites.py:72` and `:156`. (Note: `forward_curve_test.py` alone has 3 copies.)

### b) `interpolate_rate(discount_curve, T_years)` — duplicated linear-interp helper

`equity_forward_extraction.py:31-62` and `batch_forward_extraction.py:16-43` are byte-identical aside from comment formatting. Same algorithm, same edge cases, same `dateutil.parser.parse(...)` calls.

### c) `KNOWN_INDEX_RICS` and `SUFFIX_TO_RIC` dicts

`run_ivm_real_coverage.py:25-54` and `historical_basket_stage1.py:34-94` define the same `KNOWN_INDEX_RICS` (29 entries) and same `SUFFIX_TO_RIC` mappings. `historical_basket_stage1.py:29` even says *"reused from run_ivm_real_coverage.py"* in a comment — copy-paste reuse, not import reuse. `eq_vol_surface_pull_universe.py:94-126` defines its own `EXCHANGE_SUFFIXES` and `FALLBACK_SUFFIXES`, partially overlapping with `SUFFIX_TO_RIC` but using different keys (e.g. `'GR'` → `.DE@RIC` in both, but `'KR'` → `.KS@RIC` in one and `'KS'` not in the other).

### d) IRC template UUIDs

`sanity_check.py:5-6` and `weekly_loop.py:7-8` both load:
- `irc.load(resource_id='c7a3eff1-abe8-4061-9f5e-83a76c09ee09')` — EUR ESTR template
- `irc.load(resource_id='ce157336-e0c3-49e4-8b23-c1489bfb3c19')` — USD SOFR template

…and both do the same `next((p for p in eur_points if p['tenor'] in ['12M', '1Y']), None)` parsing. If LSEG rotates either UUID, two files break with no central lookup.

### e) `pull_cof_data_spx.py` and `pull_cof_data_sx5e.py`

51 lines each, byte-identical except for `"SPX_USD_SOFR"`/`"fwd_cof_spx_*"` ↔ `"SX5E_EUR_EON"`/`"fwd_cof_sx5e_*"`. Pure parameterisation duplication.

### f) Forward-curve "test" series

`forward_curve_test.py` (374 LOC), `forward_curve_test_v2.py` (117), `forward_curve_test_v3.py` (104), `forward_curve_test_final.py` (142), `forward_discovery_test.py` (285) all do the same thing: build a vol-surface request, set `outputs=["Data","UnderlyingSpot","InterestRateCurve","ForwardCurve",...]`, print the response keys. They are **SDK exploration scratch** that succeeded on `_final`. Everything before `_final` is dead context that AI assistants will keep re-reading.

### g) Mock scaffolding that never engages

`eq_vol_surface_test.py:8-58` defines a 50-line `MockEV` fallback. `REAL_EV` is set from a try/except on the SDK import; in a working venv this is always True, so the entire mock block is dead in production but present in every chat context. Worse, the file has **clear indentation bugs** between lines 116–159 — module-level statements indented as if they were inside a function — meaning the file likely doesn't run as written. It is not currently exercised by any tests.

### h) Output detritus in source root

23 CSVs, 17 PNGs, 9 logs, 2 large `grep_*` text dumps (`grep_isin.txt` is 793 KB) sit alongside `.py` files. A few specific offenders:
- `coverage_run_log.txt` (108 KB), `run_output.txt` (188 KB) — runtime logs in version-controllable space.
- `grep_isin.txt` (794 KB), `grep_output.txt` (22 KB) — ad-hoc grep dumps committed (or about to be) into the project root.
- `cof_analysis_results.json` (3.4 MB) — raw API dump kept as source.

These don't cause runtime issues; they cause AI-context issues. Any directory listing pulled into a prompt blows the budget on chaff.

## 1.4 Domain classification

| Domain | Files | Notes |
|---|---|---|
| **EQ vol surfaces** | `eq_vol_surface_test.py`, `eq_vol_surface_pull_universe.py`, `eq_vol_surface_full_coverage.py`, `test_japan_vol_surface.py`, `run_ivm_real_coverage.py`, `historical_basket_stage1.py`, `check_surface_matrix.py`, `generate_surface_coverage_csv.py`, `validate_ric_rewrites*.py`, `find_test_tickers.py`, `find_valid_pairs.py`, `analyze_coverage.py`, `analyze_may6_failures.py`, `compare_coverage.py`, `apply_prompt_overrides.py`, `test_outputs.py`, `test_rics.py`, `append_universe.py`, `create_client_csv.py` | The dominant domain |
| **EQ forward curves** (forwards from vol-surface response) | `equity_forward_extraction.py`, `batch_forward_extraction.py`, `forward_curve_implementation.py`, `forward_curve_test*.py` (×4), `forward_discovery_test.py`, `fwd_predictive_test.py`, `test_forward_default.py` | Heavy duplication |
| **SocGen COFBox** | `pull_cof_data_spx.py`, `pull_cof_data_sx5e.py`, `plot_cofbox_spreads.py`, `merge_and_plot.py`, `chart_term_structure*.py`, `chart_time_series.py`, `insight_chart.py`, `rebuild_demo_charts.py` | Uses private `lseg_analytics.socgen.cof_box._functions` |
| **Rates / IR curves** | `sanity_check.py`, `weekly_loop.py` | Hardcoded UUIDs |
| **Starmine credit screening** | `ninety_one_credit_screen.py` | Only file using `lseg.data` SDK |
| **FX** | None observed (you flagged it as expected, but nothing in this snapshot is FX-specific) | — |
| **Bond calculators** | None observed | — |
| **Notebooks / interactive** | None — but `forward_curve_test*.py` files are notebook-style scripts pretending to be modules | — |
| **Infrastructure** | None | No session, auth, config, or logging modules |

Note on **two SDKs in use**:
- `lseg_analytics.*` — used by 41/43 files (`eq_volatility`, `interest_rate_curves`, `socgen.cof_box._functions`, `pricing._basic_client.models._models`).
- `lseg.data` — used only by `ninety_one_credit_screen.py:40`.

These are different LSEG products with different auth models and different idioms. There is no recorded decision about which to standardise on.

## 1.5 Fragility and tech debt (concrete instances)

1. **Private API import** — `from lseg_analytics.socgen.cof_box._functions import post_analysis` (`pull_cof_data_spx.py:2`, `pull_cof_data_sx5e.py:2`). The leading `_` means SDK upgrades can break this without notice. Wrap it.
2. **Hardcoded resource UUIDs** — see §1.3d. If LSEG rotates them, two files silently break.
3. **Hardcoded calculation dates** — `dt.datetime(2025, 4, 18)`, `dt.datetime(2026, 5, 10)`, `dt.datetime(2026, 4, 25)` scattered across 16+ files. Reproduces a snapshot, but no single source of truth.
4. **Cross-script imports through cwd** — `check_surface_matrix.py:4` does `import eq_vol_surface_pull_universe as u`. Will break the moment files move into a package, and Copilot/Claude don't currently know it's a load-bearing import.
5. **`forward_curve_test.py` execution risk** — Tests 2 and 4 perform live `ev.calculate()` calls in 4 different ways with different inputs sequentially, including monkey-patches via `setattr(request_item, 'outputs', ...)`. Anyone running it pays for ~10 SDK calls and a noisy stdout dump.
6. **`eq_vol_surface_test.py` indentation bug** (lines 116–159) — likely doesn't run as written; mixes a function body with module-level execution.
7. **No retry/backoff anywhere** — `batch_forward_extraction.py` has a `time` import for wall-clock measurement only; no transient-error handling on the SDK calls.
8. **No logging** — every script uses `print()`. There is no log level, no run id, no structured output.
9. **CSV dialect inconsistency** — some scripts use `csv.writer` (`pull_cof_data_spx.py`), some `pd.DataFrame.to_csv` (`equity_forward_extraction.py`), some `csv.DictWriter` (`eq_vol_surface_test.py:225`). No house style.
10. **`requirements.txt` lies** — declares only `lseg-data`, `pandas`, `numpy`, `matplotlib`, but nothing imports `lseg-data` except one file, and `lseg_analytics` (the actually-used SDK) is not listed.
11. **`__pycache__` and `.DS_Store` in workspace root** — neither belongs there.

---

# PHASE 2 — Target architecture

## 2.1 Recommended layout

```
PythonLSEGV2/                      # repo root
├── pyproject.toml                  # single source of truth for deps + package metadata
├── README.md
├── .gitignore                      # .venv, __pycache__, *.csv, *.png, *.log, .DS_Store
├── .python-version                 # pin Python (e.g. 3.11)
├── .env.example                    # LSEG_APP_KEY, LSEG_PROFILE, etc. — never commit .env
│
├── docs/                           # AI-optimised knowledge layer (Phase 3)
│   ├── ARCHITECTURE.md
│   ├── API_OVERVIEW.md
│   ├── PATTERNS.md
│   ├── DATASETS.md
│   ├── WORKFLOWS.md
│   ├── COMMON_ERRORS.md
│   └── EXAMPLES_INDEX.md
│
├── src/lseg_quant/                 # the actual package, importable as `lseg_quant.xxx`
│   ├── __init__.py
│   ├── config.py                   # paths, env loading, default calculation_date resolver
│   ├── session.py                  # one auth/session manager for both SDKs
│   ├── logging.py                  # structured logging w/ run_id
│   │
│   ├── sdk/                        # thin wrappers around LSEG SDK boilerplate
│   │   ├── __init__.py
│   │   ├── eq_volatility.py        # build_surface_parameters(), build_request_item(), parse_surface_response()
│   │   ├── interest_rate_curves.py # load_template(), zero_rate_at_tenor()
│   │   ├── cofbox.py               # wraps socgen.cof_box._functions.post_analysis (insulates from `_functions` rename)
│   │   └── data_library.py         # `lseg.data` wrapper (Starmine, fundamentals)
│   │
│   ├── universe/
│   │   ├── __init__.py
│   │   ├── ric_resolver.py         # KNOWN_INDEX_RICS, SUFFIX_TO_RIC, candidate_rics(), load_overrides()
│   │   └── universe_loader.py      # parse_universe(text), load_universe_csv()
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── forwards.py             # extract_forward_data(), decompose_forwards(), interpolate_rate()
│   │   ├── volatility.py           # surface coverage extraction, summary stats
│   │   ├── rates.py                # zero-rate lookups, swap-rate weekly loop logic
│   │   ├── cofbox.py               # COFBox post-analysis -> long DataFrame
│   │   └── credit.py               # Starmine CCR scoring, screening criteria
│   │
│   └── io/
│       ├── __init__.py
│       ├── dataframes.py           # canonical "long" and "wide" schemas, dtype enforcement
│       └── exports.py              # write_csv(), write_parquet(), with run_id-stamped paths
│
├── workflows/                      # entry-point scripts: thin orchestration only
│   ├── coverage_scan.py            # replaces run_ivm_real_coverage.py
│   ├── forward_extraction.py       # replaces equity_forward_extraction.py + batch_forward_extraction.py
│   ├── cofbox_pull.py              # replaces pull_cof_data_spx.py + pull_cof_data_sx5e.py
│   ├── swap_rates_weekly.py        # replaces weekly_loop.py
│   └── credit_screen.py            # replaces ninety_one_credit_screen.py
│
├── notebooks/                      # exploratory; never imported from
│   └── sdk_response_shapes.ipynb   # one notebook replaces forward_curve_test_v{1..4}.py
│
├── data/
│   ├── reference/                  # checked-in: ric_overrides.csv, bbg_to_ric.csv (latest only)
│   └── outputs/                    # gitignored: run-stamped CSVs/PNGs
│       └── YYYY-MM-DD_run_id/
│
├── examples/                       # canonical, minimal, runnable (Phase 4)
│   ├── 01_get_vol_surface.py       # the smallest working surface request
│   ├── 02_forward_curve.py
│   ├── 03_ois_zero_rate.py
│   ├── 04_cofbox_post_analysis.py
│   └── 05_starmine_screen.py
│
└── tests/
    ├── conftest.py                 # session fixtures w/ env-gated live mode
    ├── unit/                       # pure functions: interpolate_rate, parse_universe, RIC resolver
    └── integration/                # marked @live; opt-in via LSEG_LIVE=1
```

Two principles drive this:

- **`src/lseg_quant/` is library, `workflows/` is application.** Library code is the only thing reusable; workflow scripts are orchestration. AI assistants should be told this once, not re-discover it per-prompt.
- **One way to do each thing.** Every duplicated block in §1.3 collapses into a function in `src/lseg_quant/sdk/` or `src/lseg_quant/analytics/`.

## 2.2 Naming conventions

- Modules: `snake_case`, singular (`forwards.py`, not `forward.py` for the module containing `extract_forward_data`).
- Functions: verbs (`build_surface_parameters`, `extract_forward_data`, `decompose_forwards`, `resolve_ric`).
- Constants: `UPPER_SNAKE`, defined once per module.
- Output filenames: `{run_id}_{domain}_{kind}.csv` (e.g. `20260510T0900_forwards_long.csv`). No `_v2`, no `_final`, no `_may6_2026` — that's git's job.
- Tests: `test_<module>.py`, function `test_<behaviour>`.

## 2.3 Configuration strategy

- `.env` for secrets, loaded with `python-dotenv` (or `pydantic-settings`).
- `src/lseg_quant/config.py`: single `Settings` object (pydantic) carrying:
  - `LSEG_APP_KEY`, `LSEG_PROFILE`
  - `DEFAULT_CALCULATION_DATE` (resolves to "latest business day" if unset)
  - `EUR_OIS_TEMPLATE_ID = "c7a3eff1-..."`, `USD_OIS_TEMPLATE_ID = "ce157336-..."` (today hardcoded twice)
  - `OUTPUT_ROOT = data/outputs/`
- No `dt.datetime(2026, 5, 10)` literals anywhere in business code. Workflows accept `--as-of` CLI args via `argparse` or `typer`.

## 2.4 Environment strategy

- **`uv`** (recommended) or **Poetry**. Pick one and commit `uv.lock` / `poetry.lock`. Do not stay on raw `pip + requirements.txt` — your current `requirements.txt` is already inaccurate (declares `lseg-data` only; you actually use `lseg-analytics`).
- Reasons to prefer `uv`: it's significantly faster, supports script-style dep declarations (useful for `examples/`), and has clean separation between project deps, dev deps, and optional groups.
- Single `.venv` at root, gitignored. Pin Python via `.python-version`.
- Dev/test deps in a `[project.optional-dependencies] dev = [...]` group: `pytest`, `pytest-mock`, `ruff`, `mypy`, `python-dotenv`.

## 2.5 Example workflow structure

A workflow file should be ~40 lines, not 400:

```python
# workflows/forward_extraction.py
from lseg_quant.config import settings
from lseg_quant.session import lseg_session
from lseg_quant.universe.ric_resolver import load_universe
from lseg_quant.analytics.forwards import extract_forwards_batch, decompose_forwards
from lseg_quant.io.exports import write_run_outputs

def main(as_of=None, universe_csv="data/reference/client_universe.csv"):
    as_of = as_of or settings.default_calculation_date
    universe = load_universe(universe_csv)
    with lseg_session():
        rows, summaries, failures = extract_forwards_batch(universe, as_of=as_of)
    write_run_outputs("forwards", rows=rows, summaries=summaries, failures=failures)

if __name__ == "__main__":
    import typer; typer.run(main)
```

## 2.6 Testing structure

- **Unit tests** for pure logic: `interpolate_rate`, `candidate_rics`, `parse_universe`, `decompose_forwards` (with synthetic fwd/spot/curve fixtures). These should not need the SDK.
- **Integration tests** marked `@pytest.mark.live`, gated on `LSEG_LIVE=1`, that hit one canonical RIC (e.g. `AAPL.O@RIC`) and assert response shape.
- A `tests/fixtures/` folder with pickled real responses for `eq_volatility.calculate` so unit tests can validate the full parser without a live session.

---

# PHASE 3 — AI-optimised knowledge layer

The point of these files is to **stop AI assistants from re-deriving the same context every chat**. They should be small, opinionated, and updated when behaviour changes.

### `docs/ARCHITECTURE.md` (~1 page)
**Purpose:** the single file an AI should be told to read first.
**Sections:**
- Mission: what this repo computes (vol surfaces, forwards, COFBox, IRC zero rates, Starmine screening).
- Library vs application split (`src/lseg_quant/` vs `workflows/`).
- Which SDK is canonical (`lseg_analytics` for pricing/analytics; `lseg.data` only for Starmine fundamentals).
- The 4–5 modules an AI should know exist before suggesting code.
- Cross-cutting concerns: session, config, logging, output paths.
**AI usage:** include this in every system/context prompt for IDE assistants ("read docs/ARCHITECTURE.md before suggesting code in this repo").

### `docs/API_OVERVIEW.md` (~2 pages)
**Purpose:** what each LSEG SDK call returns, in our actual experience.
**Sections:**
- `eq_volatility.calculate(universe=[...])` → top-level keys: `data[i].surface`, `surface[0]` row of expiries, `headers`, `expiry_dates`, `underlying_spot`, `forwardCurve.dataPoints`, `interestRateCurve.multiCurve.OIS`. Note camelCase vs snake_case quirks.
- `interest_rate_curves.load(resource_id=...).calculate(pricing_preferences=...)` → `as_dict()` shape, `analytics.zcCurves[0].points[].tenor / rate.value` (rate.value is in **percent**; divide by 100).
- `socgen.cof_box._functions.post_analysis(...)` → `instruments[0].cof[].series[].cofDiv100pct/cofDivMarket`, `instruments[0].fwdCof[].series[].fwdCofs[]`. (Note: this is a private module — wrap it in `sdk/cofbox.py`.)
- `lseg.data.get_data(universe, fields=[...])` → flat DataFrame with field names as columns.
**AI usage:** stops Copilot/Claude from suggesting `forward_curve` when the actual key is `forwardCurve`, or `rate.value / 1` when it's percent.

### `docs/PATTERNS.md`
**Purpose:** house style for recurring micro-patterns.
**Sections:**
- "Always go through `sdk/eq_volatility.build_surface_parameters(as_of, **overrides)`."
- Long-format DataFrame schema for forward decomposition (column names, dtypes, units).
- Error handling: catch `LSEGError`, attach RIC + as-of, add to failures list, continue batch.
- Output writing: always go through `io.exports.write_run_outputs(domain, **frames)` so files land under `data/outputs/{run_id}/`.
- Logging: `logging.getLogger("lseg_quant.<module>")`, never `print()` in library code.

### `docs/DATASETS.md`
**Purpose:** explain every CSV/JSON the repo produces or consumes, with schemas.
**Sections:**
- Inputs: `client_volatility_coverage_*.csv`, `universe_full.txt` format (4-line groups), `ric_overrides.csv` format, `bbg_to_ric*.csv`.
- Outputs: `forwards_long.csv` (long form), `forwards_summary.csv`, `coverage_results.csv`, `cof_*.csv`.
- Why three files exist named `bbg_to_ric*.csv` and which is current.

### `docs/WORKFLOWS.md`
**Purpose:** for each workflow, one paragraph + CLI invocation.
**Sections:**
- Coverage scan, forward extraction, COFBox pull, swap rates weekly, credit screen.
- For each: inputs, outputs, typical runtime, what a successful run prints.
**AI usage:** when a user says "run the forward extraction", an assistant can suggest the right command without grepping.

### `docs/COMMON_ERRORS.md`
**Purpose:** the SDK errors you've actually hit and the fix.
**Sections:**
- `"not logged in"` → re-check session bootstrap (link to `session.py`).
- `LSEGError` with empty surface → instrument code wrong; consult `ric_resolver.candidate_rics()`.
- `outputs` field not respected → must be set via `request_item['outputs'] = [...]` (dict-style), not as a kwarg. (This is exactly what `forward_curve_test_v{2,3,final}.py` was discovering.)
- Dividend-named outputs not honoured (per `forward_curve_test.py` Test 4) — only `Data, UnderlyingSpot, InterestRateCurve, ForwardCurve, SurfaceInformation` are valid output tags.

### `docs/EXAMPLES_INDEX.md`
**Purpose:** map domain → minimal example file.
**Sections:**
- "How do I get a vol surface for one RIC?" → `examples/01_get_vol_surface.py`.
- "How do I extract a forward curve and decompose into implied q?" → `examples/02_forward_curve.py`.
- etc.
**AI usage:** assistants that read `EXAMPLES_INDEX.md` first stop reinventing the boilerplate.

---

# PHASE 4 — SDK knowledge extraction

Recurring patterns that should become canonical examples / templates:

### Pattern 1 — Vol-surface request

A vol-surface request always has the same skeleton: `EtiSurfaceDefinition(instrument_code=ric)` + the 8-keyword `EtiSurfaceParameters(...)` + `EtiVolatilitySurfaceRequestItem(...)` + `SurfaceOutput(format=MATRIX)`. Reduce to:

```python
# sdk/eq_volatility.py
def build_surface_parameters(as_of: dt.datetime, **overrides) -> ev.EtiSurfaceParameters:
    defaults = dict(
        calculation_date=as_of,
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    return ev.EtiSurfaceParameters(**{**defaults, **overrides})

def build_request_item(ric, params, *, outputs=None, tag=None):
    item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=tag or ric,
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_parameters=params,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    if outputs:
        item['outputs'] = outputs   # dict-style assignment; this is the discovery from forward_curve_test_final.py
    return item
```

That single helper kills 16+ duplicates.

### Pattern 2 — Surface response → DataFrame

Both `eq_vol_surface_pull_universe.py:183-205` and the broken block in `eq_vol_surface_test.py:109-128` implement the same matrix → DataFrame conversion (with branch for `headers/expiry_dates is None` vs not). Promote to one `parse_surface_response(resp) -> tuple[pd.DataFrame, float]`.

### Pattern 3 — Forward decomposition

`equity_forward_extraction.py:127-174` and `batch_forward_extraction.py:111-216` repeat the same `T_years = (fwd_date - val_date).days / 365.0`, `q = r - ln(F/S)/T`, `carry = r - q`, `forward_premium_pct = (F/S - 1)*100`, `low_confidence = T < 0.05` logic. Promote to `analytics/forwards.py::decompose_forwards(spot, valuation_date, forwards, discount_curve) -> pd.DataFrame`.

### Pattern 4 — Discount-curve interpolation

§1.3b. `interpolate_rate(curve, T)` belongs in `analytics/rates.py`.

### Pattern 5 — RIC candidate generation

`eq_vol_surface_pull_universe.py:157-171` (`candidate_rics`) and the universe loader in `run_ivm_real_coverage.py:56-82` overlap. Consolidate into `universe/ric_resolver.py` with one source of truth for `KNOWN_INDEX_RICS` and `SUFFIX_TO_RIC`.

### Pattern 6 — `lseg_analytics.socgen.cof_box._functions.post_analysis`

The two `pull_cof_data_*.py` scripts already define a clean call signature. Wrap in `sdk/cofbox.py::post_analysis(instrument_code, maturities, start_date, end_date, cof_types=...)` so the underscore-private import is in **one** place.

### Pattern 7 — IRC template usage

Hardcoded UUIDs in `sanity_check.py` and `weekly_loop.py`. Promote to `sdk/interest_rate_curves.py`:

```python
EUR_OIS_TEMPLATE_ID = settings.eur_ois_template_id
USD_OIS_TEMPLATE_ID = settings.usd_ois_template_id

def zero_rate_at_tenor(template_id: str, valuation_date: str, tenor: str = "1Y") -> float:
    ...
```

### Canonical/minimal examples to preserve

- `examples/01_get_vol_surface.py` — derived from `eq_vol_surface_test.py`'s `get_surface_info`, but using the new `sdk.eq_volatility` helpers. ~25 LOC.
- `examples/02_forward_curve.py` — derived from `forward_curve_test_final.py` (the one that worked). ~30 LOC.
- `examples/03_ois_zero_rate.py` — derived from `sanity_check.py`. ~15 LOC.
- `examples/04_cofbox_post_analysis.py` — derived from `pull_cof_data_spx.py`, parameterised. ~25 LOC.
- `examples/05_starmine_screen.py` — derived from `ninety_one_credit_screen.py:99-110` (just the live data fetch). ~20 LOC.

Delete `forward_curve_test.py`, `_v2.py`, `_v3.py`, `forward_discovery_test.py`, `fwd_predictive_test.py` after harvesting the working bits — they are now dead context.

---

# PHASE 5 — Reusable component extraction

| Module | Responsibility | Source files (extract from) | Benefit |
|---|---|---|---|
| `session.py` | Single entry point for opening/closing LSEG sessions across both SDKs; context manager | `ninety_one_credit_screen.py:101-108` (only explicit session); implicit elsewhere | Removes the silent two-SDK split |
| `config.py` | `Settings` (pydantic): app key, default as-of date, IRC template UUIDs, output root | hardcoded UUIDs in `sanity_check.py:5-6`, `weekly_loop.py:7-8`; 16+ hardcoded `calculation_date` literals | Kills hardcoded constants; single source of truth |
| `sdk/eq_volatility.py` | `build_surface_parameters`, `build_request_item`, `parse_surface_response`, `extract_forward_curve` | `forward_curve_test_final.py`, `eq_vol_surface_pull_universe.py:128-205`, `equity_forward_extraction.py:64-122`, `batch_forward_extraction.py:45-109` | Removes the 16-copy `EtiSurfaceParameters` block |
| `sdk/interest_rate_curves.py` | `load_template`, `zero_rate_at_tenor` | `sanity_check.py`, `weekly_loop.py` | Centralises UUIDs + percent-vs-decimal handling |
| `sdk/cofbox.py` | `post_analysis_long_df(instrument_code, maturities, ...) -> pd.DataFrame` | `pull_cof_data_spx.py`, `pull_cof_data_sx5e.py` | Insulates from `_functions` rename; turns parameter duplication into one call |
| `sdk/data_library.py` | `lseg.data` thin wrapper for Starmine fields | `ninety_one_credit_screen.py:99-110` | Same auth treatment as the rest |
| `analytics/forwards.py` | `extract_forward_data`, `interpolate_rate`, `decompose_forwards`, `extract_forwards_batch` | `equity_forward_extraction.py:8-174`, `batch_forward_extraction.py:10-216` | Removes byte-identical duplication of `interpolate_rate` and the q/carry math |
| `analytics/rates.py` | swap-rate weekly loop logic, `zero_rate_at_tenor` | `weekly_loop.py:14-82` | Loop becomes a thin workflow on top |
| `universe/ric_resolver.py` | `KNOWN_INDEX_RICS`, `SUFFIX_TO_RIC`, `candidate_rics`, `load_overrides`, `load_universe_text` | `run_ivm_real_coverage.py:25-101`, `historical_basket_stage1.py:34-94`, `eq_vol_surface_pull_universe.py:94-171` | One mapping, one place |
| `io/dataframes.py` | Canonical schemas for `forwards_long`, `coverage_results`, `cof_long`; dtype enforcement | scattered `pd.DataFrame(...)` / `csv.writer` calls | Stops downstream consumers guessing column names |
| `io/exports.py` | `write_run_outputs(domain, **frames)` writes to `data/outputs/{run_id}/` | scattered `to_csv("...", index=False)` and ad-hoc `csv.writer` | Eliminates output co-location with source |
| `logging.py` | `get_logger`, run-id stamp | every script's `print()` | Replaces ~250 `print()` calls |

---

# PHASE 6 — Environment & dependency strategy

Concrete recommendations:

### 6.1 Move to `uv` + `pyproject.toml`

Reasons: your current `requirements.txt` is **wrong** (declares `lseg-data` while the codebase actually uses `lseg-analytics`). `uv` will lock the real, transitive set including the SDKs you actually import.

```toml
# pyproject.toml — sketch
[project]
name = "lseg-quant"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "lseg-analytics>=2.0",   # NOTE: actually-used SDK, not declared today
    "lseg-data>=2.0",        # used by Starmine flow
    "pandas>=2.0",
    "numpy>=1.24",
    "matplotlib>=3.7",
    "python-dateutil>=2.8",
    "pydantic>=2",
    "pydantic-settings>=2",
    "typer>=0.9",
]

[project.optional-dependencies]
dev = ["pytest>=7", "pytest-mock", "ruff", "mypy", "ipykernel"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/lseg_quant"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: requires LSEG live session (LSEG_LIVE=1)"]
```

### 6.2 Lockfile

`uv lock` (or `poetry lock`) committed. The current "venv exists in workspace, requirements.txt half-fiction" approach is unreproducible.

### 6.3 `.gitignore`

```
.venv/
__pycache__/
*.pyc
.DS_Store
.env
data/outputs/
*.png
*.log
*.tmp
grep_*.txt
run_output.txt
```

### 6.4 Don't keep the bloated unmanaged `.venv` in workspace

Currently it's there alongside source. After the migration, regenerate with `uv venv && uv sync`. The actual content is reproducible from `pyproject.toml + uv.lock`.

---

# PHASE 7 — Final synthesis

## 7.1 Major architectural weaknesses (ranked)

1. No package boundary. There is no `lseg_quant` namespace; everything is top-level scripts importing each other through `cwd`. (Highest leverage to fix; everything else is downstream.)
2. SDK boilerplate copy-pasted instead of abstracted (16+ `EtiSurfaceParameters`, 2× `interpolate_rate`, 2× IRC UUID load, 2× COFBox call).
3. Two parallel SDKs (`lseg_analytics`, `lseg.data`) with no central session strategy.
4. Versioning by filename suffix (`_v2`, `_final`, `_may6_2026`) instead of git.
5. Output detritus (CSV/PNG/log/JSON, ~30 MB) lives in source root, polluting AI context.
6. No tests, no logging, no config, no error handling beyond catch-and-print.
7. Hardcoded business inputs (calculation dates, IRC template UUIDs) scattered across files.
8. Private SDK imports (`_functions`) used directly without insulation.
9. `requirements.txt` does not match real imports.
10. AI assistants currently re-derive every pattern per chat because no `docs/` knowledge layer exists.

## 7.2 Highest-leverage improvements

1. Create `pyproject.toml` + `src/lseg_quant/` package skeleton + `.gitignore` + move output files to `data/outputs/`. Single PR. Unblocks everything else.
2. Extract `sdk/eq_volatility.py` (helpers for surface parameters / request item / response parsing). Migrate `equity_forward_extraction.py` and `batch_forward_extraction.py` to use it. Two duplicates collapse, and a future LSEG SDK rename has one breakage point instead of 16.
3. Write `docs/ARCHITECTURE.md`, `docs/API_OVERVIEW.md`, `docs/COMMON_ERRORS.md`. Tell Copilot/Claude to read these. Token-cost recovery is immediate.
4. Delete the `forward_curve_test_v{1..3}.py` family after harvesting the one true thing they discovered (the `request_item['outputs'] = [...]` dict-style assignment). Capture that as a one-paragraph entry in `COMMON_ERRORS.md`.

## 7.3 Migration roadmap

**Sprint 0 — scaffolding (½ day)**
- Add `pyproject.toml`, `.gitignore`, `.env.example`, `src/lseg_quant/__init__.py`.
- Move `__pycache__`, `.DS_Store`, all `*.png`, all generated `*.csv`, all `*.log`, the `grep_*.txt` files into `data/outputs/_legacy/` (or just delete after confirming none are referenced as inputs by another script — `client_volatility_coverage_may6_2026.csv` is referenced by `batch_forward_extraction.py:220` so check this carefully before bulk-moving).
- Initialise git if not already, with a commit before any restructuring so the old layout is recoverable.

**Sprint 1 — extract `sdk/` and `analytics/forwards.py` (1 day)**
- Move boilerplate: `sdk/eq_volatility.py`, `analytics/forwards.py`, `analytics/rates.py`, `universe/ric_resolver.py`.
- Rewrite `equity_forward_extraction.py` and `batch_forward_extraction.py` as thin workflows (`workflows/forward_extraction.py`).
- Rewrite `pull_cof_data_*.py` as one parameterised `workflows/cofbox_pull.py` with `--instrument` arg.
- Rewrite `sanity_check.py` + `weekly_loop.py` on top of `sdk/interest_rate_curves.py`.

**Sprint 2 — knowledge layer (½ day)**
- Author `docs/ARCHITECTURE.md`, `API_OVERVIEW.md`, `PATTERNS.md`, `COMMON_ERRORS.md`, `EXAMPLES_INDEX.md`.
- Add `examples/01..05_*.py`.

**Sprint 3 — coverage workflows + dead code purge (1 day)**
- Migrate `run_ivm_real_coverage.py` and `historical_basket_stage1.py` onto the shared `universe/ric_resolver.py`.
- Delete: `forward_curve_test.py`, `_v2.py`, `_v3.py`, `forward_discovery_test.py`, `fwd_predictive_test.py`, `eq_vol_surface_test.py` (broken indentation), `chart_term_structure.py` (kept `_v2.py`), the four `find_*.py` and the three `analyze_*.py` scratch scripts (capture intent in a notebook).
- Resolve the `bbg_to_ric.csv` / `_v2.csv` / `_may6_2026.csv` triplet — keep one, rename to `bbg_to_ric.csv`.

**Sprint 4 — tests + CI hooks (1 day)**
- Pure-function tests for `interpolate_rate`, `decompose_forwards`, `candidate_rics`, `parse_universe`.
- One `@live` integration test that pulls AAPL.O@RIC and asserts response shape.
- Pre-commit: `ruff format`, `ruff check`, `mypy --strict src/lseg_quant`.

## 7.4 Quick wins vs long-term

| Type | Item |
|---|---|
| **Quick win (≤1 hr)** | `.gitignore`; move outputs out of root; delete `__pycache__` and `.DS_Store`; collapse `pull_cof_data_spx.py`/`_sx5e.py` into one parameterised script |
| **Quick win (≤½ day)** | `sdk/eq_volatility.py` helpers + migrate one workflow; `docs/ARCHITECTURE.md`; correct `requirements.txt` (or replace with `pyproject.toml`) |
| **Medium (1–2 days)** | Full `src/` package skeleton; migration of all forward/COFBox/rates workflows |
| **Long-term** | Tests with response fixtures; CI; structured logging; output-format standardisation; possible refactor away from `lseg_analytics.socgen.cof_box._functions` if a public API exists |

## 7.5 AI-optimisation recommendations (specific to your stack)

Concrete things that lower the per-chat token cost in Copilot, Claude, and GPT once the structure above is in place:

1. **Tell each assistant to read `docs/ARCHITECTURE.md` and `docs/API_OVERVIEW.md` first.** In Copilot, this is the `.github/copilot-instructions.md` file (stable, repo-wide). In Claude Code, this is `CLAUDE.md` at the repo root. Anchoring both to `docs/*.md` keeps them in sync.
2. **Make the package layout flat-but-discoverable.** A flat `src/lseg_quant/` with descriptive module names (`forwards.py`, `volatility.py`, `cofbox.py`) lets symbol-grep tools surface the right file in one hop. Avoid nested layers like `analytics/equity/forwards/extraction.py`.
3. **Stop tooling re-reading dead code.** Move the `_v2`/`_v3` files into `notebooks/` or delete them. Copilot in VS Code indexes the workspace; every `forward_curve_test*.py` you keep is N more tokens it has to traverse.
4. **Move bulky text artefacts out of source.** `grep_isin.txt` (794 KB), `grep_output.txt`, `coverage_run_log.txt`, `run_output.txt`, `cof_analysis_results.json` (3.4 MB) — none of these belong next to source. They will be indexed and re-indexed by IDE assistants.
5. **Use docstrings as truth, not comments-in-scripts.** When `equity_forward_extraction.py:328-332` documents the implied-q caveats inline as a triple-quoted run-log, that knowledge is invisible to a fresh chat. Move those caveats into `analytics/forwards.py.decompose_forwards.__doc__` so any AI looking at the symbol gets them.
6. **Standardise output column names** (`io/dataframes.py`). Once an assistant has seen the canonical `forwards_long.csv` schema once, it stops re-asking and re-renaming columns across runs.
7. **One canonical example per domain in `examples/`.** Put them under 40 LOC. Most "explain how to call X" prompts can be answered by a one-file include.
8. **Avoid Python-version drift.** Pin via `.python-version` and reference it in `docs/ARCHITECTURE.md`. Copilot won't suggest 3.12-only syntax in a 3.11 project if it's told.
9. **Type hints everywhere in `src/`.** They are the single highest-leverage AI hint per character: `def decompose_forwards(spot: float, valuation_date: dt.datetime, forwards: list[tuple[dt.datetime, float]], discount_curve: list[OISPoint]) -> pd.DataFrame` tells Claude/GPT the entire data flow without reading the body.

## 7.6 What to preserve verbatim

Don't rewrite these — extract them as-is:

- `eq_vol_surface_pull_universe.py:157-205` — `candidate_rics` + `parse_surface_response`. Solid logic, just needs to live in a module.
- `batch_forward_extraction.py:45-109` — the batch-aware version of `extract_forward_data`. Use this, not the single-RIC one in `equity_forward_extraction.py`.
- `equity_forward_extraction.py:127-174` — the implied-q decomposition with the `low_confidence` flag and the explicit caveats it carries.
- `run_ivm_real_coverage.py:25-101` — the most complete `KNOWN_INDEX_RICS`/`SUFFIX_TO_RIC`/`load_overrides` set. Make this the canonical resolver.
- `ninety_one_credit_screen.py:62-87` — the Starmine FIELDS list and CRITERIA dict. This is real domain knowledge encoded as data.

## 7.7 What to throw away (after a final read-through)

- `forward_curve_test.py` (374 LOC, 3 duplicates of the same boilerplate inside, replaced by `_final.py`).
- `forward_curve_test_v2.py`, `forward_curve_test_v3.py` (intermediate exploration; superseded).
- `forward_discovery_test.py` (285 LOC of `dir()`-spelunking; the discoveries belong in `docs/API_OVERVIEW.md`, not as code).
- `eq_vol_surface_test.py` (broken indentation; mock scaffolding never engaged).
- `chart_term_structure.py` (kept `_v2`).
- `bbg_to_ric.csv` and `bbg_to_ric_v2.csv` (kept `_may6_2026.csv` as latest).
- `coverage_results.csv`, `coverage_results_v2.csv` (kept `_may6_2026.csv`).
- `__pycache__/`, `.DS_Store`.
- `grep_isin.txt`, `grep_output.txt`, `run_output.txt`, `coverage_run_log.txt`, `cof_analysis_results.json` — large, not source, not reproducible inputs.

---

## Appendix A — File-by-file recommended action

| File | Action |
|---|---|
| `analyze_coverage.py` | merge into `workflows/coverage_scan.py` (`--analyse`) |
| `analyze_may6_failures.py` | one-shot; archive or delete |
| `append_universe.py` | helper in `universe/universe_loader.py` |
| `apply_prompt_overrides.py` | one-shot; archive |
| `batch_forward_extraction.py` | extract into `analytics/forwards.py` + `workflows/forward_extraction.py` |
| `chart_term_structure.py` | delete (superseded by `_v2`) |
| `chart_term_structure_v2.py` | move to `workflows/charts.py` or `notebooks/` |
| `chart_time_series.py` | move to `workflows/charts.py` |
| `check_basket_tickers.py` | one-shot; archive |
| `check_surface_matrix.py` | move into `examples/` after refactor |
| `compare_coverage.py` | small; merge into `workflows/coverage_scan.py` |
| `create_client_csv.py` | move to `workflows/exports/client_csv.py` |
| `eq_vol_surface_full_coverage.py` | merge into `workflows/coverage_scan.py` |
| `eq_vol_surface_pull_universe.py` | break into `universe/ric_resolver.py` + `sdk/eq_volatility.py` + `workflows/coverage_scan.py` |
| `eq_vol_surface_test.py` | delete (broken indentation) |
| `equity_forward_extraction.py` | extract into `analytics/forwards.py` + `workflows/forward_extraction.py` |
| `find_test_tickers.py`, `find_valid_pairs.py` | one-shot; archive |
| `forward_curve_implementation.py` | extract any unique logic into `analytics/forwards.py`, then delete |
| `forward_curve_test*.py` (4 files) | delete; capture findings in `docs/COMMON_ERRORS.md` and `examples/02_forward_curve.py` |
| `forward_discovery_test.py` | delete |
| `fwd_predictive_test.py` | move to `notebooks/` or delete |
| `generate_surface_coverage_csv.py` | small; fold into `workflows/coverage_scan.py` |
| `historical_basket_stage1.py` | rewrite as `workflows/historical_basket.py` on shared resolver |
| `insight_chart.py`, `merge_and_plot.py`, `plot_cofbox_spreads.py`, `rebuild_demo_charts.py` | merge into `workflows/cofbox_charts.py` |
| `ninety_one_credit_screen.py` | split into `sdk/data_library.py` + `analytics/credit.py` + `workflows/credit_screen.py` |
| `pull_cof_data_spx.py`, `pull_cof_data_sx5e.py` | merge into one `workflows/cofbox_pull.py` with `--instrument` |
| `run_ivm_real_coverage.py` | extract `universe/ric_resolver.py` + `workflows/coverage_scan.py` |
| `sanity_check.py` | example: `examples/03_ois_zero_rate.py` |
| `test_forward_default.py`, `test_japan_vol_surface.py`, `test_outputs.py`, `test_rics.py` | rewrite as proper pytest under `tests/` |
| `validate_ric_rewrites.py`, `validate_ric_rewrites_fast.py` | keep one; move to `workflows/validate_overrides.py` |
| `weekly_loop.py` | rewrite as `workflows/swap_rates_weekly.py` on `sdk/interest_rate_curves.py` |

End of audit.
