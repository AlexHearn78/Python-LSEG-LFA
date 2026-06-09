"""
Historical Basket Coverage Test — Stage 1

Tests point-in-time vol surfaces for 4 (date, ticker) combinations:
  - Dates: 2025-02-12 (early), 2026-04-22 (recent)
  - Tickers: AAPL US, NVDA US
  
Each request includes outputs enrichments:
  outputs=["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]
  
Logs: status, surface_ok, forward_curve_returned, spot, forward_curve_count, max_forward_date
"""

import sys
import json
import datetime as dt
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
except Exception as exc:
    raise RuntimeError(
        'Unable to import lseg_analytics. Live LSEG SDK access is required and no mocks may be used.'
    ) from exc

# ==============================================================================
# RIC MAPPING (reused from run_ivm_real_coverage.py)
# ==============================================================================

OVERRIDE_CSV = Path('ric_overrides.csv')

KNOWN_INDEX_RICS = {
    'SPX': '.SPX@RIC',
    'NDX': '.NDX@RIC',
    'RTY': '.RUT@RIC',
    'DAX': '.GDAXI@RIC',
    'CAC': '.FCHI@RIC',
    'UKX': '.FTSE@RIC',
    'SX5E': '.STOXX50E@RIC',
    'SXXP': '.STOXX@RIC',
    'NKY': '.N225@RIC',
    'TPX': '.TOPX@RIC',
    'HSI': '.HSI@RIC',
    'HSCEI': '.HSCE@RIC',
    'AS51': '.AXJO@RIC',
    'SMI': '.SSMI@RIC',
    'N225': '.N225@RIC',
    'IBEX': '.IBEX@RIC',
    'KOSPI': '.KS11@RIC',
    'NSEI': '.NSEI@RIC',
    'OMX': '.OMXS30@RIC',
    'STOXX50E': '.STOXX50E@RIC',
    'ESX5': '.STOXX50E@RIC',
    'EUROSTOXX': '.STOXX50E@RIC',
    'EUX': '.STOXX50E@RIC',
    'FTMIB': '.FTMIB@RIC',
    'CCMP': '.IXIC@RIC',
    'DJI': '.DJI@RIC',
    'JKSE': '.JKSE@RIC',
    'SSEC': '.SSEC@RIC',
}

SUFFIX_TO_RIC = {
    'US': ['.P@RIC', '@RIC', '.K@RIC', '.O@RIC', '.N@RIC'],
    'LN': ['.L@RIC'],
    'GB': ['.L@RIC'],
    'GR': ['.DE@RIC'],
    'DE': ['.DE@RIC'],
    'FP': ['.PA@RIC'],
    'FR': ['.PA@RIC'],
    'NA': ['.AS@RIC'],
    'NL': ['.AS@RIC'],
    'SM': ['.MC@RIC'],
    'IM': ['.MI@RIC'],
    'IT': ['.MI@RIC'],
    'SW': ['.S@RIC'],
    'CH': ['.SW@RIC'],
    'HK': ['.HK@RIC'],
    'JP': ['.T@RIC'],
    'AU': ['.AX@RIC'],
    'CN': ['.SS@RIC', '.SZ@RIC'],
    'CA': ['.TO@RIC', '.CN@RIC'],
    'ES': ['.MC@RIC'],
    'KR': ['.KS@RIC'],
    'IN': ['.NS@RIC'],
    'ID': ['.JK@RIC'],
    'PL': ['.WA@RIC'],
    'SE': ['.ST@RIC'],
    'NO': ['.OL@RIC'],
    'DK': ['.CO@RIC'],
    'FI': ['.HE@RIC'],
}

def load_overrides(path):
    if not path.exists():
        return {}
    overrides = {}
    with open(path, 'r', encoding='utf-8') as f:
        header = f.readline().strip().split(',', 2)
        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip('\n').split(',', 2)
            if len(parts) < 2:
                continue
            key = parts[0].strip()
            override_ric = parts[1].strip()
            if key and override_ric:
                overrides[key] = override_ric
    return overrides

def parse_bbg_name(name: str):
    name = str(name).strip()
    parts = name.split()
    if len(parts) <= 1:
        return name, None
    return ' '.join(parts[:-1]), parts[-1]

def build_ric_candidates(name, description=''):
    ticker, suffix = parse_bbg_name(name)
    ticker = ticker.strip()
    if not ticker:
        return []

    overrides = load_overrides(OVERRIDE_CSV)
    key = ticker if suffix is None else f'{ticker} {suffix}'
    key = key.strip()
    if key in overrides:
        override = overrides[key]
        return [override]

    # strip existing dot-suffix tickers before applying exchange suffix rules
    if '.' in ticker and not ticker.startswith('.'):
        return [ticker + '@RIC']

    # Check for known index using the base ticker name
    index_ticker = ticker.split('.')[0].upper()
    if index_ticker in KNOWN_INDEX_RICS:
        return [KNOWN_INDEX_RICS[index_ticker]]

    if suffix is None or suffix == '':
        return []

    suffix = suffix.upper()
    candidates = []
    if suffix in SUFFIX_TO_RIC:
        suffix_tokens = SUFFIX_TO_RIC[suffix]
        candidates.extend(f'{ticker}{suffix_token}' for suffix_token in suffix_tokens)
    if not candidates:
        candidates.append(f'{ticker}@RIC')
    return candidates

