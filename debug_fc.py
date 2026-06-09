#!/usr/bin/env python3
import datetime as dt
import lseg_analytics.pricing.market_data.eq_volatility as ev
from pprint import pprint

FIELDS = ",".join([
    "Data", "UnderlyingSpot", "InterestRateCurve", "DiscountCurve",
    "ForwardCurve", "Dividends", "SurfaceInformation"
])

VAL_DATE = dt.datetime(2026, 5, 10)

def build_request(ric: str):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f"{ric.replace('@RIC','').replace('.','_')}_test",
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        surface_parameters=ev.EtiSurfaceParameters(
            calculation_date=VAL_DATE,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        ),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )

print("Pulling T@RIC...")
resp = ev.calculate(universe=[build_request('T@RIC')], fields=FIELDS)
item = resp['data'][0]

print(f"\n=== Item Structure ===")
print(f"Item type: {type(item).__name__}")

# List all attributes
attrs = [x for x in dir(item) if not x.startswith('_')]
print(f"Attributes: {attrs[:15]}")

# Try forward curve  
print(f"\n=== Forward Curve Access ===")
fc = getattr(item, 'forward_curve', None)
print(f"forward_curve attr exists: {fc is not None}")

if fc:
    print(f"forward_curve type: {type(fc).__name__}")
    print(f"forward_curve keys: {list(fc.keys())}")

# Access data points directly
dp = fc.get('dataPoints')
if dp:
    print(f"\n=== dataPoints Content ===")
    print(f"dataPoints type: {type(dp).__name__}")
    for i, (date_key, val) in enumerate(list(dp.items())[:3]):
        print(f"  {date_key}: {val} (type: {type(val).__name__})")

