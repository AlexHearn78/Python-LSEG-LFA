"""
Forward Curve Implementation — Production Code Pattern
Shows the correct way to request and parse forward curve data
"""

import datetime as dt
import json
import math
from lseg_analytics.pricing.market_data import eq_volatility as ev

def build_surface_request_with_forwards(ticker: str, calc_date: dt.datetime) -> ev.EtiVolatilitySurfaceRequestItem:
    """
    Build an equity vol surface request that includes forward curves, rates, and spot.
    
    Args:
        ticker: RIC code (e.g., 'AAPL.O@RIC')
        calc_date: Calculation date as datetime
    
    Returns:
        EtiVolatilitySurfaceRequestItem with outputs configured
    """
    surface_definition = ev.EtiSurfaceDefinition(instrument_code=ticker)
    surface_parameters = ev.EtiSurfaceParameters(
        calculation_date=calc_date,
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    
    request_item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f"{ticker.split('.')[0]}_forwards",
        underlying_definition=surface_definition,
        surface_parameters=surface_parameters,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    # KEY STEP: Add outputs via dict interface
    request_item['outputs'] = [
        "Data",                  # Surface volatility data
        "UnderlyingSpot",        # Current spot price
        "InterestRateCurve",     # Risk-free rate curve
        "ForwardCurve",          # Equity forward curve
        "SurfaceInformation"     # Surface metadata
    ]
    
    return request_item

def parse_surface_with_forwards(response_item: dict, spot: float, calc_date: dt.datetime):
    """
    Parse a vol surface response that includes forwards and rates.
    
    Args:
        response_item: Single item from response['data']
        spot: Underlying spot price
        calc_date: Calculation date
    
    Returns:
        Dictionary with surface, forwards, rates, and implied dividends
    """
    result = {
        'surface': response_item.get('surface'),
        'spot': response_item.get('underlyingSpot') or spot,
        'forwards': response_item.get('forwardCurve', []),
        'rates': response_item.get('interestRateCurve', []),
        'implied_dividends': []
    }
    
    # Compute implied dividend yields from forwards
    spot = result['spot']
    for fwd_point in result['forwards']:
        try:
            fwd_date = fwd_point.get('date') or fwd_point.get('maturityDate')
            fwd_value = fwd_point.get('value') or fwd_point.get('price')
            
            # Find corresponding rate
            ois_rate = None
            for rate_point in result['rates']:
                rate_date = rate_point.get('date') or rate_point.get('maturityDate')
                if rate_date == fwd_date:
                    ois_rate = rate_point.get('value') or rate_point.get('rate')
                    break
            
            # Compute T and implied dividend
            if fwd_date and fwd_value and ois_rate is not None:
                try:
                    fwd_dt = dt.datetime.fromisoformat(str(fwd_date).split('T')[0]) if isinstance(fwd_date, str) else fwd_date
                    T = (fwd_dt - calc_date).days / 365.25
                    
                    if T > 0 and spot > 0:
                        # Forward = Spot * exp((r - q) * T)
                        # => q = r - ln(F/S) / T
                        r_minus_q = math.log(float(fwd_value) / float(spot)) / T
                        implied_q = float(ois_rate) - r_minus_q
                        
                        result['implied_dividends'].append({
                            'date': fwd_date,
                            'tenor_years': round(T, 4),
                            'forward': float(fwd_value),
                            'ois_rate': float(ois_rate),
                            'implied_dividend_yield': implied_q
                        })
                except Exception as e:
                    pass
        except Exception as e:
            pass
    
    return result

def batch_request_with_forwards(tickers: list, calc_date: dt.datetime):
    """
    Create batch request for multiple underlyings with forward curves.
    
    Args:
        tickers: List of RIC codes
        calc_date: Calculation date
    
    Returns:
        List of configured request items ready for calculate()
    """
    requests = []
    for ticker in tickers:
        req = build_surface_request_with_forwards(ticker, calc_date)
        requests.append(req)
    return requests

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("FORWARD CURVE IMPLEMENTATION EXAMPLE")
    print("="*80)
    
    # Example 1: Single ticker request
    print("\n=== Example 1: Build request with forwards ===\n")
    request = build_surface_request_with_forwards("AAPL.O@RIC", dt.datetime(2025, 4, 18))
    print(f"Request outputs: {request.get('outputs')}")
    print(f"Request tag: {request.get('surface_tag')}")
    print(f"Request structure: {json.dumps(dict(request), indent=2, default=str)[:1000]}")
    
    # Example 2: Batch request
    print("\n\n=== Example 2: Batch request for multiple tickers ===\n")
    tickers = ["AAPL.O@RIC", "MSFT.O@RIC", "NVDA.O@RIC", "GOOGL.O@RIC"]
    requests = batch_request_with_forwards(tickers, dt.datetime(2025, 4, 18))
    print(f"Created {len(requests)} requests with forward curve outputs")
    
    # Example 3: Show structure of expected response
    print("\n\n=== Example 3: Expected response structure ===\n")
    expected_response = {
        'surface': [
            [None, '2025-05-16', '2025-06-20', '2025-07-18'],  # expiries
            ['98.49', 99.45, 79.03, 71.44],  # strike 1
            ['118.19', 85.99, 68.87, 62.57],  # strike 2
        ],
        'underlyingSpot': 181.23,
        'forwardCurve': [
            {'date': '2025-05-16', 'value': 181.65},
            {'date': '2025-06-20', 'value': 182.12},
            {'date': '2025-07-18', 'value': 182.89},
            {'date': '2026-04-18', 'value': 185.34},
        ],
        'interestRateCurve': [
            {'date': '2025-05-16', 'value': 0.0450},
            {'date': '2025-06-20', 'value': 0.0452},
            {'date': '2025-07-18', 'value': 0.0453},
            {'date': '2026-04-18', 'value': 0.0458},
        ]
    }
    
    parsed = parse_surface_with_forwards(expected_response, 181.23, dt.datetime(2025, 4, 18))
    
    print(f"Spot: ${parsed['spot']:.2f}")
    print(f"Forward points: {len(parsed['forwards'])}")
    print(f"Rate points: {len(parsed['rates'])}")
    print(f"Implied dividends computed: {len(parsed['implied_dividends'])}")
    
    print("\nImplied dividend yields:")
    for div in parsed['implied_dividends']:
        print(f"  {div['date']}: {div['implied_dividend_yield']*100:.2f}% (Forward: ${div['forward']:.2f}, OIS: {div['ois_rate']*100:.2f}%)")
    
    print("\n" + "="*80)
    print("IMPLEMENTATION COMPLETE")
    print("="*80)
    print("\nKey takeaway:")
    print("  request_item['outputs'] = ['Data', 'UnderlyingSpot', 'InterestRateCurve', 'ForwardCurve']")
    print("\nThis single line enables forward curve extraction for any equity vol surface request.")