# ==============================================================================
# LOAD BASKET DATA
# ==============================================================================

def load_basket_csv(path):
    """
    Load basket_stocks_by_date.csv
    - Row 0: dates in DD-Mon-YY format
    - Rows 1+: Bloomberg tickers (e.g., 'AAPL US')
    - Cell (i, j) = ticker on date j (NaN if not traded)
    """
    df = pd.read_csv(path)
    
    # First row is the header (dates in DD-Mon-YY format)
    dates = []
    for col in df.columns:
        try:
            date = pd.to_datetime(col, format='%d-%b-%y')
            dates.append(date)
        except:
            dates.append(None)
    
    return df, dates

def get_tickers_on_date(df, dates, target_date: dt.datetime) -> List[str]:
    """
    Returns list of tickers (Bloomberg style, e.g., 'AAPL US') on target_date.
    target_date is a datetime object; find matching column.
    """
    # Find the column matching target_date
    col_index = None
    for i, date in enumerate(dates):
        if date and date.date() == target_date.date():
            col_index = i
            break
    
    if col_index is None:
        return []
    
    col_name = df.columns[col_index]
    tickers = []
    for row_idx in range(len(df)):
        ticker_val = df.iloc[row_idx, col_index]
        if pd.notna(ticker_val):
            ticker_str = str(ticker_val).strip()
            if ticker_str and ticker_str.upper() not in ['NAN', 'NONE']:
                tickers.append(ticker_str)
    return tickers

# ==============================================================================
# API CALLS
# ==============================================================================

