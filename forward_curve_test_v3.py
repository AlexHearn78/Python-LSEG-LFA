"""
Forward Curve Test — Using outputs via dict interface
Constructs request with outputs field for forwards, rates, and spot
"""

import json
import datetime as dt
from lseg_analytics.pricing.market_data import eq_volatility as ev

print("="*80)
print("FORWARD CURVE TEST — Using outputs field")
print("="*80)

# Build the request normally first
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

# Convert to dict, add outputs, convert back
request_dict = dict(request_item)
print(f"\nOriginal request_dict keys: {list(request_dict.keys())}")

# Set outputs to request all available data types
request_dict['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]
print(f"After adding outputs: {list(request_dict.keys())}")
print(f"  outputs value: {request_dict['outputs']}")

# Print the full request structure
print(f"\n=== Full Request JSON (first 3000 chars) ===")
print(json.dumps(request_dict, indent=2, default=str)[:3000])

# Now try to execute with this augmented request
print(f"\n\nAttempting to execute calculate()...")
try:
    # Create a new request item from the dict
    request_with_outputs = ev.EtiVolatilitySurfaceRequestItem(**request_dict)
    
    response = ev.calculate(universe=[request_with_outputs])
    
    print("✓ Calculate succeeded!")
    
    # Examine response
    data_item = response['data'][0]
    data_keys = list(data_item.keys()) if hasattr(data_item, 'keys') else [x for x in dir(data_item) if not x.startswith('_')]
    
    print(f"\nResponse keys: {data_keys}")
    
    # Look for various output types
    print("\n=== Checking for various output types ===")
    
    # Surface (should always be there)
    if 'surface' in data_item:
        surface = data_item['surface']
        print(f"✓ 'surface': {type(surface)} with {len(surface)} rows" if isinstance(surface, list) else f"✓ 'surface': {type(surface)}")
    
    # Forward curve
    for key in ['forwardCurve', 'forward_curve', 'ForwardCurve', 'forwards']:
        if key in data_item:
            fwd = data_item[key]
            print(f"✓ '{key}': {type(fwd)}")
            if isinstance(fwd, (list, dict)):
                print(f"  Sample (first 1000 chars): {str(fwd)[:1000]}")
    
    # Interest rate curve
    for key in ['interestRateCurve', 'interest_rate_curve', 'InterestRateCurve', 'rates', 'riskFreeRateCurve']:
        if key in data_item:
            rates = data_item[key]
            print(f"✓ '{key}': {type(rates)}")
            if isinstance(rates, (list, dict)):
                print(f"  Sample (first 1000 chars): {str(rates)[:1000]}")
    
    # Spot price
    for key in ['underlyingSpot', 'underlying_spot', 'UnderlyingSpot', 'spot', 'underlyingPrice', 'currentPrice']:
        if key in data_item:
            spot = data_item[key]
            print(f"✓ '{key}': {spot}")
    
    # Print all keys found
    print(f"\nAll response keys: {data_keys}")
    
except Exception as e:
    print(f"✗ Calculate failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
