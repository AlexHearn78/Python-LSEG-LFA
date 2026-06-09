from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt
import pandas as pd
import json
import numpy as np
from dateutil import parser

def resolve_to_ric(identifier):
    """Resolve identifier to RIC"""
    # Simple mapping for known identifiers
    mappings = {
        'AAPL.O': 'AAPL.O@RIC',
        'MSFT.O': 'MSFT.O@RIC',
        'EWJ': 'EWJ@RIC',
        '.N225': '.N225@RIC',
        'VOD.L': 'VOD.L@RIC',
        '.SPX': '.SPX@RIC',
        'US78462F1030': 'SPY.O@RIC'  # SPY ISIN
    }

    if identifier in mappings:
        return mappings[identifier]

    # If it ends with @RIC, use as is
    if identifier.endswith('@RIC'):
        return identifier

    # Otherwise, assume it's already a RIC
    return f"{identifier}@RIC"

def interpolate_rate(discount_curve, T_years):
    """Linear interpolation of zero rate at T_years"""
    if not discount_curve:
        return 0.0

    # Sort by end_date
    sorted_curve = sorted(discount_curve, key=lambda x: x['endDate'])

    # Find bracketing points
    for i in range(len(sorted_curve) - 1):
        curr = sorted_curve[i]
        next_ = sorted_curve[i+1]

        curr_date = parser.parse(curr['endDate'])
        next_date = parser.parse(next_['endDate'])
        val_date = parser.parse(sorted_curve[0]['startDate'])

        curr_T = (curr_date - val_date).days / 365.0
        next_T = (next_date - val_date).days / 365.0

        if curr_T <= T_years <= next_T:
            # Linear interpolation in zero rate
            r1 = curr['ratePercent'] / 100.0
            r2 = next_['ratePercent'] / 100.0
            return r1 + (r2 - r1) * (T_years - curr_T) / (next_T - curr_T)

    # Extrapolate from last point
    last = sorted_curve[-1]
    last_date = parser.parse(last['endDate'])
    val_date = parser.parse(sorted_curve[0]['startDate'])
    last_T = (last_date - val_date).days / 365.0
    return last['ratePercent'] / 100.0

def extract_forward_data(ric):
    """Extract forward curve data for a RIC"""
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
            surface_tag=f"{ric}_forwards",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )

        response = ev.calculate(universe=[request_item])

        if 'data' not in response or not response['data']:
            return None, "No data in response"

        data_item = response['data'][0]

        # Extract components
        spot = data_item.get('underlyingSpot', 0)
        forward_curve = data_item.get('forwardCurve', {})
        interest_curve = data_item.get('interestRateCurve', {})

        # Get OIS curve
        ois_curve = interest_curve.get('multiCurve', {}).get('OIS', [])

        # Valuation date from first OIS point
        val_date = None
        if ois_curve:
            val_date = parser.parse(ois_curve[0]['startDate'])

        # Forward points
        forwards = []
        if 'dataPoints' in forward_curve:
            for date_str, fwd_price in forward_curve['dataPoints'].items():
                fwd_date = parser.parse(date_str)
                forwards.append((fwd_date, fwd_price))

        forwards.sort(key=lambda x: x[0])  # Sort by date

        return {
            'spot': spot,
            'valuation_date': val_date,
            'forwards': forwards,
            'discount_curve': ois_curve,
            'ric': ric
        }, None

    except Exception as e:
        return None, str(e)

def decompose_forwards(data):
    """Decompose forwards into implied dividend yields"""
    spot = data['spot']
    val_date = data['valuation_date']
    forwards = data['forwards']
    discount_curve = data['discount_curve']

    results = []

    for fwd_date, fwd_price in forwards:
        T_days = (fwd_date - val_date).days
        T_years = T_days / 365.0

        # Interpolate rate
        r = interpolate_rate(discount_curve, T_years)

        # Calculate implied q
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

        # Flag short tenors
        low_confidence = T_years < 0.05

        results.append({
            'expiry': fwd_date.strftime('%Y-%m-%d'),
            'T_years': round(T_years, 4),
            'F': round(fwd_price, 4),
            'spot': round(spot, 4),
            'F/S−1 %': round(fwd_premium_pct, 4),
            'r %': round(r * 100, 4),
            'implied_q %': round(q * 100, 4) if not np.isnan(q) else np.nan,
            'carry %': round(carry * 100, 4) if not np.isnan(carry) else np.nan,
            'flag': 'low_confidence' if low_confidence else ''
        })

    return results

def main():
    identifiers = ['AAPL.O', 'MSFT.O', 'EWJ', '.N225', 'VOD.L', '.SPX', 'US78462F1030']

    all_results = []
    failures = []
    summaries = []

    for ident in identifiers:
        ric = resolve_to_ric(ident)
        print(f"\nProcessing {ident} -> {ric}")

        data, error = extract_forward_data(ric)

        if error:
            print(f"FAILED: {error}")
            failures.append({'identifier': ident, 'ric': ric, 'error': error})
            continue

        # Decompose
        results = decompose_forwards(data)

        if not results:
            print("No forward data extracted")
            failures.append({'identifier': ident, 'ric': ric, 'error': 'No forward data'})
            continue

        # Create DataFrame
        df = pd.DataFrame(results)

        # Save per-identifier CSV
        csv_path = f"forwards_{ric.replace('@RIC', '').replace('.', '_')}.csv"
        df.to_csv(csv_path, index=False)

        # Summary
        n_tenors = len(results)
        max_T = max(r['T_years'] for r in results) if results else 0
        currency = 'USD'  # Default, could detect from RIC

        summary = {
            'ric': ric,
            'spot': data['spot'],
            'valuation_date': data['valuation_date'].strftime('%Y-%m-%d') if data['valuation_date'] else None,
            'n_tenors': n_tenors,
            'max_T': round(max_T, 2),
            'currency': currency,
            'notes': ''
        }

        summaries.append(summary)

        print(f"[{ric}] spot=${data['spot']:.2f}, val_date={summary['valuation_date']}, tenors={n_tenors}, range=0.00–{max_T:.2f} y, currency={currency}")

        # Add to combined
        df_combined = df.copy()
        df_combined['ric'] = ric
        all_results.append(df_combined)

    # Combined DataFrame
    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        combined_df.to_csv('forwards_combined.csv', index=False)

        print("
Combined table head:")
        print(combined_df.head().to_string(index=False))

        print(f"\nSaved forwards_combined.csv with {len(combined_df)} rows")

    # Save summaries and failures
    with open('forwards_summary.json', 'w') as f:
        json.dump(summaries, f, indent=2)

    if failures:
        with open('forwards_failures.json', 'w') as f:
            json.dump(failures, f, indent=2)
        print(f"\nFailures saved to forwards_failures.json: {len(failures)} failed")

if __name__ == '__main__':
    main()