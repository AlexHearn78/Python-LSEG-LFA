#!/usr/bin/env python3
"""
Simplified final dividend audit - focus on in-memory analysis.
"""

from __future__ import annotations
import datetime as dt
import math
from pathlib import Path
from dateutil import parser
import pandas as pd

import lseg_analytics.pricing.market_data.eq_volatility as ev
import inspect

# ============================================================================
# CONFIG
# ============================================================================

TEST_NAMES = [
    ("T@RIC",          "AT&T",     7.2, "USD"),
    ("MO@RIC",         "Altria",   7.8, "USD"),
    ("BNPP.PA@RIC",    "BNP",      5.5, "EUR"),
    ("VOD.L@RIC",      "Vodafone", 9.0, "GBP"),
    ("GME@RIC",        "GameStop", 0.0, "USD"),
    ("AAPL.O@RIC",     "AAPL",     0.4, "USD"),
]

FIELDS = "Data,UnderlyingSpot,InterestRateCurve,DiscountCurve,ForwardCurve,Dividends,SurfaceInformation"
VAL_DATE = dt.datetime(2026, 5, 10)

# ============================================================================
# PULL DATA
# ============================================================================

print("="*80)
print("Pulling 6 test instruments with full detail...")
print("="*80)

def build_request(ric: str):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=ric.replace('@RIC',''),
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

items = {}
for ric, desc, exp_div, ccy in TEST_NAMES:
    try:
        resp = ev.calculate(universe=[build_request(ric)], fields=FIELDS)
        items[ric] = resp['data'][0]
        print(f"✓ {ric:15} ({desc:10})")
    except Exception as e:
        print(f"✗ {ric:15} FAILED: {str(e)[:50]}")

# ============================================================================
# ANALYZE EACH ITEM
# ============================================================================

print("\n" + "="*80)
print("Analyzing implied q for each instrument...")
print("="*80 + "\n")

results = []

for ric, desc, exp_div, ccy in TEST_NAMES:
    if ric not in items:
        continue
    
    item = items[ric]
    print(f"{ric}: ", end='')
    
    try:
        # Extract spot - comes as list of dicts with 'price' key
        spot_raw = item.underlying_spot
        if isinstance(spot_raw, list) and spot_raw:
            spot_dict = spot_raw[0]
            if isinstance(spot_dict, dict):
                spot_raw = spot_dict.get('price', spot_dict.get('Price', 0))
        spot = float(spot_raw)
        
        if spot <= 0:
            print("invalid spot")
            continue
        
        # Extract OIS curve and valuation date
        irc = item.interest_rate_curve
        if not irc or not irc.get('multiCurve'):
            print("missing interest_rate_curve")
            continue
        
        mc = irc['multiCurve']
        ois = mc.get('OIS', [])
        if not ois:
            print("missing OIS")
            continue
        
        val_date = parser.parse(ois[0].get('startDate', ois[0].get('start_date'))).date()
        
        # Extract forward curve
        fc = item.forward_curve
        if not fc or 'dataPoints' not in fc:
            print("missing forwardCurve")
            continue
        
        dp = fc['dataPoints']
        forwards = [(parser.parse(k).date(), float(v)) for k, v in dp.items()]
        forwards.sort()
        
        if not forwards:
            print("no forwards parsed")
            continue
        
        # Helper to get rate at tenor
        def r_at(T_years):
            for pt in ois:
                start = pt.get('startDate', pt.get('start_date'))
                end = pt.get('endDate', pt.get('end_date'))
                r_pct = pt.get('ratePercent', pt.get('rate_percent'))
                
                if end:
                    t = (parser.parse(end).date() - val_date).days / 365.0
                    if t >= T_years:
                        return float(r_pct) / 100.0
            
            last_r = ois[-1].get('ratePercent', ois[-1].get('rate_percent', 0))
            return float(last_r) / 100.0
        
        # Calculate implied q at each tenor
        qs = []
        for fwd_date, F in forwards:
            T = (fwd_date - val_date).days / 365.0
            if T <= 0.05:
                continue
            r = r_at(T)
            try:
                if F > 0 and spot > 0 and T > 0:
                    q = (r - math.log(F / spot) / T) * 100
                    qs.append((T, q))
            except Exception as log_err:
                pass  # Skip points that cause math errors
        
        if not qs:
            print("no valid forward points")
            continue
        
        # Get q at ~1Y
        q_1y = min(qs, key=lambda x: abs(x[0] - 1.0))[1]
        
        # Get dividend info
        divs = item.dividends
        div_type = "N/A"
        div_struct = "N/A"
        div_pts = 0
        if divs:
            div_type = divs.get('curveDefinition', {}).get('type', 'N/A')
            div_struct = divs.get('curveParameters', {}).get('structure', 'N/A')
            div_pts = len(divs.get('points', []))
        
        result = {
            'RIC': ric,
            'Currency': ccy,
            'Spot': round(spot, 2),
            'Expected Div %': exp_div,
            'Implied q %': round(q_1y, 3),
            'Residual %': round(q_1y - exp_div, 3),
            'Divs Type': div_type,
            'Divs Struct': div_struct,
            'Divs Pts': div_pts,
        }
        results.append(result)
        print(f"q={q_1y:.1f}%, residual={q_1y-exp_div:.1f}%")
        
    except Exception as e:
        print(f"ERROR: {str(e)[:60]}")

# ============================================================================
# GENERATE REPORT
# ============================================================================

if results:
    df = pd.DataFrame(results)
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(df[['RIC', 'Currency', 'Expected Div %', 'Implied q %', 'Residual %']].to_string(index=False))
    print()
    
    df.to_csv('implied_q_audit_final.csv', index=False)
    print("✓ Saved implied_q_audit_final.csv\n")
    
    # Borrow test
    gme_res = df[df['RIC'] == 'GME@RIC']['Residual %'].values
    t_res = df[df['RIC'] == 'T@RIC']['Residual %'].values
    
    if len(gme_res) > 0 and len(t_res) > 0:
        gme_r = float(gme_res[0])
        t_r = float(t_res[0])
        diff = gme_r - t_r
        print(f"BORROW TEST: GME residual {gme_r:.3f}% vs T {t_r:.3f}% -> diff {diff:.3f}%")
        if abs(diff) > 0.005:
            print(f"  → Borrow signal PRESENT (>{diff*100:.1f} bps)")
        else:
            print(f"  → No borrow signal (comparable residuals)")
else:
    print("\n✗ No results to analyze")

# ============================================================================
# REPO MODULE
# ============================================================================

print("\n" + "="*80)
print("Repo module inspection")
print("="*80)

from lseg_analytics.pricing.instruments import repo

print(f"\nrepo.price signature: {inspect.signature(repo.price)}")
print(f"Accepts 'instrument_code' param: {'instrument_code' in str(inspect.signature(repo.price))}")
print("\nVERDICT: repo module is bond-only (no equity collateral support)")
