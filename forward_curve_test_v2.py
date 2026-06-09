"""
Forward Curve Test — Using authenticated session from coverage script
Tests outputs with proper session context
"""

import json
import datetime as dt
import inspect
from lseg_analytics.pricing.market_data import eq_volatility as ev

print("="*80)
print("FORWARD CURVE TEST — Checking outputs/fields parameters")
print("="*80)

# First, let's explore all possible ways to request additional data

print("\n=== Checking fields parameter ===")
print("The calculate() function has a 'fields' parameter. Let's try that.\n")

# Build basic request
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
    surface_tag="AAPL_fields_test",
    underlying_definition=surface_definition,
    surface_parameters=surface_parameters,
    underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
    surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
)

# Try with different fields values
fields_options = [
    None,
    "Data",
    "Data,UnderlyingSpot",
    "Data,UnderlyingSpot,InterestRateCurve,ForwardCurve",
    "ForwardCurve",
    "*",
]

for fields_value in fields_options:
    try:
        print(f"\nTrying calculate(universe=[request], fields={repr(fields_value)})...")
        response = ev.calculate(universe=[request_item], fields=fields_value)
        
        data_item = response['data'][0]
        data_keys = list(data_item.keys()) if hasattr(data_item, 'keys') else [x for x in dir(data_item) if not x.startswith('_')]
        
        print(f"  ✓ Success! Response keys: {data_keys}")
        
        # Check for forward-related keys
        forward_keys = [k for k in data_keys if 'forward' in k.lower()]
        rate_keys = [k for k in data_keys if 'rate' in k.lower() or 'interest' in k.lower()]
        spot_keys = [k for k in data_keys if 'spot' in k.lower() or 'underlying' in k.lower()]
        
        if forward_keys:
            print(f"  → Found forward keys: {forward_keys}")
        if rate_keys:
            print(f"  → Found rate keys: {rate_keys}")
        if spot_keys:
            print(f"  → Found spot keys: {spot_keys}")
            
    except Exception as e:
        error_msg = str(e)[:100]
        print(f"  ✗ Failed: {error_msg}")

# Now check if outputs can be set via the request item's dictionary interface
print("\n=== Checking if EtiVolatilitySurfaceRequestItem is dict-like ===")
print(f"Is dict-like: {hasattr(request_item, 'keys')}")
print(f"Dir sample: {[x for x in dir(request_item) if not x.startswith('_')][:15]}")

# Try to add outputs as a dictionary key if it's dict-like
if hasattr(request_item, '__setitem__'):
    try:
        request_item['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve"]
        print("✓ Successfully set outputs via __setitem__")
        
        response = ev.calculate(universe=[request_item])
        data_keys = list(response['data'][0].keys())
        print(f"  Response keys: {data_keys}")
    except Exception as e:
        print(f"✗ __setitem__ failed: {e}")

# Check if request_item itself is accessible as a dict
print("\n=== Request item as dict ===")
try:
    req_dict = dict(request_item)
    print(f"Keys in request_item dict: {list(req_dict.keys())}")
    
    # Try adding outputs to the dict
    req_dict['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve"]
    print(f"Added outputs to dict. New keys: {list(req_dict.keys())}")
    
except Exception as e:
    print(f"Error: {e}")

# Try inspect to find all available init parameters
print("\n=== EtiVolatilitySurfaceRequestItem full inspection ===")
print(f"All attributes (sample): {[a for a in dir(request_item) if not a.startswith('_')]}")

# Check the class definition
print(f"\nClass __init__ docstring:")
print(ev.EtiVolatilitySurfaceRequestItem.__init__.__doc__)

print("\n" + "="*80)
print("FORWARD CURVE TEST COMPLETE")
print("="*80)
