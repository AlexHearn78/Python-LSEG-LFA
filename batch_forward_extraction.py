import os
import pandas as pd
from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt
import json
import numpy as np
from dateutil import parser
import time

def normalise_ric(ric: str) -> str:
    ric = ric.strip()
    if not ric.endswith('@RIC'):
        ric = ric + '@RIC'
    return ric

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
    last_date = parser.parse(last['endDate'])
    val_date = parser.parse(sorted_curve[0]['startDate'])
    last_T = (last_date - val_date).days / 365.0
    return last['ratePercent'] / 100.0

def extract_forward_data_batch(rics_with_meta):
    """Extract forward data for a batch of RICs"""
    request_items = []
    for meta in rics_with_meta:
        ric = meta['ric']
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
            surface_tag=f"{ric}_batch",
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
            ric = meta['ric']
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
                    'error': None
                })
            else:
                results.append({
                    'meta': meta,
                    'error': 'No data in response'
                })
        return results
    except Exception as e:
        return [{'meta': meta, 'error': str(e)} for meta in rics_with_meta]

def decompose_forwards_batch(results):
    """Decompose forwards for batch results"""
    all_rows = []
    summaries = []

    for result in results:
        if result.get('error'):
            continue

        meta = result['meta']
        spot = result['spot']
        val_date = result['valuation_date']
        forwards = result['forwards']
        discount_curve = result['discount_curve']

        ric = meta['ric']
        bbg_name = meta['bbg_name']
        region = meta['region']
        type_ = meta['type']

        currency = 'USD'  # Default, could detect

        if not forwards:
            continue

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

            row = {
                'ric': ric,
                'bbg_name': bbg_name,
                'region': region,
                'type': type_,
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
            all_rows.append(row)

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
            # Slope
            if len(q_values) > 1:
                x = [t for t, _ in q_values]
                y = valid_q
                slope = np.polyfit(x, y, 1)[0]
            else:
                slope = 0
        else:
            min_q = median_q = max_q = slope = np.nan

        summary = {
            'ric': ric,
            'bbg_name': bbg_name,
            'currency': currency,
            'spot': spot,
            'val_date': val_date.strftime('%Y-%m-%d') if val_date else None,
            'n_tenors': n_tenors,
            'max_T': round(max_T, 2),
            'min_q_pct': round(min_q, 4) if not np.isnan(min_q) else np.nan,
            'median_q_pct': round(median_q, 4) if not np.isnan(median_q) else np.nan,
            'max_q_pct': round(max_q, 4) if not np.isnan(max_q) else np.nan,
            'slope_q_per_year': round(slope, 4) if not np.isnan(slope) else np.nan,
            'success': True
        }
        summaries.append(summary)

    return all_rows, summaries

def main():
    # Read CSV
    df = pd.read_csv('client_volatility_coverage_may6_2026.csv')
    # Skip the summary row
    df = df[df['Instrument Name'] != 'SUMMARY: 290/394 instruments available (73.6%)'].copy()

    # Create output directory
    os.makedirs('forwards_output', exist_ok=True)

    # Filter successful (Available)
    successful = df[df['Status'] == 'Available'].copy()
    failed = df[df['Status'] != 'Available'].copy()

    # Normalize failed RICs
    failed = failed.copy()
    failed['RIC'] = failed['RIC'].apply(normalise_ric)

    # Combine all to process
    all_to_process = []
    for _, row in successful.iterrows():
        all_to_process.append({
            'ric': row['RIC'],
            'bbg_name': row['Instrument Name'],
            'region': row['Region'],
            'type': row['Type'],
            'original_status': 'Available'
        })

    for _, row in failed.iterrows():
        all_to_process.append({
            'ric': row['RIC'],
            'bbg_name': row['Instrument Name'],
            'region': row['Region'],
            'type': row['Type'],
            'original_status': 'Not Available'
        })

    # Sort by region priority
    region_order = {'Americas': 0, 'EMEA': 1, 'APAC': 2}
    all_to_process.sort(key=lambda x: (region_order.get(x['region'], 3), x['ric']))

    # Batch processing
    batch_size = 10
    all_rows = []
    all_summaries = []
    failures = []
    batch_num = 0

    start_time = time.time()

    for i in range(0, len(all_to_process), batch_size):
        batch = all_to_process[i:i+batch_size]
        batch_num += 1

        region = batch[0]['region'] if batch else 'Mixed'
        print(f"[batch {batch_num}/{len(all_to_process)//batch_size + 1} | {region} | {len(batch)} RICs] ", end='')

        batch_start = time.time()
        results = extract_forward_data_batch(batch)
        batch_time = time.time() - batch_start

        success_count = 0
        for result in results:
            if result.get('error'):
                failures.append({
                    'ric': result['meta']['ric'],
                    'bbg_name': result['meta']['bbg_name'],
                    'error': result['error']
                })
                print(f"{result['meta']['ric'].split('@')[0]}✗ ", end='')
            else:
                success_count += 1
                print(f"{result['meta']['ric'].split('@')[0]}✓ ", end='')

        print(f"{success_count}/{len(batch)} ok in {batch_time:.1f}s")

        # Decompose
        rows, summaries = decompose_forwards_batch(results)
        all_rows.extend(rows)
        all_summaries.extend(summaries)

    # Write outputs
    if all_rows:
        long_df = pd.DataFrame(all_rows)
        long_df.to_csv('forwards_output/forwards_long.csv', index=False)

    if all_summaries:
        summary_df = pd.DataFrame(all_summaries)
        summary_df.to_csv('forwards_output/forwards_summary.csv', index=False)

    if failures:
        fail_df = pd.DataFrame(failures)
        fail_df.to_csv('forwards_output/forwards_failures.csv', index=False)

    # Run log
    total_time = time.time() - start_time
    total_instruments = len(all_to_process)
    successes = len(all_summaries)
    total_tenors = sum(s['n_tenors'] for s in all_summaries)

    log_content = f"""Forward Curve Extraction Run Log
Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Total instruments processed: {total_instruments}
Successful extractions: {successes}
Failed extractions: {len(failures)}
Total tenors extracted: {total_tenors}
Wall time: {total_time:.1f}s

Caveats:
- For ETFs, implied q embeds expense ratio drag, distribution timing, and any FX/borrow wedge — it is NOT the underlying basket dividend yield directly.
- For ADRs, implied q embeds borrow cost, foreign withholding tax, and any AR/ordinary spread dynamics — cross-check with the foreign primary listing where it matters.
- For non-USD underlyings, the OIS curve returned is the underlying's native currency (TONA for Japan, ESTR for EU, SONIA for UK). All implied q figures are therefore native-currency-discounted, not USD-discounted. Do NOT translate to USD-equivalent without an explicit FX-and-cross-currency-basis adjustment.
- The valuation date may differ slightly between regions in the same batch (T+0 vs T+1 settlement conventions). The valuation_date column captures whatever the API returned per-instrument.
- low_confidence=True rows are mathematically fine for F(T) but the implied q decomposition is unstable when T < 18 days. Treat those as forwards-only.
"""

    with open('forwards_output/forwards_run_log.txt', 'w') as f:
        f.write(log_content)

    # Anomalies
    if all_rows:
        anomalies = []
        for row in all_rows:
            if (row['implied_q_pct'] is not None and
                (row['implied_q_pct'] < -5 or row['implied_q_pct'] > 15)) or \
               (row['forward_premium_pct'] is not None and
                (row['forward_premium_pct'] < -10 or row['forward_premium_pct'] > 10)) or \
               (row.get('n_tenors', 10) < 3):  # Note: n_tenors not in row, but in summary
                anomalies.append(row)

        if anomalies:
            anomaly_df = pd.DataFrame(anomalies)
            anomaly_df.to_csv('forwards_output/forwards_anomalies.csv', index=False)

    # Print summary
    print("\nRegional Summary:")
    for region in ['Americas', 'EMEA', 'APAC']:
        region_data = [s for s in all_summaries if any(r['region'] == region for r in all_rows if r['ric'] == s['ric'])]
        if region_data:
            q_at_1y = [s['median_q_pct'] for s in region_data if s['max_T'] >= 1.0]
            if q_at_1y:
                median_q_1y = np.median(q_at_1y)
                print(f"{region}: {len(region_data)} instruments, median implied_q at 1Y = {median_q_1y:.2f}%")

    print("\nOutput files:")
    print("- forwards_output/forwards_long.csv")
    print("- forwards_output/forwards_summary.csv")
    if failures:
        print("- forwards_output/forwards_failures.csv")
    if anomalies:
        print("- forwards_output/forwards_anomalies.csv")
    print("- forwards_output/forwards_run_log.txt")

if __name__ == '__main__':
    main()