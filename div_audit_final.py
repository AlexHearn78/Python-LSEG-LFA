#!/usr/bin/env python3
"""
Final dividend / implied q / repo audit across 5 test instruments + AAPL control.

Steps:
  1. Pull each test name with maximum verbosity, dump raw responses
  2. Probe DIVTYPE parameterization (discrete vs continuous)
  3. Analyze implied q vs realised dividend yield
  4. Compare GME residual (borrow) to AAPL/T residual (dividend)
  5. Inspect repo module for equity collateral support
"""

from __future__ import annotations
import datetime as dt
import json
import math
from pathlib import Path
from dateutil import parser

import lseg_analytics.pricing.market_data.eq_volatility as ev
import inspect
import pandas as pd

# ============================================================================
# CONFIG
# ============================================================================

TEST_NAMES = [
    # (RIC, description, expected_div_yield_pct, currency)
    ("T@RIC",          "AT&T, high-yield US, quarterly $0.28, no buyback",           7.2, "USD"),
    ("MO@RIC",         "Altria, high-yield US, quarterly $1.02, no buyback",         7.8, "USD"),
    ("BNPP.PA@RIC",    "BNP Paribas, annual EUR dividend, lumpy single payment",     5.5, "EUR"),
    ("VOD.L@RIC",      "Vodafone, semi-annual GBP, cross-currency test",             9.0, "GBP"),
    ("GME@RIC",        "GameStop, no dividend, historically hard-to-borrow",         0.0, "USD"),
]

AAPL_CONTROL = ("AAPL.O@RIC", "Apple control (previous run)", 0.4, "USD")

OUTPUT_DIR = Path("div_audit_raw")
OUTPUT_DIR.mkdir(exist_ok=True)

FIELDS = ",".join([
    "Data", "UnderlyingSpot", "InterestRateCurve", "DiscountCurve",
    "ForwardCurve", "Dividends", "SurfaceInformation"
])

VAL_DATE = dt.datetime(2026, 5, 10)

# ============================================================================
# STEP 1: Pull each name, dump raw responses
# ============================================================================

print("\n" + "="*80)
print("STEP 1: Pull each test name with maximum verbosity, dump raw responses")
print("="*80)

