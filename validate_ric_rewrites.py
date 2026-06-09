import os
import pandas as pd
from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt
import json
import numpy as np
from dateutil import parser
import time

# Manual overrides for known delisted/acquired names
MANUAL_OVERRIDES = {
    'ATVI US': 'ATVI@RIC',  # Acquired by Microsoft Oct 2023
    'TWTR US': None,  # Delisted Oct 2022
    'DISH US': None,  # Merged Jan 2024
    'SGEN US': None,  # Acquired by Pfizer Dec 2023
    'BHP LN': 'BHP.AX@RIC',  # Unified to ASX
    'K DP': None,  # Event marker ^L25, delisted
    '0011 HK': None,  # Event marker ^A26, delisted
}

def build_candidates(row):
    """Build ordered list of RIC candidates to try"""
    proposed = row['ric_proposed'].replace('@RIC', '').strip()
    original = row['ric_original'].replace('@RIC', '').strip()
    country = row['country'].strip()
    inst_type = row['type'].strip()
    bbg_name = row['bbg_name'].strip()
    
    candidates = []
    
    # Check for manual override
    if bbg_name in MANUAL_OVERRIDES:
        override = MANUAL_OVERRIDES[bbg_name]
        if override:
            candidates.append(override.replace('@RIC', ''))
        else:
            return [None]  # Delisted marker
    
    # Always try the proposed first
    if proposed:
        candidates.append(proposed)
    
    # For US single names rewritten to bare ticker, try exchange suffixes
    if country == 'US' and inst_type == 'Single name' and '.' not in proposed:
        for sfx in ['.O', '.N', '.A']:
            cand = proposed + sfx
            if cand not in candidates:
                candidates.append(cand)
    
    # For US ETFs rewritten to .O, also try .K and .P
    if country == 'US' and inst_type == 'US ETF':
        base = proposed.split('.')[0] if '.' in proposed else proposed
        for sfx in ['.O', '.K', '.P']:
            cand = base + sfx
            if cand not in candidates:
                candidates.append(cand)
    
    # Always include the original RIC as final fallback
    if original and original not in candidates:
        candidates.append(original)
    
    return candidates

def test_ric(ric):
    """Test if a RIC has a vol surface. Returns (works, error_message)"""
    if not ric or ric == 'None':
        return False, "invalid ric"
    
    try:
        surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2026, 5, 10),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ric} test",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        response = ev.calculate(universe=[request_item])
        
        if not response or 'data' not in response or not response['data']:
            return False, "empty response"
        
        data_item = response['data'][0]
        if not data_item or not data_item.get('surface'):
            return False, "no surface data"
        
        return True, None
        
    except Exception as e:
        return False, str(e)[:100]

def test_ric_candidates(row):
    """Test candidates for a row. Returns (ric_resolved, attempts, n_attempts)"""
    candidates = build_candidates(row)
    
    if candidates == [None]:
        return '', [('DELISTED', False, 'manual override')], 1
    
    attempts = []
    for ric in candidates:
        if not ric:
            continue
        works, error = test_ric(ric)
        attempts.append((ric, works, error if error else 'ok'))
        if works:
            return ric, attempts, len(attempts)
        time.sleep(0.1)  # Rate limiting
    
    return '', attempts, len(attempts)

def interpolate_rate(discount_curve, T_years):
    """Linear interpolation of zero rate at T_years"""
    if not discount_curve:
        return 0.0
    
    sorted_curve = sorted(discount_curve, key=lambda x: x['endDate'])
    
    for i in range(len(sorted_curve) - 1):
        curr = sorted_curve[i]
        next_ = sorted_curve[i+1]
        
        curr_date = parser.parse(curr['endDate'])
        next_date = parser.parse(next_['endDate'])
        val_date = parser.parse(sorted_curve[0]['startDate'])
        
        curr_T = (curr_date - val_date).days / 365.0
        next_T = (next_date - val_date).days / 365.0
        
        if curr_T <= T_years <= next_T:
            r1 = curr['ratePercent'] / 100.0
            r2 = next_['ratePercent'] / 100.0
            return r1 + (r2 - r1) * (T_years - curr_T) / (next_T - curr_T)
    
    last = sorted_curve[-1]
    return last['ratePercent'] / 100.0

