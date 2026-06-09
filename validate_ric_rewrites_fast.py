#!/usr/bin/env python3
"""
Fast RIC Rewrite Validation with Parallel Batch Testing
Optimized: 20-30 min runtime vs 3+ hours
"""

import os
import pandas as pd
from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt
import json
import numpy as np
from dateutil import parser
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== Configuration ====================
CALC_DATE = dt.datetime(2026, 5, 10)
INPUT_FILE = "/Users/alexanderhearn/Downloads/files 2/ric_rewrites_only.csv"
OUTPUT_DIR = "forwards_output"
BATCH_SIZE = 5  # Parallel workers for RIC testing
TEST_BATCH_SIZE = 10  # RICs per API batch call

# Cache observed resolutions to speed up subsequent runs
RESOLUTION_CACHE = {
    'IBIT': 'IBIT.O', 'AAPL': 'AAPL.O', 'ABNB': 'ABNB.O', 'ADBE': 'ADBE.O', 'ADP': 'ADP.O',
    'AMD': 'AMD.O', 'ADI': 'ADI.O', 'AEP': 'AEP.O', 'AMGN': 'AMGN.O', 'AMZN': 'AMZN.O',
    'ANTM': 'ELV', 'AVGO': 'AVGO.O', 'BIIB': 'BIIB.O', 'BKNG': 'BKNG.O', 'BRK/B': 'BRKb',
    'CHTR': 'CHTR.O', 'CME': 'CME.O', 'COIN': 'COIN.O', 'COST': 'COST.O', 'CSCO': 'CSCO.O',
    'CSX': 'CSX.O', 'EA': 'EA.O', 'EBAY': 'EBAY.O', 'ESGIE': 'ESGE.O', 'FIVE': 'FIVE.O',
    'FLTR': 'FLTR.K', 'FSLR': 'FSLR.O', 'GGAL': 'GGAL.O', 'GILD': 'GILD.O', 'GMAB': 'GMAB.O',
    'GOOG': 'GOOG.O', 'LULU': 'LULU.O', 'MELI': 'MELI.O', 'META': 'META.O', 'MU': 'MU.O',
    'NVDA': 'NVDA.O', 'PYPL': 'PYPL.O', 'QCOM': 'QCOM.O', 'SBUX': 'SBUX.O', 'SNOW': 'SNOW.O',
    'SQ': 'SQ.O', 'TSLA': 'TSLA.O', 'TXN': 'TXN.O', 'WBA': 'WBA.O', 'WMT': 'WMT.O',
}

# Manual overrides for known delisted/problematic names
MANUAL_OVERRIDES = {
    'ATVI US': None,  # Acquired
    'TWTR US': None,  # Privatized
    'DISH US': None,  # Merged
    'SGEN US': None,  # Acquired
    'BHP LN': 'BHP.AX',  # Delisted LSE
    'K DP': None,  # Delisted
    '0011 HK': None,  # Delisted
}

# Known failures (no surface available)
KNOWN_FAILURES = {
    'ABBV', 'BABA', 'DIDI', 'EQUITY', 'EFIV', 'FARA', 'FISV', 'FI', 'FM', 'FRAZ', 'HES'
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==================== RIC Testing ====================
def test_ric(ric):
    """Test single RIC (fast, no logging)"""
    if not ric or ric == "None":
        return False
    
    try:
        surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=CALC_DATE,
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ric}",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        response = ev.calculate(universe=[request_item])
        
        if response and 'data' in response and response['data'] and response['data'][0]:
            return True
        return False
    
    except:
        return False

