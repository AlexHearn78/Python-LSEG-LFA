#!/usr/bin/env python3
"""Test different fields parameter values to request forward curve data"""

import pandas as pd
import json
from datetime import datetime
from lseg_analytics.pricing.market_data import eq_volatility as ev

# Load ric_resolution.csv and pick the first resolved RIC
df = pd.read_csv('forwards_output/ric_resolution.csv')
resolved = df[df['status'] == 'RESOLVED'].head(1)

row = resolved.iloc[0]
ric = row['ric_resolved']

print(f"Testing RIC: {ric}\n")

# Test 1: No fields parameter (current behavior)
print("=" * 60)
print("TEST 1: No fields parameter")
print("=" * 60)
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
data = response.get('data', [])
if data and len(data) > 0:
    keys = list(data[0].keys()) if hasattr(data[0], 'keys') else dir(data[0])
    print(f"Response keys: {keys}")
print()

# Test 2: fields parameter with various values
test_fields = [
    "ForwardCurve",
    "UnderlyingSpot",
    "InterestRateCurve", 
    "ForwardCurve,UnderlyingSpot,InterestRateCurve",
    "Data,ForwardCurve,UnderlyingSpot,InterestRateCurve",
]

for fields_value in test_fields:
    print("=" * 60)
    print(f"TEST: fields='{fields_value}'")
    print("=" * 60)
    try:
        response = ev.calculate(universe=[request_item], fields=fields_value)
        data = response.get('data', [])
        if data and len(data) > 0:
            item = data[0]
            print(f"Response type: {type(item)}")
            if hasattr(item, 'keys'):
                keys = list(item.keys())
                print(f"Response keys: {keys}")
            else:
                attrs = [x for x in dir(item) if not x.startswith('_')]
                print(f"Response attributes: {attrs[:20]}")
        else:
            print(f"No data returned")
    except Exception as e:
        print(f"Error: {e}")
    print()