def pull_surface_batch(rics_with_meta):
    """Pull full surface + forwards for a batch of RICs"""
    request_items = []
    for meta in rics_with_meta:
        ric = meta['ric_resolved']
        surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2026, 5, 10),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ric} batch",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        request_items.append(request_item)
    
    try:
        response = ev.calculate(universe=request_items)
        results = []
        for i, meta in enumerate(rics_with_meta):
            if 'data' in response and i < len(response['data']):
                data_item = response['data'][i]
                spot = data_item.get('underlyingSpot', 0)
                forward_curve = data_item.get('forwardCurve', {})
                interest_curve = data_item.get('interestRateCurve', {})
                
                ois_curve = interest_curve.get('multiCurve', {}).get('OIS', [])
                val_date = None
                if ois_curve:
                    val_date = parser.parse(ois_curve[0]['startDate'])
                
                forwards = []
                if 'dataPoints' in forward_curve:
                    for date_str, fwd_price in forward_curve['dataPoints'].items():
                        fwd_date = parser.parse(date_str)
                        forwards.append((fwd_date, fwd_price))
                forwards.sort(key=lambda x: x[0])
                
                results.append({
                    'meta': meta,
                    'spot': spot,
                    'valuation_date': val_date,
                    'forwards': forwards,
                    'discount_curve': ois_curve,
                    'error': None,
                    'sparse': len(forwards) < 3
                })
            else:
                results.append({
                    'meta': meta,
                    'error': 'no data in response',
                    'sparse': True
                })
        return results
    except Exception as e:
        return [{'meta': meta, 'error': str(e)[:100], 'sparse': True} for meta in rics_with_meta]

def decompose_forwards(result, row):
    """Decompose forwards into implied dividend yields"""
    if result.get('error'):
        return [], None
    
    spot = result['spot']
    val_date = result['valuation_date']
    forwards = result['forwards']
    discount_curve = result['discount_curve']
    
    ric = row['ric_resolved']
    bbg_name = row['bbg_name']
    region = row['region']
    
    currency = 'USD'  # Default
    rows = []
    q_values = []
    
    for fwd_date, fwd_price in forwards:
        T_days = (fwd_date - val_date).days
        T_years = T_days / 365.0
        
        r = interpolate_rate(discount_curve, T_years)
        
        if spot > 0 and fwd_price > 0:
            try:
                ln_term = np.log(fwd_price / spot)
                q = r - ln_term / T_years
                carry = r - q
                fwd_premium_pct = (fwd_price / spot - 1) * 100
            except:
                q = np.nan
                carry = np.nan
                fwd_premium_pct = np.nan
        else:
            q = np.nan
            carry = np.nan
            fwd_premium_pct = np.nan
        
        low_confidence = T_years < 0.05
        
        row_dict = {
            'ric_resolved': ric,
            'bbg_name': bbg_name,
            'region': region,
            'currency': currency,
            'valuation_date': val_date.strftime('%Y-%m-%d') if val_date else None,
            'expiry_date': fwd_date.strftime('%Y-%m-%d'),
            'T_years': round(T_years, 4),
            'spot': round(spot, 4),
            'F': round(fwd_price, 4),
            'forward_premium_pct': round(fwd_premium_pct, 4) if not np.isnan(fwd_premium_pct) else np.nan,
            'r_pct': round(r * 100, 4),
            'implied_q_pct': round(q * 100, 4) if not np.isnan(q) else np.nan,
            'carry_pct': round(carry * 100, 4) if not np.isnan(carry) else np.nan,
            'low_confidence': low_confidence
        }
        rows.append(row_dict)
        
        if not np.isnan(q):
            q_values.append((T_years, q * 100))
    
    # Summary
    n_tenors = len(forwards)
    max_T = max(T_years for _, T_years in [(d, (d - val_date).days / 365.0) for d, _ in forwards]) if forwards else 0
    valid_q = [q for _, q in q_values]
    
    if valid_q:
        min_q = min(valid_q)
        median_q = np.median(valid_q)
        max_q = max(valid_q)
        if len(q_values) > 1:
            x = [t for t, _ in q_values]
            y = valid_q
            slope = np.polyfit(x, y, 1)[0]
        else:
            slope = 0
    else:
        min_q = median_q = max_q = slope = np.nan
    
    summary = {
        'ric_resolved': ric,
        'bbg_name': bbg_name,
        'currency': currency,
        'spot': round(spot, 4),
        'val_date': val_date.strftime('%Y-%m-%d') if val_date else None,
        'n_tenors': n_tenors,
        'max_T': round(max_T, 2),
        'median_q_pct': round(median_q, 4) if not np.isnan(median_q) else np.nan,
        'slope_q_per_year': round(slope, 4) if not np.isnan(slope) else np.nan,
    }
    
    return rows, summary

