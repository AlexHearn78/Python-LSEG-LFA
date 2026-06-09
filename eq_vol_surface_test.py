import datetime as dt
import pandas as pd

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    from lseg_analytics.core.exceptions import LSEGError
    REAL_EV = True
except Exception:
    REAL_EV = False

    class MockEV:
        class EtiSurfaceParameters:
            def __init__(self, **kwargs):
                self.calculation_date = kwargs.get('calculation_date')

        class CurvesAndSurfacesTimeStampEnum:
            DEFAULT = 'DEFAULT'

        class InputVolatilityTypeEnum:
            IMPLIED = 'IMPLIED'

        class CurvesAndSurfacesVolatilityModelEnum:
            SSVI = 'SSVI'

        class MoneynessTypeEnum:
            SPOT = 'SPOT'

        class CurvesAndSurfacesPriceSideEnum:
            MID = 'MID'

        class XAxisEnum:
            STRIKE = 'STRIKE'

        class YAxisEnum:
            DATE = 'DATE'

        class SurfaceOutput:
            def __init__(self, **kwargs):
                pass

        class FormatEnum:
            MATRIX = 'MATRIX'

        @staticmethod
        def calculate(universe, eti_surface_parameters, surface_layout):
            # Mock response
            result = {}
            for ric in universe:
                if 'FAIL' in ric:
                    raise Exception('Mock failure')
                dates = pd.date_range(start=eti_surface_parameters.calculation_date + dt.timedelta(days=30), periods=12, freq='ME')
                strikes = [80, 90, 100, 110, 120]
                surface = pd.DataFrame(index=dates, columns=strikes)
                surface = surface.fillna(0.2)
                result[ric] = {'surface': surface, 'spot': 100}
            return result

    ev = MockEV()

# Test universe
universe = {
    'US': [
        'AAPL.O@RIC', 'MSFT.O@RIC', 'NVDA.O@RIC', 'TSLA.O@RIC', 'AMZN.O@RIC',
        'META.O@RIC', 'GOOGL.O@RIC', 'JPM.N@RIC', 'XOM.N@RIC', 'SPY.P@RIC'
    ],
    'EU': [
        'SHEL.L@RIC', 'AZN.L@RIC', 'HSBA.L@RIC',  # UK
        'SAPG.DE@RIC', 'SIEGn.DE@RIC',  # Germany
        'LVMH.PA@RIC', 'MC.PA@RIC',  # France
        'ASML.AS@RIC',  # Netherlands
        'NOVOb.CO@RIC',  # Denmark
        'NESN.S@RIC'  # Switzerland
    ],
    'APAC': [
        '7203.T@RIC', '6758.T@RIC', '9984.T@RIC',  # Japan
        '0700.HK@RIC', '0941.HK@RIC', '9988.HK@RIC',  # HK
        'BHP.AX@RIC', 'CBA.AX@RIC',  # Australia
        '005930.KS@RIC', '000660.KS@RIC'  # Korea
    ]
}

print("RIC Universe:")
for region, rics in universe.items():
    print(f"{region}: {rics}")

# Test parameters
params = ev.EtiSurfaceParameters(
    calculation_date=dt.datetime(2025, 4, 25),  # recent settled date
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)

surface_layout = ev.SurfaceOutput(format=ev.FormatEnum.MATRIX)