def build_surface_request(ric, calculation_date: dt.datetime):
    """Build a vol surface request for the given RIC and date."""
    surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
    surface_parameters = ev.EtiSurfaceParameters(
        calculation_date=calculation_date,
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    
    request_item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f'{ric}_{calculation_date.strftime("%Y%m%d")}',
        underlying_definition=surface_definition,
        surface_parameters=surface_parameters,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    # Set outputs via dict interface
    request_item['outputs'] = [
        "Data",
        "UnderlyingSpot",
        "InterestRateCurve",
        "ForwardCurve",
        "SurfaceInformation"
    ]
    
    return request_item

def test_pair(date: dt.datetime, bbg_ticker: str, test_num: int) -> Dict[str, Any]:
    """
    Test a single (date, ticker) pair.
    
    Returns dict with:
      - status: 'OK' or error code
      - surface_ok: bool
      - forward_curve_returned: bool
      - spot: float or None
      - forward_curve_count: int (number of forward curve data points)
      - max_forward_date: str (YYYY-MM-DD) or None
      - error_message: str or None
    """
    result = {
        'test_num': test_num,
        'date': date.strftime('%Y-%m-%d'),
        'bbg_ticker': bbg_ticker,
        'status': None,
        'surface_ok': False,
        'forward_curve_returned': False,
        'spot': None,
        'forward_curve_count': 0,
        'max_forward_date': None,
        'error_message': None,
    }
    
    # Build RIC candidates
    ric_candidates = build_ric_candidates(bbg_ticker)
    if not ric_candidates:
        result['status'] = 'NO_RIC_CANDIDATES'
        result['error_message'] = f'Could not generate RIC candidates from {bbg_ticker}'
        return result
    
    # Try each candidate
    for ric in ric_candidates:
        try:
            request_item = build_surface_request(ric, date)
            response = ev.calculate(universe=[request_item])
            
            if not response or 'data' not in response or not response['data']:
                result['status'] = 'NO_RESPONSE'
                result['error_message'] = 'Empty response from API'
                continue
            
            data_item = response['data'][0]
            
            # Check for surface
            if 'surface' not in data_item or data_item['surface'] is None:
                result['status'] = 'NO_SURFACE'
                result['error_message'] = 'No surface in response'
                continue
            
            result['surface_ok'] = True
            
            # Extract spot
            if 'underlying_spot' in data_item and data_item['underlying_spot'] is not None:
                result['spot'] = float(data_item['underlying_spot'])
            
            # Extract forward curve
            forward_curve = None
            for key in ['forwardCurve', 'forward_curve', 'ForwardCurve']:
                if key in data_item:
                    forward_curve = data_item[key]
                    break
            
            if forward_curve:
                result['forward_curve_returned'] = True
                
                # Count data points and find max date
                if isinstance(forward_curve, list):
                    result['forward_curve_count'] = len(forward_curve)
                    if forward_curve:
                        max_date = None
                        for point in forward_curve:
                            if isinstance(point, dict) and 'date' in point:
                                point_date = point['date']
                                if max_date is None or point_date > max_date:
                                    max_date = point_date
                        result['max_forward_date'] = max_date
                elif isinstance(forward_curve, dict):
                    result['forward_curve_count'] = len(forward_curve)
                    if forward_curve:
                        max_date = max(forward_curve.keys())
                        result['max_forward_date'] = max_date
            
            result['status'] = 'OK'
            return result
        
        except Exception as e:
            error_msg = str(e)
            if 'BAD RIC' in error_msg or 'bad ric' in error_msg or 'not found' in error_msg:
                result['error_message'] = error_msg
                continue
            else:
                result['status'] = 'ERROR'
                result['error_message'] = error_msg
                return result
    
    # Exhausted all RIC candidates
    if result['status'] is None:
        result['status'] = 'BAD_RIC'
        result['error_message'] = f'All RIC candidates failed: {ric_candidates}'
    
    return result

# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 80)
    print("HISTORICAL BASKET COVERAGE TEST — STAGE 1")
    print("=" * 80)
    print()
    
    # Load basket data
    print("Loading basket_stocks_by_date.csv...")
    basket_path = Path('/Users/alexanderhearn/Downloads/basket_stocks_by_date.csv')
    if not basket_path.exists():
        print(f"ERROR: {basket_path} not found")
        sys.exit(1)
    
    df, dates = load_basket_csv(basket_path)
    print(f"  Loaded {len(df)} tickers across {len(dates)} dates")
    print(f"  Date range: {dates[0].date()} to {dates[-1].date()}")
    print()
    
    # Test dates
    test_dates = [
        dt.datetime(2025, 2, 12),  # Early
        dt.datetime(2026, 4, 22),  # Recent
    ]
    
    # Verify dates exist in basket
    for test_date in test_dates:
        tickers_on_date = get_tickers_on_date(df, dates, test_date)
        print(f"Date {test_date.date()}: {len(tickers_on_date)} tickers")
        
        # Check if AAPL US and NVDA US are there
        if 'AAPL US' in tickers_on_date:
            print(f"  ✓ AAPL US found")
        else:
            print(f"  ✗ AAPL US NOT found")
        
        if 'NVDA US' in tickers_on_date:
            print(f"  ✓ NVDA US found")
        else:
            print(f"  ✗ NVDA US NOT found")
    print()
    
    # Run 4 tests
    print("=" * 80)
    print("STAGE 1: Running 4 test calls")
    print("=" * 80)
    print()
    
    test_pairs = [
        (dt.datetime(2025, 2, 12), 'AAPL US'),
        (dt.datetime(2025, 2, 12), 'NVDA US'),
        (dt.datetime(2026, 4, 22), 'AAPL US'),
        (dt.datetime(2026, 4, 22), 'NVDA US'),
    ]
    
    results = []
    for i, (date, ticker) in enumerate(test_pairs, 1):
        print(f"Test {i}/4: {date.date()} × {ticker}")
        result = test_pair(date, ticker, i)
        results.append(result)
        
        # Print result inline
        status = result['status']
        surface_ok = '✓' if result['surface_ok'] else '✗'
        fwd_ok = '✓' if result['forward_curve_returned'] else '✗'
        spot = f"{result['spot']:.2f}" if result['spot'] is not None else 'None'
        fwd_count = result['forward_curve_count']
        max_date = result['max_forward_date'] or 'None'
        
        print(f"  Status: {status}, Surface: {surface_ok}, ForwardCurve: {fwd_ok}")
        print(f"  Spot: {spot}, ForwardCurve points: {fwd_count}, Max date: {max_date}")
        if result['error_message']:
            print(f"  Error: {result['error_message']}")
        print()
    
    # Summary
    print("=" * 80)
    print("STAGE 1 SUMMARY")
    print("=" * 80)
    
    ok_count = sum(1 for r in results if r['status'] == 'OK')
    forward_count = sum(1 for r in results if r['forward_curve_returned'])
    
    print(f"Tests passed: {ok_count}/4")
    print(f"Forward curves returned: {forward_count}/4")
    
    # Decision
    if ok_count == 4 and forward_count == 4:
        print("\n✓ STAGE 1 PASSED — All 4 calls successful with forward curves")
        print("  Ready to proceed to Stage 2 (100 random pairs)")
    else:
        print("\n✗ STAGE 1 FAILED")
        if ok_count < 4:
            print(f"  - Only {ok_count}/4 calls returned surfaces")
        if forward_count < 4:
            print(f"  - Only {forward_count}/4 calls returned forward curves")
        print("  Halting. Diagnose before proceeding.")
        sys.exit(1)
    
    # Save results to JSON for inspection
    results_json = Path('historical_basket_stage1_results.json')
    with open(results_json, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nDetailed results saved to {results_json}")

if __name__ == '__main__':
    main()
