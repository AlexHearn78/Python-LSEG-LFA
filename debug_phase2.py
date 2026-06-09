#!/usr/bin/env python3
"""Debug Phase 2: Discover the correct path to forward curve data from API response."""

import pandas as pd
import json
from datetime import datetime
from lseg_analytics.pricing.market_data import eq_volatility as ev

# Step 1: Load ric_resolution.csv and pick the first resolved RIC
df = pd.read_csv('forwards_output/ric_resolution.csv')
resolved = df[df['status'] == 'RESOLVED'].head(1)

if resolved.empty:
    print("ERROR: No resolved RICs found!")
    exit(1)

row = resolved.iloc[0]
ric = row['ric_resolved']
bbg_name = row['bbg_name']

print(f"=== SELECTED RIC ===")
print(f"Name: {bbg_name}")
print(f"Resolved RIC: {ric}")
print()

# Step 2: Call the surface API using the same pattern as production code
print("=== CALLING SURFACE API ===")
try:
    surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
    surface_parameters = ev.EtiSurfaceParameters(
        calculation_date=datetime(2026, 5, 10),
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
    
    response = ev.calculate(universe=[request_item])
    print("API call succeeded")
except Exception as e:
    print(f"API call failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print()
print("=== EXPLORING response STRUCTURE ===")
print(f"Response type: {type(response)}")
print(f"Response is dict-like: {hasattr(response, 'get')}")
if hasattr(response, 'get') or isinstance(response, dict):
    print(f"Top keys: {list(response.keys()) if hasattr(response, 'keys') else 'N/A'}")
print()

# Step 3: Access the data and look for surface structure
print("=== EXPLORING response['data'] ===")

try:
    if hasattr(response, 'get'):
        data = response.get('data')
    elif isinstance(response, dict):
        data = response['data']
    else:
        data = None
    
    print(f"data type: {type(data)}")
    print(f"data value: {data}")
    print(f"data is None: {data is None}")
    if data is not None:
        print(f"data length: {len(data) if hasattr(data, '__len__') else 'N/A'}")
        print(f"data bool: {bool(data)}")
        
        if data and len(data) > 0:
            first_item = data[0]
            print(f"data[0] type: {type(first_item)}")
            print(f"data[0] value: {first_item}")
            
            if isinstance(first_item, dict):
                print(f"data[0] keys: {list(first_item.keys())}")
                
                if 'surface' in first_item:
                    surface = first_item['surface']
                    print(f"  surface type: {type(surface)}")
                    if isinstance(surface, dict):
                        print(f"  surface keys: {list(surface.keys())}")
                        
                        # Check for forward_curve
                        if 'forward_curve' in surface:
                            fwd = surface['forward_curve']
                            print(f"    forward_curve type: {type(fwd)}")
                            if hasattr(fwd, '__len__'):
                                print(f"    forward_curve length: {len(fwd)}")
                                if fwd and len(fwd) > 0:
                                    print(f"    first forward_curve item: {fwd[0]}")
                        else:
                            print(f"    forward_curve: NOT FOUND")
                        
                        # Check for spot_price
                        if 'spot_price' in surface:
                            print(f"    spot_price: {surface['spot_price']}")
                        else:
                            print(f"    spot_price: NOT FOUND")
                        
                        # Check for discount_curve
                        if 'discount_curve' in surface:
                            dc = surface['discount_curve']
                            print(f"    discount_curve type: {type(dc)}")
                            if hasattr(dc, '__len__'):
                                print(f"    discount_curve length: {len(dc)}")
                                if dc and len(dc) > 0:
                                    print(f"    first discount_curve item: {dc[0]}")
                        else:
                            print(f"    discount_curve: NOT FOUND")
                else:
                    print(f"  surface: NOT FOUND")
                    print(f"  Available keys in data[0]: {list(first_item.keys())}")
        else:
            print(f"data is empty or zero length")
    else:
        print(f"data is None - checking response attributes")
        if hasattr(response, '__dict__'):
            attrs = vars(response)
            print(f"response attributes: {list(attrs.keys())}")
            for k, v in attrs.items():
                if not k.startswith('_'):
                    print(f"  {k}: {type(v)} = {v if not isinstance(v, (list, dict)) or len(str(v)) < 100 else '...'}")

except Exception as e:
    print(f"Error exploring response: {e}")
    import traceback
    traceback.print_exc()



# Step 4: Dump full response to JSON
print("=== DUMPING FULL RESPONSE TO JSON ===")

def to_dict(obj):
    """Best-effort conversion of SDK response object to a JSON-serialisable dict."""
    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        try:
            return obj.to_dict()
        except:
            pass
    
    if hasattr(obj, '__dict__'):
        result = {}
        for k, v in vars(obj).items():
            if not k.startswith('_'):
                result[k] = to_dict(v)
        return result
    
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    # For datetime and other types
    return str(obj)

try:
    response_dict = to_dict(response)
    with open('debug_response.json', 'w') as f:
        json.dump(response_dict, f, indent=2, default=str)
    print("✓ Full response dumped to debug_response.json")
except Exception as e:
    print(f"✗ Failed to dump response: {e}")

print()
print("=== COMPLETE ===")
print("Next: Open debug_response.json and search for 'forwardCurve' or 'forward_curve'")
