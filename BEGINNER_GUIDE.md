# Beginner guide — what just happened and what to do in VS Code

I added a proper Python package alongside your existing scripts. **Nothing existing has been deleted or moved.** Your old scripts still work the way they did. The new layout is additive.

This guide assumes zero baseline. Skip sections you're comfortable with.

---

## 1. What changed (the new files)

```
PythonLSEGV2/
├── .gitignore                          ← so .venv, __pycache__, *.png, big logs don't get committed
├── .env.example                        ← copy to `.env` to set LSEG_APP_KEY etc.
├── pyproject.toml                      ← declares the project + its dependencies
├── CLAUDE.md                           ← tells Claude how this repo is organised
├── BEGINNER_GUIDE.md                   ← this file
├── LSEG_PLATFORM_AUDIT.md              ← the full audit I wrote earlier
├── docs/
│   └── ARCHITECTURE.md                 ← one-page anchor for AI assistants
├── .github/
│   └── copilot-instructions.md         ← tells Copilot how this repo is organised
├── src/lseg_quant/                     ← the new library (importable as `lseg_quant.*`)
│   ├── __init__.py
│   ├── config.py
│   ├── sdk/
│   │   ├── __init__.py
│   │   └── eq_volatility.py            ← replaces the 16x duplicated boilerplate
│   ├── analytics/
│   │   ├── __init__.py
│   │   └── forwards.py                 ← interpolate_rate + decompose_forwards
│   ├── universe/
│   │   ├── __init__.py
│   │   ├── ric_resolver.py             ← handles RIC / ISIN / CUSIP / ticker
│   │   └── loader.py                   ← reads any CSV with identifier columns
│   └── io/
│       ├── __init__.py
│       └── exports.py                  ← run-stamped output writer
└── workflows/
    ├── __init__.py
    └── forward_extraction.py           ← replaces equity_forward_extraction.py + batch_forward_extraction.py
```

All your old `.py` files (`batch_forward_extraction.py`, `pull_cof_data_*.py`, etc.) are still there. Don't delete anything yet.

---

## 2. Set up your VS Code environment (one time)

You'll do this from VS Code's integrated terminal.

