import datetime as dt
import lseg_analytics.pricing.market_data.eq_volatility as ev

def build_request(ric):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=ric.replace('@RIC',''),
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        surface_parameters=ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2026, 5, 10),
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

FIELDS = "Data,UnderlyingSpot,InterestRateCurve,DiscountCurve,ForwardCurve,Dividends,SurfaceInformation"
resp = ev.calculate(universe=[build_request('T@RIC')], fields=FIELDS)
item = resp['data'][0]

print(f"underlying_spot: {item.underlying_spot}")
print(f"type: {type(item.underlying_spot)}")

# Save to file
with open('debug_spot.txt', 'w') as f:
    f.write(f"underlying_spot: {item.underlying_spot}\n")
    f.write(f"type: {type(item.underlying_spot)}\n")
    
    if isinstance(item.underlying_spot, dict):
        f.write("Dict keys:\n")
        for k, v in item.underlying_spot.items():
            f.write(f"  {k}: {v} (type: {type(v).__name__})\n")
    elif isinstance(item.underlying_spot, list):
        f.write(f"List of length {len(item.underlying_spot)}\n")
        if item.underlying_spot:
            f.write(f"First element: {item.underlying_spot[0]}\n")
            f.write(f"Type: {type(item.underlying_spot[0]).__name__}\n")

print("Saved to debug_spot.txt")