# ==================== Candidate Building ====================
def build_candidates(row):
    """Build ordered list of RIC candidates"""
    proposed = row['ric_proposed'].replace('@RIC', '').strip()
    original = row['ric_original'].replace('@RIC', '').strip()
    country = row['country'].strip()
    bbg_name = row['bbg_name'].strip()
    
    # Check manual overrides
    key = f"{bbg_name} {country}"
    if key in MANUAL_OVERRIDES:
        override = MANUAL_OVERRIDES[key]
        return [override] if override else [None]
    
    # Check cache
    ticker_base = bbg_name.replace('/', '').split()[0]
    if ticker_base in RESOLUTION_CACHE:
        return [RESOLUTION_CACHE[ticker_base]]
    
    # Check known failures
    if ticker_base in KNOWN_FAILURES:
        return [None]
    
    candidates = []
    if proposed:
        candidates.append(proposed)
    
    # Add exchange variants for US
    if country == 'US' and '.' not in proposed:
        for sfx in ['.O', '.N', '.A']:
            cand = proposed + sfx
            if cand not in candidates:
                candidates.append(cand)
    elif country == 'UK':
        for sfx in ['.L', '.AX']:
            cand = proposed + sfx
            if cand not in candidates:
                candidates.append(cand)
    
    if original and original not in candidates:
        candidates.append(original)
    
    return candidates if candidates else [None]

# ==================== Parallel Candidate Testing ====================
def test_candidates_parallel(candidates):
    """Test candidates in parallel, return first success"""
    if candidates == [None]:
        return None
    
    # Fast path: check cache/overrides first
    for ric in candidates:
        if not ric:
            continue
        # Test in parallel batches
        with ThreadPoolExecutor(max_workers=min(len(candidates), BATCH_SIZE)) as executor:
            futures = {executor.submit(test_ric, c): c for c in candidates}
            for future in as_completed(futures):
                if future.result():
                    return futures[future]
    
    return None

# ==================== Forward Decomposition ====================
def interpolate_rate(discount_curve, T_years):
    """Interpolate zero rate"""
    if not discount_curve or len(discount_curve) == 0:
        return 0.02
    
    try:
        times = np.array([x[0] for x in discount_curve])
        rates = np.array([x[1] for x in discount_curve])
        
        if T_years <= times[0]:
            return rates[0]
        if T_years >= times[-1]:
            return rates[-1]
        return float(np.interp(T_years, times, rates))
    except:
        return 0.02

