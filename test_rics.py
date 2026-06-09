import datetime as dt
import pandas as pd

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    from lseg_analytics.core.exceptions import LSEGError
    REAL_EV = True
except Exception:
    REAL_EV = False

CALC_DATE = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

SURFACE_PARAMS = ev.EtiSurfaceParameters(
    calculation_date=CALC_DATE,
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)
SURFACE_LAYOUT = ev.SurfaceOutput(format=ev.FormatEnum.MATRIX)

def build_surface_request(ric):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f'{ric}_test',
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        surface_parameters=SURFACE_PARAMS,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=SURFACE_LAYOUT,
    )

def test_ric(ric):
    try:
        request = build_surface_request(ric)
        response = ev.calculate(universe=[request])
        if response and response.data:
            item = response.data[0]
            if item.surface:
                return "OK", ""
            else:
                return "NO_SURFACE", "No surface data returned"
        else:
            return "NO_RESPONSE", "No response from API"
    except Exception as e:
        return "ERROR", str(e)

test_rics = [
    "SPY.P@RIC",   # SPY ETF, NYSE Arca
    "QQQ.O@RIC",   # QQQ ETF, NASDAQ
    "AAPL.O@RIC",  # Apple, NASDAQ
    "MSFT.O@RIC",  # Microsoft, NASDAQ
    ".SPX@RIC",    # S&P 500 index
]

results = []
for ric in test_rics:
    status, message = test_ric(ric)
    results.append({
        'ric': ric,
        'status': status,
        'message': message
    })

df = pd.DataFrame(results)
df.to_csv('test_rics_coverage.csv', index=False)
print("Test results saved to test_rics_coverage.csv")
print(df)