**Open the terminal:** in VS Code, press **`Ctrl + ` `** (the backtick key, top-left). A terminal pane will open at the bottom. The prompt should show the folder name (`PythonLSEGV2`).

**Step 2a — Make sure the `.venv` is active.**
At the terminal prompt, run:

```bash
source .venv/bin/activate
```

On Windows it would be `.venv\Scripts\activate` instead. You should see `(.venv)` appear at the start of your prompt. If you get an error that the venv doesn't exist, create one first:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Step 2b — Install the project plus its dependencies.**

```bash
pip install -e .
```

The `-e` means "editable" — it installs the package in a way that picks up changes immediately, so you don't have to reinstall after every edit. This single command:
- installs `pandas`, `numpy`, `matplotlib`, `lseg-analytics`, `lseg-data`, `pydantic`, etc.
- makes `import lseg_quant` work from anywhere inside this folder.

If you also want the dev tools (linter, tests):

```bash
pip install -e ".[dev]"
```

**Step 2c — Tell VS Code to use this venv.**

Press **`Ctrl + Shift + P`** to open the command palette, type `Python: Select Interpreter`, and choose the one that says `.venv` under `./PythonLSEGV2`. VS Code will then use this venv for IntelliSense, linting, and run buttons.

**Step 2d — Create your `.env` file.**

```bash
cp .env.example .env
```

Open `.env` in VS Code and fill in `LSEG_APP_KEY` if you use one. (If your LSEG auth is via `~/.lseg/credentials.ini`, you can leave `.env` empty for now.) `.env` is in `.gitignore` so it will never be committed.

---

## 3. Verify the new workflow runs (parity check)

The new file `workflows/forward_extraction.py` is meant to replace `batch_forward_extraction.py`. Before deleting the old one, prove they produce the same output.

**Step 3a — Run the new workflow against your existing universe CSV.**

In the VS Code terminal, with the venv active:

```bash
python workflows/forward_extraction.py --universe client_volatility_coverage_may6_2026.csv --as-of 2026-05-10
```

It will print progress lines and finish with something like:

```
Done. success=290 failed=104 wall=187.3s → /…/data/outputs/20260510T143022_forwards
```

Inside `data/outputs/20260510T143022_forwards/` you'll find:
- `long.csv` — one row per (instrument, expiry). Compare to the old `forwards_output/forwards_long.csv`.
- `summary.csv` — one row per instrument. Compare to the old `forwards_output/forwards_summary.csv`.
- `failures.json` — anything that couldn't be extracted.
- `run_log.txt` — wall-clock + counts + caveats.
- `metadata.json` — what produced this run.

**Step 3b — Diff against the old output.**

```bash
diff <(sort forwards_output/forwards_long.csv) <(sort data/outputs/*_forwards/long.csv) | head -40
```

If the diff is empty (or only differs in row order / float-precision-last-digit), you have parity. Once you're satisfied, you can delete `equity_forward_extraction.py` and `batch_forward_extraction.py` in a later turn. **Don't delete them yet.**

If the diff shows real differences, paste the first 20 lines back to me and I'll investigate.

---

## 4. Try the new universe loader with different identifier types

You mentioned wanting to upload tickers, ISINs, CUSIPs going forward. The loader handles all of them. Just make a CSV like:

```csv
name,ticker,isin,exchange
Apple Inc,AAPL,US0378331005,US
Shell plc,SHEL,GB00BP6MXD84,LN
S&P 500 Index,SPX,,US
,,US78462F1030,
```

You don't need all four columns. You can have just `ticker`, just `isin`, just `cusip`, or any combination. The loader figures out the best identifier per row and produces a priority-ordered list of RICs to try. Save it as `data/reference/my_universe.csv` and:

```bash
python workflows/forward_extraction.py --universe data/reference/my_universe.csv
```

The exchange suffix mapping currently covers US, LN/GB, GR/DE, FP/FR, NA/NL, SM/ES, IM/IT, SW/CH, HK, JP, AU, CN, CA, KR, IN, ID, PL, SE, NO, DK, FI, BE. If you need more, edit `src/lseg_quant/universe/ric_resolver.py` and add to `SUFFIX_TO_RIC`.

---

## 5. Commit and push to GitHub

When you're happy with the new files and the parity check passed, commit them:

```bash
# from the VS Code terminal at repo root
git add .gitignore pyproject.toml .env.example CLAUDE.md BEGINNER_GUIDE.md LSEG_PLATFORM_AUDIT.md
git add docs/ .github/
git add src/ workflows/
git commit -m "Sprint 0: package scaffolding + forward extraction extraction"
git push
```

Notice I'm being explicit about which paths to add (rather than `git add -A`). That's because your repo still has many untracked legacy files and the 3.4 MB `cof_analysis_results.json` — you don't want any of those committed accidentally.

---

## 6. Common errors and what to do

**`ModuleNotFoundError: No module named 'lseg_quant'`**
You forgot `pip install -e .` (Step 2b), or the venv isn't activated. Run `which python` — it should point inside `.venv/bin/`.

**`ImportError: lseg_analytics is not installed`**
Same fix as above. `pip install -e .` brings it in.

**`FileNotFoundError: client_volatility_coverage_may6_2026.csv`**
You're not running from the repo root. `cd` into the `PythonLSEGV2` folder first.

**The output run directory is empty.**
The workflow's first step (loading the universe) probably succeeded but the SDK calls failed (auth or network). Look at `data/outputs/<run>/failures.json`. If everything is in there, your LSEG session isn't authenticated — check `LSEG_APP_KEY` or `~/.lseg/credentials.ini`.

---

## 7. What's next

After the parity check passes:

- **Sprint 1 finish**: migrate `pull_cof_data_spx.py` + `pull_cof_data_sx5e.py` into one `workflows/cofbox_pull.py`, and `sanity_check.py` + `weekly_loop.py` into `workflows/swap_rates_weekly.py`. Same pattern as forward extraction.
- **Sprint 2**: AI knowledge layer — fill in `docs/API_OVERVIEW.md`, `docs/PATTERNS.md`, `docs/COMMON_ERRORS.md`, `docs/EXAMPLES_INDEX.md`.
- **Sprint 3**: delete the legacy scripts (after parity is proven for each).

Each sprint is a separate commit. Don't batch them.

---

## Glossary (a few terms used above)

- **venv** — a folder with its own Python and its own installed packages, isolated from the system Python. The standard way to keep one project's dependencies separate from another's.
- **editable install (`pip install -e .`)** — installs the package such that Python imports it directly from your source files, so changes appear without reinstalling.
- **`pyproject.toml`** — the modern way to declare a Python project: its name, version, dependencies, and how to build it.
- **`.gitignore`** — a file listing patterns git should never track. Anything matching is invisible to commits.
- **library vs workflow** — library code (in `src/lseg_quant/`) is reusable functions and classes; workflow code (in `workflows/`) is a thin CLI on top of the library. Workflows have `if __name__ == "__main__"` blocks. Library files don't.
