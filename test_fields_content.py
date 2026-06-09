#!/usr/bin/env python3
"""Examine the forward curve and spot price data when fields parameter is used"""

import pandas as pd
import json
from datetime import datetime
from lseg_analytics.pricing.market_data import eq_volatility as ev

# Load ric_resolution.csv and pick the first resolved RIC
df = pd.read_csv('forwards_output/ric_resolution.csv')
resolved = df[df['status'] == 'RESOLVED'].head(1)

row = resolved.iloc[0]
ric = row['ric_resolved']

print(f"RIC: {ric}\n")

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

# Call with all fields
response = ev.calculate(universe=[request_item], fields="ForwardCurve,UnderlyingSpot,InterestRateCurve")
data = response.get('data', [])

if data and len(data) > 0:
    item = data[0]
    
    print("=" * 70)
    print("UNDERLYING SPOT")
    print("=" * 70)
    spot = item.get('underlyingSpot')
    print(f"Type: {type(spot)}")
    print(f"Value: {spot}")
    print()
    
    print("=" * 70)
    print("FORWARD CURVE")
    print("=" * 70)
    fwd_curve = item.get('forwardCurve')
    print(f"Type: {type(fwd_curve)}")
    if fwd_curve:
        if isinstance(fwd_curve, dict):
            print(f"Keys: {list(fwd_curve.keys())}")
            # Try to access structure
            for k, v in list(fwd_curve.items())[:3]:
                print(f"  {k}: {type(v)} = {v}")
        elif isinstance(fwd_curve, list):
            print(f"Length: {len(fwd_curve)}")
            if len(fwd_curve) > 0:
                print(f"First item type: {type(fwd_curve[0])}")
                print(f"First item: {fwd_curve[0]}")
        elif hasattr(fwd_curve, '__dict__'):
            attrs = vars(fwd_curve)
            print(f"Attributes: {list(attrs.keys())}")
            for k, v in list(attrs.items())[:3]:
                print(f"  {k}: {type(v)} = {v if not isinstance(v, list) or len(str(v)) < 100 else '...'}")
    print()
    
    print("=" * 70)
    print("INTEREST RATE CURVE")
    print("=" * 70)
    rate_curve = item.get('interestRateCurve')
    print(f"Type: {type(rate_curve)}")
    if rate_curve:
        if isinstance(rate_curve, dict):
            print(f"Keys: {list(rate_curve.keys())}")
            # Check for multiCurve
            if 'multiCurve' in rate_curve:
                multi = rate_curve['multiCurve']
                print(f"  multiCurve type: {type(multi)}")
                if isinstance(multi, dict):
                    print(f"  multiCurve keys: {list(multi.keys())}")
                    if 'OIS' in multi:
                        ois = multi['OIS']
                        print(f"    OIS type: {type(ois)}")
                        if isinstance(ois, dict):
                            print(f"    OIS keys: {list(ois.keys())}")
                        elif hasattr(ois, '__dict__'):
                            print(f"    OIS attributes: {list(vars(ois).keys())}")
        elif hasattr(rate_curve, '__dict__'):
            attrs = vars(rate_curve)
            print(f"Attributes: {list(attrs.keys())}")
    print()
    
    # Try to serialize to JSON to see structure
    print("=" * 70)
    print("FULL RESPONSE JSON DUMP")
    print("=" * 70)
    
    def to_dict(obj):
        if hasattr(obj, 'to_dict'):
            try:
                return obj.to_dict()
            except:
                pass
        if hasattr(obj, '__dict__'):
            return {k: to_dict(v) for k, v in vars(obj).items() if not k.startswith('_')}
        if isinstance(obj, dict):
            return {k: to_dict(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_dict(x) for x in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)
    
    item_dict = to_dict(item)
    
    # Write to file
    with open('debug_fields_response.json', 'w') as f:
        json.dump(item_dict, f, indent=2, default=str)
    print("Wrote full response to debug_fields_response.json")
    
    # Print first 2000 chars
    json_str = json.dumps(item_dict, indent=2, default=str)
    print(json_str[:2000])