def main():
    # Read CSV
    df = pd.read_csv('/Users/alexanderhearn/Downloads/files 2/ric_rewrites_only.csv')
    
    # Create output directory
    os.makedirs('forwards_output', exist_ok=True)
    
    # Resolution phase
    print("\n=== Phase 1: RIC Validation ===\n")
    
    resolution_results = []
    resolved_rows = []
    failed_rows = []
    
    for idx, (_, row) in enumerate(df.iterrows()):
        bbg_name = row['bbg_name']
        print(f"[{idx+1:2d}/93] {bbg_name:20s} ", end='', flush=True)
        
        ric_resolved, attempts, n_attempts = test_ric_candidates(row)
        
        status = 'RESOLVED' if ric_resolved else ('DELISTED' if n_attempts == 1 and attempts[0][0] == 'DELISTED' else 'EXHAUSTED')
        
        # Print attempt summary
        for i, (ric_tried, works, msg) in enumerate(attempts):
            symbol = '✓' if works else '✗'
            if ric_tried != 'DELISTED':
                print(f"{ric_tried}{symbol} ", end='', flush=True)
        
        if ric_resolved:
            # Get spot from successful response
            works, _ = test_ric(ric_resolved)
            print(f" → resolved={ric_resolved}", end='')
        
        print()
        
        resolution_results.append({
            'bbg_name': bbg_name,
            'isin': row['isin'],
            'region': row['region'],
            'country': row['country'],
            'type': row['type'],
            'ric_original': row['ric_original'],
            'ric_proposed': row['ric_proposed'],
            'ric_resolved': ric_resolved,
            'n_attempts': n_attempts,
            'attempts_json': json.dumps(attempts),
            'status': status
        })
        
        if ric_resolved:
            resolved_rows.append({**row.to_dict(), 'ric_resolved': ric_resolved})
        elif status != 'DELISTED':
            failed_rows.append({**row.to_dict(), 'attempts': attempts})
    
    # Write resolution results
    res_df = pd.DataFrame(resolution_results)
    res_df.to_csv('forwards_output/ric_resolution.csv', index=False)
    
    # Phase 2: Surface pull + decompose
    print("\n=== Phase 2: Forward Curve Extraction ===\n")
    
    all_forward_rows = []
    all_summaries = []
    batch_size = 10
    
    for i in range(0, len(resolved_rows), batch_size):
        batch = resolved_rows[i:i+batch_size]
        batch_num = i // batch_size + 1
        n_batches = (len(resolved_rows) + batch_size - 1) // batch_size
        
        print(f"[batch {batch_num}/{n_batches}] Pulling {len(batch)} RICs... ", end='', flush=True)
        batch_start = time.time()
        
        batch_meta = [{'ric_resolved': r['ric_resolved']} for r in batch]
        results = pull_surface_batch(batch_meta)
        
        for result, row in zip(results, batch):
            if result.get('error'):
                failed_rows.append({**row, 'pull_error': result['error']})
            else:
                forward_rows, summary = decompose_forwards(result, row)
                all_forward_rows.extend(forward_rows)
                summary['sparse'] = result.get('sparse', False)
                all_summaries.append(summary)
        
        batch_time = time.time() - batch_start
        success_count = sum(1 for r in results if not r.get('error'))
        print(f"{success_count}/{len(batch)} ok in {batch_time:.1f}s")
        
        time.sleep(0.1)  # Rate limiting between batches
    
    # Write forward data
    if all_forward_rows:
        long_df = pd.DataFrame(all_forward_rows)
        long_df.to_csv('forwards_output/forwards_long.csv', index=False)
    
    if all_summaries:
        summary_df = pd.DataFrame(all_summaries)
        summary_df.to_csv('forwards_output/forwards_summary.csv', index=False)
    
    # Write failures
    if failed_rows:
        fail_df = pd.DataFrame(failed_rows)
        fail_df.to_csv('forwards_output/forwards_failures.csv', index=False)
    
    # Print summary
    n_resolved = len(resolved_rows)
    n_total = len(df)
    n_extracted = len(all_summaries)
    n_failed = n_resolved - n_extracted
    n_tenors = len(all_forward_rows)
    
    print("\n=== Summary ===")
    print(f"Resolution rate: {n_resolved}/{n_total} ({100*n_resolved//n_total}%)")
    print(f"Forwards extracted: {n_extracted} RICs, {n_tenors} (ric, expiry) tenor points")
    print(f"Failures: {n_failed} — see forwards_failures.csv")
    print(f"\nOutput files:")
    print(f"  forwards_output/ric_resolution.csv")
    print(f"  forwards_output/forwards_long.csv ({n_tenors} rows)")
    print(f"  forwards_output/forwards_summary.csv ({n_extracted} rows)")
    if failed_rows:
        print(f"  forwards_output/forwards_failures.csv ({n_failed} rows)")

if __name__ == '__main__':
    main()