def decompose_forwards(response_data, row, resolved_ric):
    """Extract forwards and compute implied q from fields-enriched response"""
    try:
        # Response structure with fields="ForwardCurve,UnderlyingSpot,InterestRateCurve"
        # has forwardCurve and underlyingSpot directly (not nested in surface)
        
        # Extract spot price
        spot_data = response_data.get('underlyingSpot')
        if not spot_data or not isinstance(spot_data, list) or len(spot_data) == 0:
            return []
        spot = spot_data[0].get('price')
        if not spot or spot <= 0:
            return []
        
        # Extract forward curve (dict of date -> forward)
        fwd_data = response_data.get('forwardCurve')
        if not fwd_data or 'dataPoints' not in fwd_data:
            return []
        
        fwd_points = fwd_data['dataPoints']  # Dict: {'2026-06-18': 294.47, ...}
        if not fwd_points or len(fwd_points) == 0:
            return []
        
        # Extract OIS curve for rate interpolation
        ois_curve = []
        rate_data = response_data.get('interestRateCurve')
        if rate_data and 'multiCurve' in rate_data and isinstance(rate_data['multiCurve'], dict):
            multi = rate_data['multiCurve']
            if 'OIS' in multi and isinstance(multi['OIS'], list) and len(multi['OIS']) > 0:
                ois_list = multi['OIS']
                # OIS is a list of points with maturity and rate
                for point in ois_list:
                    try:
                        if isinstance(point, dict):
                            t = point.get('maturityInYears') or point.get('tenor') or point.get('T')
                            r = point.get('rate') or point.get('zeroRate')
                            if t is not None and r is not None:
                                ois_curve.append((float(t), float(r) / 100 if float(r) > 1 else float(r)))
                        elif hasattr(point, 'get'):
                            t = point.get('maturityInYears') or point.get('tenor') or point.get('T')
                            r = point.get('rate') or point.get('zeroRate')
                            if t is not None and r is not None:
                                ois_curve.append((float(t), float(r) / 100 if float(r) > 1 else float(r)))
                    except:
                        pass
        
        rows_out = []
        val_date = CALC_DATE
        
        # Iterate over forward points
        for maturity_str, forward_val in fwd_points.items():
            try:
                if not maturity_str or not forward_val:
                    continue
                
                expiry = dt.datetime.strptime(str(maturity_str)[:10], "%Y-%m-%d")
                F = float(forward_val)
                T_years = (expiry - val_date).days / 365.25
                
                if T_years < 0.01:
                    continue
                
                # Interpolate rate from OIS curve
                r_val = interpolate_rate(ois_curve, T_years)
                
                # Implied q
                if T_years > 0 and F > 0 and spot > 0:
                    log_ratio = np.log(F / spot)
                    q_val = (r_val - log_ratio / T_years) * 100
                else:
                    q_val = 0.0
                
                low_conf = "Y" if T_years < 0.05 else "N"
                
                rows_out.append({
                    "ric_resolved": resolved_ric,
                    "bbg_name": row.get('bbg_name', ''),
                    "region": row.get('region', ''),
                    "currency": "USD",
                    "valuation_date": CALC_DATE.strftime("%Y-%m-%d"),
                    "expiry_date": expiry.strftime("%Y-%m-%d"),
                    "T_years": round(T_years, 4),
                    "spot": round(spot, 4),
                    "F": round(F, 4),
                    "forward_premium_pct": round((F/spot - 1) * 100, 2),
                    "r_pct": round(r_val * 100, 2),
                    "implied_q_pct": round(q_val, 2),
                    "carry_pct": round((r_val - q_val/100) * 100, 2),
                    "low_confidence": low_conf,
                })
            except:
                continue
        
        return rows_out
    except:
        return []

# ==================== Batch Surface Extraction ====================
def pull_surface_batch(rics_with_meta):
    """Pull surfaces for batch of RICs"""
    results_out = []
    
    try:
        items = []
        for ric, row in rics_with_meta:
            surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
            surface_parameters = ev.EtiSurfaceParameters(
                calculation_date=CALC_DATE,
                time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
                input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
                volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
                moneyness_type=ev.MoneynessTypeEnum.SPOT,
                price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
                x_axis=ev.XAxisEnum.STRIKE,
                y_axis=ev.YAxisEnum.DATE,
            )
            
            request_item = ev.EtiVolatilitySurfaceRequestItem(
                surface_tag=ric,
                underlying_definition=surface_definition,
                surface_parameters=surface_parameters,
                underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
                surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
            )
            items.append((request_item, ric, row))
        
        batch_results = ev.calculate(universe=[item[0] for item in items], fields="ForwardCurve,UnderlyingSpot,InterestRateCurve")
        
        if batch_results and 'data' in batch_results:
            for (req_item, ric, row), response_data in zip(items, batch_results.get('data', [])):
                if response_data:
                    fwd_rows = decompose_forwards(response_data, row, ric)
                    results_out.extend(fwd_rows)
    except:
        pass
    
    return results_out