if REAL_EV:
    def build_request_item(ric):
        return ev.EtiVolatilitySurfaceRequestItem(
            surface_layout=surface_layout,
            surface_parameters=params,
            underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        )

    def parse_surface_response(resp):
        if not resp or not getattr(resp, 'data', None):
            raise ValueError('No response data returned')
        item = resp.data[0]
        if item.surface is None:
            raise ValueError('No surface returned')

    surface = item.surface
    headers = item.headers
    expiry_dates = item.expiry_dates

    if headers is None or expiry_dates is None:
        if not isinstance(surface, list) or not surface or not isinstance(surface[0], list):
            raise ValueError('Unable to parse surface matrix')
        expiry_dates = surface[0][1:]
        strikes = [float(row[0]) for row in surface[1:] if row and len(row) > 1]
        data = [row[1:] for row in surface[1:] if row and len(row) > 1]
        surface_df = pd.DataFrame(data, index=strikes, columns=expiry_dates).T
    else:
        surface_df = pd.DataFrame(surface, index=expiry_dates, columns=headers)

            resp = ev.calculate(universe=[request_item])
            surface_df, spot = parse_surface_response(resp)
            strikes = surface_df.shape[1]
            expiries = surface_df.shape[0]
            exp_dates = pd.to_datetime(surface_df.index)
            if getattr(exp_dates, 'tz', None) is not None:
                exp_dates = exp_dates.tz_convert(None)
            min_exp_days = (exp_dates.min() - params.calculation_date).days
            max_exp_days = (exp_dates.max() - params.calculation_date).days
            min_strike = surface_df.columns.min() if len(surface_df.columns) else 0
            max_strike = surface_df.columns.max() if len(surface_df.columns) else 0
            return {
                'status': 'OK',
                'strikes': strikes,
                'expiries': expiries,
                'min_exp': f'{min_exp_days}d',
                'max_exp': f'{max_exp_days}d',
                'min_strike': f'{min_strike / spot * 100:.1f}%','max_strike': f'{max_strike / spot * 100:.1f}%',
                'notes': ''
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'strikes': '',
                'expiries': '',
                'min_exp': '',
                'max_exp': '',
                'min_strike': '',
                'max_strike': '',
                'notes': str(e)
            }
else:
    def get_surface_info(ric):
        try:
            result = ev.calculate(
                universe=[ric],
                eti_surface_parameters=params,
                surface_layout=surface_layout
            )
            if ric not in result:
                raise ValueError(f"No data for {ric}")
            data = result[ric]
            surface = data['surface']  # Assume DataFrame
            strikes = surface.shape[1]
            expiries = surface.shape[0]
            exp_dates = pd.to_datetime(surface.index)
            min_exp_days = (exp_dates.min() - params.calculation_date).days
            max_exp_days = (exp_dates.max() - params.calculation_date).days
            min_strike = surface.columns.min()
            max_strike = surface.columns.max()
            spot = data.get('spot', 100)  # Placeholder
            min_strike_pct = min_strike / spot * 100
            max_strike_pct = max_strike / spot * 100
            return {
                'status': 'OK',
                'strikes': strikes,
                'expiries': expiries,
                'min_exp': f"{min_exp_days}d",
                'max_exp': f"{max_exp_days}d",
                'min_strike': f"{min_strike_pct:.1f}%",
                'max_strike': f"{max_strike_pct:.1f}%",
                'notes': ''
            }
        except Exception as e:
            return {
                'status': 'FAIL',
                'strikes': '',
                'expiries': '',
                'min_exp': '',
                'max_exp': '',
                'min_strike': '',
                'max_strike': '',
                'notes': str(e)
            }

# Collect results
results = []
for region, rics in universe.items():
    for ric in rics:
        print(f"Processing {ric}...")
        info = get_surface_info(ric)
        results.append({
            'RIC': ric,
            'Region': region,
            'Status': info['status'],
            'Strikes': info['strikes'],
            'Expiries': info['expiries'],
            'Min Exp': info['min_exp'],
            'Max Exp': info['max_exp'],
            'Notes': info['notes']
        })

# Save to CSV
import csv
with open('eq_vol_surface_coverage.csv', 'w', newline='') as csvfile:
    fieldnames = ['RIC', 'Region', 'Status', 'Strikes', 'Expiries', 'Min Exp', 'Max Exp', 'Notes']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for res in results:
        writer.writerow(res)

print("Results saved to eq_vol_surface_coverage.csv")

# Print table
print(f"\n{'RIC':<15} {'Region':<8} {'Status':<8} {'Strikes':<8} {'Expiries':<9} {'Min Exp':<8} {'Max Exp':<8} {'Notes'}")
print("-" * 80)
for res in results:
    print(f"{res['RIC']:<15} {res['Region']:<8} {res['Status']:<8} {res['Strikes']:<8} {res['Expiries']:<9} {res['Min Exp']:<8} {res['Max Exp']:<8} {res['Notes']}")

# Summary stats
us_success = sum(1 for r in results if r['Region'] == 'US' and r['Status'] == 'OK')
eu_success = sum(1 for r in results if r['Region'] == 'EU' and r['Status'] == 'OK')
apac_success = sum(1 for r in results if r['Region'] == 'APAC' and r['Status'] == 'OK')

print(f"\nUS success rate: {us_success}/10")
print(f"EU success rate: {eu_success}/10")
print(f"APAC success rate: {apac_success}/10")