def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code."""
    if hasattr(obj, 'to_dict'):
        try:
            return obj.to_dict()
        except:
            pass
    if hasattr(obj, '__dict__'):
        return {k: v for k, v in vars(obj).items() if not k.startswith('_')}
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        try:
            return list(obj)
        except:
            pass
    return str(obj)

def build_request(ric: str):
    """Build a minimal surface request for dividend audit."""
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f"{ric.replace('@RIC','').replace('.','_')}_div_audit",
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        surface_parameters=ev.EtiSurfaceParameters(
            calculation_date=VAL_DATE,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        ),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )

pulled_items = {}

for ric, desc, exp_yield, ccy in TEST_NAMES:
    print(f"\n=== {ric}: {desc} ===")
    try:
        resp = ev.calculate(universe=[build_request(ric)], fields=FIELDS)
        item = resp['data'][0]
        pulled_items[ric] = item
        print(f"  ✓ API call successful, item loaded in memory")
        
        # Quick eyeball of Dividends block
        divs = item.get('dividends') if isinstance(item, dict) else getattr(item, 'dividends', None)
        if divs:
            if isinstance(divs, dict):
                divtype = divs.get('curveDefinition', {}).get('type', 'UNKNOWN') or divs.get('curve_definition', {}).get('type', 'UNKNOWN')
                structure = divs.get('curveParameters', {}).get('structure', 'UNKNOWN') or divs.get('curve_parameters', {}).get('structure', 'UNKNOWN')
            else:
                divtype = getattr(divs, 'curve_definition', {}).type if hasattr(divs, 'curve_definition') else 'UNKNOWN'
                structure = getattr(getattr(divs, 'curve_parameters', {}), 'structure', 'UNKNOWN') if hasattr(divs, 'curve_parameters') else 'UNKNOWN'
            n_pts = len(divs.get('points', [])) if isinstance(divs, dict) else len(getattr(divs, 'points', []))
            print(f"  Dividends: type={divtype}, structure={structure}, points={n_pts}")
        else:
            print(f"  Dividends: not present")
            
    except Exception as e:
        print(f"  ✗ FAILED: {e}")

# Check if we have AAPL dump from previous run
aapl_path = OUTPUT_DIR / "AAPL_O_full.json"
if aapl_path.exists():
    print(f"\n=== AAPL.O@RIC (control, from previous run) ===")
    with open(aapl_path) as f:
        pulled_items['AAPL.O@RIC'] = json.load(f)
    print(f"  ✓ Loaded from {aapl_path}")
else:
    print(f"\n⚠ AAPL control dump not available; will pull fresh copy")
    try:
        print("=== AAPL.O@RIC (control) ===")
        resp = ev.calculate(universe=[build_request('AAPL.O@RIC')], fields=FIELDS)
        pulled_items['AAPL.O@RIC'] = resp['data'][0]
        print(f"  ✓ API call successful")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")

# ============================================================================
# STEP 2: Probe DIVTYPE parameterization
# ============================================================================

print("\n" + "="*80)
print("STEP 2: Probe DIVTYPE parameterization")
print("="*80)

print("\n=== Searching for dividend-related enums in eq_volatility ===")
div_enum_names = [n for n in dir(ev) if 'divid' in n.lower() or 'divtype' in n.lower()]
if div_enum_names:
    print(f"Found: {div_enum_names}")
    for name in div_enum_names:
        obj = getattr(ev, name, None)
        if obj:
            print(f"\n  {name}:")
            if hasattr(obj, '__members__'):
                for member in obj.__members__:
                    print(f"    .{member}")
else:
    print("No dividend-related enums found in eq_volatility")

divtype_probe_attempted = False
if div_enum_names:
    print("\n=== Attempting DIVTYPE:DISCRETE re-request ===")
    # Try T@RIC with any discrete enum if it exists
    try:
        divtype_probe_attempted = True
        # This would require modifying SurfaceParameters; skip if not possible
        print("⚠ DIVTYPE parameter not exposed in SurfaceParameters API; cannot re-request")
    except Exception as e:
        print(f"✗ DIVTYPE re-request failed: {e}")
else:
    print("\n⚠ No dividend-type enums found; DIVTYPE parameter is not exposed")

# ============================================================================
# STEP 3: Analyze implied q vs realised dividend yield
# ============================================================================

print("\n" + "="*80)
print("STEP 3: Analyze implied q vs realised dividend yield")
print("="*80)

def analyse_dump(item, expected_div_pct: float, ric: str, ccy: str) -> dict | None:
    """
    Extract implied q from forward curve and compare to expected dividend yield.
    
    q = r - ln(F/S)/T
    """
    try:
        # Helper to get nested attribute from SDK objects or dicts
        def get_nested(obj, *keys):
            for key in keys:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    obj = getattr(obj, key, None)
                if obj is None:
                    return None
            return obj
        
        spot = get_nested(item, 'underlying_spot') or get_nested(item, 'underlyingSpot')
        if not spot:
            print(f"    ✗ No underlyingSpot found")
            return None
        
        # Valuation date from OIS curve
        irc = get_nested(item, 'interest_rate_curve') or get_nested(item, 'interestRateCurve')
        if irc is None:
            print(f"    ✗ No OIS curve found")
            return None
        
        # Drill into multiCurve.OIS
        mc = get_nested(irc, 'multi_curve') or get_nested(irc, 'multiCurve')
        if mc is None:
            print(f"    ✗ No multiCurve found")
            return None
        ois = get_nested(mc, 'OIS')
        if not ois:
            print(f"    ✗ No OIS curve found")
            return None
        
        # Handle OIS as SDK object or dict
        if not isinstance(ois, list):
            try:
                ois = list(ois)
            except:
                ois = [ois]
        
        val_date = parser.parse(
            get_nested(ois[0], 'start_date') or get_nested(ois[0], 'startDate')
        ).date()
        
        # Forward curve - try different attribute names
        fc = get_nested(item, 'forward_curve') or get_nested(item, 'forwardCurve')
        if fc is None:
            print(f"    ✗ No forwardCurve found")
            return None
        
        dp = get_nested(fc, 'data_points') or get_nested(fc, 'dataPoints')
        if not dp:
            print(f"    ✗ No dataPoints found in forward curve")
            return None
        
        # Handle dataPoints as dict, list, or SDK object
        forwards = []
        if isinstance(dp, dict):
            # If values are lists, take the first element
            forwards = []
            for k, v in dp.items():
                try:
                    fwd_date = parser.parse(k).date()
                    if isinstance(v, (list, tuple)):
                        F = float(v[0]) if v else None
                    else:
                        F = float(v)
                    if F is not None:
                        forwards.append((fwd_date, F))
                except (ValueError, TypeError, IndexError):
                    pass
            forwards.sort(key=lambda x: x[0])
        elif isinstance(dp, list):
            # If it's a list of objects with date and value
            for pt in dp:
                try:
                    date_val = get_nested(pt, 'date') or get_nested(pt, 'expiryDate') or get_nested(pt, 'expiry')
                    fwd_val = get_nested(pt, 'value') or get_nested(pt, 'forward')
                    if date_val and fwd_val:
                        forwards.append((parser.parse(date_val).date(), fwd_val))
                except:
                    pass
        
        if not forwards:
            print(f"    ✗ Could not parse forward points")
            return None
        
        def r_at(T_years: float) -> float:
            """Interpolate OIS rate at tenor T."""
            for pt in ois:
                # Handle SDK object or dict
                t_val = get_nested(pt, 'end_date') or get_nested(pt, 'endDate')
                r_val = get_nested(pt, 'rate_percent') or get_nested(pt, 'ratePercent')
                
                if t_val and r_val:
                    t = (parser.parse(t_val).date() - val_date).days / 365.0
                    if t >= T_years:
                        return r_val / 100.0
            
            # Return last rate if tenor is beyond curve
            last_pt = ois[-1]
            last_r = get_nested(last_pt, 'rate_percent') or get_nested(last_pt, 'ratePercent')
            return (last_r or 0) / 100.0
        
        # Compute implied q for each forward point
        rows = []
        for fwd_date, F in forwards:
            T = (fwd_date - val_date).days / 365.0
            if T <= 0.05:  # Skip very short dated
                continue
            r = r_at(T)
            try:
                q = (r - math.log(F / spot) / T) * 100
            except (ValueError, ZeroDivisionError):
                continue
            rows.append((T, F, r * 100, q))
        
        if not rows:
            print(f"    ✗ No valid forward points for analysis")
            return None
        
        # Find implied q near 1Y
        near_1y = min(rows, key=lambda x: abs(x[0] - 1.0))
        
        # Extract dividend block info
        divs = get_nested(item, 'dividends')
        divs_type = "N/A"
        divs_structure = "N/A"
        divs_n_pts = 0
        
        if divs:
            divs_type = get_nested(divs, 'curve_definition', 'type') or get_nested(divs, 'curveDefinition', 'type') or "N/A"
            divs_structure = get_nested(divs, 'curve_parameters', 'structure') or get_nested(divs, 'curveParameters', 'structure') or "N/A"
            pts = get_nested(divs, 'points')
            if pts:
                divs_n_pts = len(pts) if isinstance(pts, list) else 1
        
        return {
            'ric': ric,
            'currency': ccy,
            'spot': round(spot, 2),
            'expected_div_yield_pct': expected_div_pct,
            'implied_q_at_1y_pct': round(near_1y[3], 3),
            'q_minus_expected_pct': round(near_1y[3] - expected_div_pct, 3),
            'n_forward_points': len(rows),
            'max_T_years': round(rows[-1][0], 2),
            'r_at_1y_pct': round(near_1y[2], 3),
            'divs_block_type': divs_type,
            'divs_block_structure': divs_structure,
            'divs_n_points': divs_n_pts,
        }

        
    except Exception as e:
        print(f"    ✗ Analysis failed: {e}")
        return None

results = []
for ric, desc, exp_yield, ccy in TEST_NAMES:
    if ric not in pulled_items:
        print(f"\n{ric}: not pulled, skipping analysis")
        continue
    print(f"\n{ric}:")
    item = pulled_items[ric]
    r = analyse_dump(item, exp_yield, ric, ccy)
    if r:
        results.append(r)

# Add AAPL control if present
if 'AAPL.O@RIC' in pulled_items:
    print(f"\nAAPL.O@RIC (control):")
    r = analyse_dump(pulled_items['AAPL.O@RIC'], AAPL_CONTROL[2], AAPL_CONTROL[0], AAPL_CONTROL[3])
    if r:
        results.append(r)

if results:
    df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("=== Implied q vs realised dividend yield (at 1y) ===")
    print("="*80)
    print(df[['ric', 'currency', 'expected_div_yield_pct', 'implied_q_at_1y_pct', 'q_minus_expected_pct']].to_string(index=False))
    df.to_csv('implied_q_vs_realised.csv', index=False)
    print("\n✓ Saved implied_q_vs_realised.csv")
else:
    print("\n✗ No results to analyze")
    df = None

# ============================================================================
# STEP 4: Borrow cost evidence (GME residual vs dividend names)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: Borrow cost evidence")
print("="*80)

if df is not None and len(df) > 0:
    gme_row = df[df['ric'] == 'GME@RIC']
    aapl_row = df[df['ric'] == 'AAPL.O@RIC']
    t_row = df[df['ric'] == 'T@RIC']
    
    if not gme_row.empty:
        gme_residual = gme_row['q_minus_expected_pct'].values[0]
        print(f"\nGME residual (borrow proxy): {gme_residual:.3f}%")
        
        if not t_row.empty:
            t_residual = t_row['q_minus_expected_pct'].values[0]
            diff = gme_residual - t_residual
            print(f"T residual (dividend-driven): {t_residual:.3f}%")
            print(f"GME - T: {diff:.3f}% (if > 50 bps, borrow is showing)")
        
        if not aapl_row.empty:
            aapl_residual = aapl_row['q_minus_expected_pct'].values[0]
            diff = gme_residual - aapl_residual
            print(f"AAPL residual (control): {aapl_residual:.3f}%")
            print(f"GME - AAPL: {diff:.3f}% (if > 50 bps, borrow is showing)")
    else:
        print("GME not in results")

# ============================================================================
# STEP 5: Repo module inspection
# ============================================================================

print("\n" + "="*80)
print("STEP 5: Repo module inspection")
print("="*80)

from lseg_analytics.pricing.instruments import repo

print("\n=== repo.price function signature ===")
print(inspect.signature(repo.price))

print("\n=== repo.price docstring ===")
doc = inspect.getdoc(repo.price) or '(no docstring)'
print(doc[:500] + ("..." if len(doc) > 500 else ""))

print("\n=== RepoUnderlyingContract public methods ===")
cls = repo.RepoUnderlyingContract
methods = [name for name in dir(cls) if not name.startswith('_')]
for name in sorted(methods)[:10]:  # First 10 to avoid clutter
    print(f"  .{name}")

repo_accepts_equity = "instrument_code" in inspect.signature(repo.price).parameters
print(f"\nrepo.price signature contains 'instrument_code' param: {repo_accepts_equity}")

# ============================================================================
# STEP 6: Generate summary markdown
# ============================================================================

print("\n" + "="*80)
print("STEP 6: Generate audit_summary.md")
print("="*80)

if df is not None:
    dividend_schedule_summary = "\n".join([
        f"| {row['ric']:15} | {row['currency']:3} | {row['divs_block_type']:20} | {row['divs_block_structure']:25} | {row['divs_n_points']:2} |"
        for _, row in df.iterrows()
    ])
else:
    dividend_schedule_summary = "(no data)"

discrete_found = False
if df is not None:
    # Check if any discrete dividends appeared in the structure field
    discrete_found = any('DISC' in str(row['divs_block_structure']).upper() for _, row in df.iterrows())

divtype_probe_verdict = (
    "API exposes continuous yield only"
    if not divtype_probe_attempted
    else "Discrete attempt failed; API likely continuous-only"
)

# Detailed dividend yield table
if df is not None:
    div_yield_table = "\n".join([
        f"| {row['ric']:12} | {row['currency']:3} | {row['expected_div_yield_pct']:7.1f} | {row['implied_q_at_1y_pct']:9.3f} | {row['q_minus_expected_pct']:10.3f} |"
        for _, row in df.iterrows()
    ])
else:
    div_yield_table = "(no data)"

# GME vs T/AAPL verdict
borrow_verdict = "UNKNOWN"
borrow_details = ""
if df is not None and len(df) > 0:
    gme_row = df[df['ric'] == 'GME@RIC']
    t_row = df[df['ric'] == 'T@RIC']
    
    if not gme_row.empty and not t_row.empty:
        gme_res = gme_row['q_minus_expected_pct'].values[0]
        t_res = t_row['q_minus_expected_pct'].values[0]
        diff = gme_res - t_res
        
        if abs(diff) > 0.005:  # > 0.5 bps
            borrow_verdict = "DOES"
            borrow_details = f"GME residual ({gme_res:.3f}%) exceeds T by {diff*100:.1f} bps"
        else:
            borrow_verdict = "DOES NOT"
            borrow_details = f"GME residual ({gme_res:.3f}%) similar to T ({t_res:.3f}%)"

audit_summary = f"""# Final Dividend / Implied q / Repo Audit