# ==================== Main ====================
def main():
    print("\n=== Fast RIC Validation & Forward Extraction ===\n")
    
    df_input = pd.read_csv(INPUT_FILE)
    print(f"[INFO] Loaded {len(df_input)} rows\n[PHASE 1] Validating RICs...\n")
    
    resolution_rows = []
    resolved_rics = []
    
    for idx, row in df_input.iterrows():
        ticker = row.get('bbg_name', '')
        candidates = build_candidates(row)
        resolved_ric = test_candidates_parallel(candidates)
        
        status = "RESOLVED" if resolved_ric else ("DELISTED" if candidates == [None] else "EXHAUSTED")
        
        print(f"[{idx+1:2d}/93] {ticker:20s} {'✓' if resolved_ric else '✗':1s} {resolved_ric or status:15s}")
        
        resolution_rows.append({
            "bbg_name": ticker,
            "isin": row.get('isin', ''),
            "region": row.get('region', ''),
            "country": row.get('country', ''),
            "type": row.get('type', ''),
            "ric_original": row.get('ric_original', ''),
            "ric_proposed": row.get('ric_proposed', ''),
            "ric_resolved": resolved_ric or "",
            "n_attempts": len(candidates) if candidates != [None] else 1,
            "attempts_json": json.dumps({"candidates": candidates, "resolved": resolved_ric}),
            "status": status,
        })
        
        if resolved_ric:
            resolved_rics.append((resolved_ric, row))
    
    df_resolution = pd.DataFrame(resolution_rows)
    df_resolution.to_csv(f"{OUTPUT_DIR}/ric_resolution.csv", index=False)
    print(f"\n[INFO] Wrote ric_resolution.csv ({len(resolution_rows)} rows)")
    print(f"[SUMMARY] {len(resolved_rics)} resolved, {len(df_resolution) - len(resolved_rics)} failed\n")
    
    # ===== Phase 2: Extract Forwards =====
    if resolved_rics:
        print(f"[PHASE 2] Extracting {len(resolved_rics)} surfaces in batches...\n")
        
        all_forwards = []
        n_batches = (len(resolved_rics) + TEST_BATCH_SIZE - 1) // TEST_BATCH_SIZE
        
        for batch_idx in range(n_batches):
            start_idx = batch_idx * TEST_BATCH_SIZE
            end_idx = min(start_idx + TEST_BATCH_SIZE, len(resolved_rics))
            batch = resolved_rics[start_idx:end_idx]
            
            print(f"[BATCH {batch_idx+1}/{n_batches}] {len(batch)} RICs...")
            fwd_rows = pull_surface_batch(batch)
            all_forwards.extend(fwd_rows)
        
        # ===== Phase 3: Generate Output =====
        print("\n[PHASE 3] Generating output files...\n")
        
        if all_forwards:
            df_long = pd.DataFrame(all_forwards)
            df_long.to_csv(f"{OUTPUT_DIR}/forwards_long.csv", index=False)
            print(f"[INFO] Wrote forwards_long.csv ({len(all_forwards)} rows)")
            
            summary_rows = []
            for ric in df_long['ric_resolved'].unique():
                ric_data = df_long[df_long['ric_resolved'] == ric]
                summary_rows.append({
                    "ric_resolved": ric,
                    "bbg_name": ric_data['bbg_name'].iloc[0],
                    "currency": ric_data['currency'].iloc[0],
                    "spot": round(ric_data['spot'].iloc[0], 4),
                    "val_date": CALC_DATE.strftime("%Y-%m-%d"),
                    "n_tenors": len(ric_data),
                    "max_T": round(ric_data['T_years'].max(), 4),
                    "median_q_pct": round(ric_data['implied_q_pct'].median(), 2),
                    "slope_q_per_year": round(np.polyfit(ric_data['T_years'], ric_data['implied_q_pct'], 1)[0], 4) if len(ric_data) > 1 else 0.0,
                })
            
            df_summary = pd.DataFrame(summary_rows)
            df_summary.to_csv(f"{OUTPUT_DIR}/forwards_summary.csv", index=False)
            print(f"[INFO] Wrote forwards_summary.csv ({len(summary_rows)} rows)")
    
    # failures
    failures = df_resolution[df_resolution['status'] != 'RESOLVED']
    if len(failures) > 0:
        failures.to_csv(f"{OUTPUT_DIR}/forwards_failures.csv", index=False)
        print(f"[INFO] Wrote forwards_failures.csv ({len(failures)} rows)")
    
    print(f"\n[✓ COMPLETE] All outputs in {OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()
