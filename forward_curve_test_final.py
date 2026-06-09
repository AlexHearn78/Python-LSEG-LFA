"""
Forward Curve Test — Direct approach with outputs
Sets outputs on the request_item directly via dict interface
"""

import json
import datetime as dt
from lseg_analytics.pricing.market_data import eq_volatility as ev

print("="*80)
print("FORWARD CURVE TEST — Direct outputs approach")
print("="*80)

# Build the request normally
surface_definition = ev.EtiSurfaceDefinition(instrument_code="AAPL.O@RIC")
surface_parameters = ev.EtiSurfaceParameters(
    calculation_date=dt.datetime(2025, 4, 18),
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)

request_item = ev.EtiVolatilitySurfaceRequestItem(
    surface_tag="AAPL_with_forwards",
    underlying_definition=surface_definition,
    surface_parameters=surface_parameters,
    underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
    surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
)

print("Original request_item keys:", list(request_item.keys()))

# Set outputs via dict interface
request_item['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]

print("After setting outputs:", list(request_item.keys()))
print(f"outputs value: {request_item['outputs']}")

# Print request structure
print(f"\n=== Request structure (as JSON) ===")
req_json = json.dumps(dict(request_item), indent=2, default=str)
print(req_json[:2000])

print(f"\n\nAttempting calculate() with outputs...")
try:
    response = ev.calculate(universe=[request_item])
    
    print("✓ Calculate SUCCEEDED!")
    
    # Examine response
    data_item = response['data'][0]
    data_keys = list(data_item.keys()) if hasattr(data_item, 'keys') else [x for x in dir(data_item) if not x.startswith('_')]
    
    print(f"\n=== Response keys ===")
    print(data_keys)
    
    # Look for various output types
    print("\n=== Checking for output types ===")
    
    # Surface (should always be there)
    if 'surface' in data_item:
        surface = data_item['surface']
        if isinstance(surface, list) and len(surface) > 0:
            print(f"✓ 'surface': list with {len(surface)} rows and {len(surface[0]) if surface[0] else 0} cols")
        else:
            print(f"✓ 'surface': {type(surface)}")
    
    # Forward curve - try all possible naming conventions
    forward_found = False
    for key in ['forwardCurve', 'forward_curve', 'ForwardCurve', 'forwards', 'forward']:
        if key in data_item:
            forward_found = True
            fwd = data_item[key]
            print(f"\n✓ FOUND FORWARD CURVE (key: '{key}')")
            print(f"  Type: {type(fwd)}")
            if isinstance(fwd, dict):
                print(f"  Keys: {list(fwd.keys())[:10]}")
                print(f"  Sample: {json.dumps(fwd, default=str)[:1000]}")
            elif isinstance(fwd, list):
                print(f"  Length: {len(fwd)}")
                if fwd and isinstance(fwd[0], dict):
                    print(f"  First item keys: {list(fwd[0].keys())}")
                    print(f"  First item: {json.dumps(fwd[0], default=str)}")
            break
    
    if not forward_found:
        print("✗ No forward curve found")
    
    # Interest rate curve
    rate_found = False
    for key in ['interestRateCurve', 'interest_rate_curve', 'InterestRateCurve', 'rates', 'riskFreeRateCurve']:
        if key in data_item:
            rate_found = True
            rates = data_item[key]
            print(f"\n✓ FOUND INTEREST RATE CURVE (key: '{key}')")
            print(f"  Type: {type(rates)}")
            if isinstance(rates, dict):
                print(f"  Keys: {list(rates.keys())[:10]}")
            elif isinstance(rates, list):
                print(f"  Length: {len(rates)}")
                if rates and isinstance(rates[0], dict):
                    print(f"  First item keys: {list(rates[0].keys())}")
                    print(f"  First item: {json.dumps(rates[0], default=str)[:500]}")
            break
    
    if not rate_found:
        print("✗ No interest rate curve found")
    
    # Spot price
    spot_found = False
    for key in ['underlyingSpot', 'underlying_spot', 'UnderlyingSpot', 'spot', 'underlyingPrice', 'currentPrice']:
        if key in data_item:
            spot_found = True
            spot = data_item[key]
            print(f"\n✓ FOUND SPOT (key: '{key}'): {spot}")
            break
    
    if not spot_found:
        print("✗ No spot price found")
    
    # Print full response structure for inspection
    print(f"\n=== Full response structure (first 5000 chars) ===")
    print(json.dumps(data_item, indent=2, default=str)[:5000])
    
except Exception as e:
    error_msg = str(e)
    if "not logged in" in error_msg:
        print(f"✗ Authentication error: {error_msg[:200]}")
        print("\nNote: The SDK structure accepts outputs, but authentication is needed for live execution.")
        print("The 'outputs' field is properly structured in the request as shown above.")
    else:
        print(f"✗ Error: {error_msg}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
