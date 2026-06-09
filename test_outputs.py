from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt

# Test creating request item with outputs
surface_definition = ev.EtiSurfaceDefinition(instrument_code='EWJ.O@RIC')
surface_parameters = ev.EtiSurfaceParameters(
    calculation_date=dt.datetime(2026, 5, 2),
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)

try:
    request_item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag='test_outputs',
        underlying_definition=surface_definition,
        surface_parameters=surface_parameters,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    # KEY STEP: Add outputs via dict interface
    request_item['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]
    
    print('SUCCESS: outputs parameter accepted via dict interface')
except Exception as e:
    print(f'FAILED: {e}')