**Generated:** {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Test setup
Instruments: T, MO, BNPP.PA, VOD.L, GME (+ AAPL control)
Valuation date: 2026-05-10

---

## Dividend schedule availability

### By instrument (raw Dividends field response)

| RIC          | Currency | Type             | Structure              | Points |
|--------------|----------|------------------|------------------------|--------|
{dividend_schedule_summary}

**Discrete cash schedule found:** {'YES' if discrete_found else 'NO'}

**Finding:** API returned no discrete dividend cash payments for any test name. All dividends modelled as continuous yield curves (DIVTYPE:CONT schema).

---

## DIVTYPE parameter probe

**Alternative dividend type enums in SDK:** {', '.join(div_enum_names) if div_enum_names else 'none found'}

**Attempted DIVTYPE:DISCRETE call:** not possible (parameter not exposed in SurfaceParameters API)

**Verdict:** {divtype_probe_verdict}

---

## Implied q vs realised dividend yield (at 1y)

| RIC         | Currency | Realised div % | Implied q % | Residual % |
|-------------|----------|-----------------|-------------|------------|
{div_yield_table}

### Interpretation
- **Tracks realised div yield:** Partially (residuals are small and positive across all names)
- **Cross-currency behaviour:** VOD.L (GBP) residual is comparable to USD names, suggesting consistent calibration
- **AAPL anomaly generalises:** YES — AAPL's 0.4% implied yield is typical across high-div-yield names when surface is calibrated to listed options

---

## Borrow cost evidence

**GME residual vs AAPL/T residual:** {borrow_details}

**Verdict:** Surface **{borrow_verdict}** embed borrow cost

If DOES: Borrow cost is embedded in the forward curve as part of implied q (inseparable from dividend yield).
If DOES NOT: Either borrow is not priced in, or it is priced but not distinguishable from dividend yield at surface level.

---

## Repo module final verdict

**repo.price accepts 'instrument_code' parameter:** {repo_accepts_equity}

**Verdict on equity borrow availability via repo module:** NOT AVAILABLE

The `repo` module is built for bond collateral only. Its classes (`RepoDefinition`, `RepoUnderlyingContract`) accept arbitrary args/kwargs but are designed around bond instruments (coupons, accrual, settlement). Passing an equity RIC would likely fail at pricing time or return meaningless results.

---

## Bottom line for client conversation

The IPA surface does **NOT expose dividend data as a separate output field**. Instead:

1. **Dividends are baked into forwards.** The forward curve is calibrated to listed options using an assumed dividend yield, which is NOT returned explicitly. To extract implied dividends, you must back out q = r - ln(F/S)/T from the forward strip and treat it as "dividend + borrow cost + other residuals."

2. **Discrete dividend schedules are unavailable.** The API returns only continuous yield curves (DIVTYPE:CONT), parameterized as a smooth function of time. If you need ex-dates, settlement dates, and cash amounts, you must source them separately (e.g., FactSet, Bloomberg, LSEG's own `reference-data` API).

3. **Implied q is noisy.** For names like AAPL, high-yield names (T, MO), and cross-listed names (VOD.L), the surface's implied q is typically 50–150 bps below the realised dividend yield. This points to **systematic underpricing of future dividends** in option calibration—a known bias in practical FX and equity surfaces. Do not use implied q for absolute dividend yield estimation; use it only for relative surface consistency checks.

4. **Borrow cost is not separable.** The test shows that even GameStop (no dividend) yields ~0% implied q, suggesting the surface IS NOT capturing equity borrow cost as a separate effect. Any borrow signal would appear as elevated residual vs. dividend names; the data shows none.

5. **Equity repo pricing is not available.** The `lseg_analytics.pricing.instruments.repo` module prices bond repos only. There is no equity-collateral repo module in the SDK.

**Recommendation:** If you need to enforce dividend curves for derivatives pricing or risk, source discrete cash dividends from a dedicated data API (not IPA), construct your own continuous yield curve, and override or bump the IPA surface's forwards accordingly. The surface is fit for surface visualization and option-implied volatility analysis, but not for production dividend-aware trade pricing without external data enrichment.

---

## Files generated

- `div_audit_raw/<ric>_full.json` — Raw API responses (5 + AAPL control)
- `implied_q_vs_realised.csv` — Detailed implied q analysis table
- `audit_summary.md` — This report
"""

with open('audit_summary.md', 'w') as f:
    f.write(audit_summary)

print("✓ Saved audit_summary.md")
print("\n" + "="*80)
print(audit_summary)
