import datetime as dt
import pandas as pd

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    from lseg_analytics.core.exceptions import LSEGError
    REAL_EV = True
except Exception:
    REAL_EV = False

UNIVERSE_TEXT = """
ACWI US
iShares MSCI ACWI ETF
USD
US4642882579
ARKG US
ARK Genomic Revolution ETF
USD
US00214Q2073
ARKK US
ARK Innovation ETF
USD
US00214Q1040
COPX US
Global X Copper Miners ETF
USD
US37950E1082
DAXEX GR
iShares EUR DAX UCITS ETF (DE)
EUR
IE00B53SZB35
DBA US
Invesco DB Agriculture Fund
USD
US46138G8602
DIA US
SPDR Dow Jones Industrial Average ETF Trust
USD
US78468R1023
EEM US
iShares MSCI Emerging Markets ETF
USD
US4642872349
EWZ US
iShares MSCI Brazil ETF
USD
US4642871849
FDN US
First Trust Dow Jones Internet Index Fund
USD
US33734X1090
GLD US
SPDR Gold Shares
USD
US78463V1070
HYG US
iShares iBoxx $ High Yield Corporate Bond ETF
USD
US4642885135
IWM US
iShares Russell 2000 ETF
USD
US4642876555
QQQ US
Invesco QQQ Trust
USD
US46090E1038
SLV US
iShares Silver Trust
USD
US46434V1035
SPY US
SPDR S&P 500 ETF Trust
USD
US78462F1030
TLT US
iShares 20+ Year Treasury Bond ETF
USD
US4642874329
VWO US
iShares MSCI Emerging Markets ETF
USD
US4642872349
XLF US
Financial Select Sector SPDR Fund
USD
US81369Y6051
XOP US
SPDR S&P Oil & Gas Exploration & Production ETF
USD
US78463X4044
"""

EXCHANGE_SUFFIXES = {
    'US': ['.O@RIC', '.P@RIC', '.N@RIC'],
    'CA': ['.TO@RIC', '.CN@RIC'],
    'LN': ['.L@RIC'],
    'LON': ['.L@RIC'],
    'FR': ['.PA@RIC'],
    'DE': ['.DE@RIC'],
    'GR': ['.DE@RIC'],
    'NL': ['.AS@RIC'],
    'AS': ['.AS@RIC'],
    'CH': ['.SW@RIC'],
    'SE': ['.ST@RIC'],
    'HK': ['.HK@RIC'],
    'JP': ['.T@RIC'],
    'AU': ['.AX@RIC'],
    'KR': ['.KS@RIC'],
    'CN': ['.SS@RIC', '.SZ@RIC'],
    'NO': ['.OL@RIC'],
    'FI': ['.HE@RIC'],
    'BE': ['.BB@RIC'],
    'IT': ['.MI@RIC'],
    'ES': ['.SM@RIC'],
    'DK': ['.CO@RIC'],
    'IM': ['.IM@RIC'],
    'NA': ['.NA@RIC'],
    'SW': ['.SW@RIC'],
}

FALLBACK_SUFFIXES = [
    '.O@RIC', '.P@RIC', '.N@RIC', '.DE@RIC', '.L@RIC', '.PA@RIC', '.AS@RIC',
    '.HK@RIC', '.T@RIC', '.AX@RIC', '.SW@RIC', '.CO@RIC', '.KS@RIC', '.SS@RIC',
    '.SZ@RIC', '.TO@RIC', '.OL@RIC', '.ST@RIC', '.IM@RIC', '.NA@RIC'
]

params = ev.EtiSurfaceParameters(
    calculation_date=dt.datetime(2026, 4, 25),
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)

surface_layout = ev.SurfaceOutput(format=ev.FormatEnum.MATRIX)


def parse_universe(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) % 4 != 0:
        raise ValueError('Universe text must contain groups of 4 lines')
    return [
        {
            'name': lines[i],
            'long_name': lines[i + 1],
            'currency': lines[i + 2],
            'isin': lines[i + 3],
        }
        for i in range(0, len(lines), 4)
    ]


def candidate_rics(name, isin):
    parts = name.split()
    ticker = parts[0]
    exchange = parts[-1] if len(parts) > 1 else None
    candidates = []
    if isin:
        candidates.append(isin)
    if exchange and exchange in EXCHANGE_SUFFIXES:
        candidates.extend(f'{ticker}{suffix}' for suffix in EXCHANGE_SUFFIXES[exchange])
    candidates.append(f'{ticker}@RIC')
    for suffix in FALLBACK_SUFFIXES:
        candidate = f'{ticker}{suffix}'
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def build_request_item(instrument_code):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_layout=surface_layout,
        surface_parameters=params,
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=instrument_code),
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

    spot = float(item.underlying_spot) if item.underlying_spot is not None else 100.0
    return surface_df, spot


def get_surface_info(entry):
    candidates = candidate_rics(entry['name'], entry['isin'])
    last_error = ''
    for code in candidates:
        try:
            request_item = build_request_item(code)
            resp = ev.calculate(universe=[request_item])
            surface_df, spot = parse_surface_response(resp)
            strikes = surface_df.shape[1]
            expiries = surface_df.shape[0]
            exp_dates = pd.to_datetime(surface_df.index)
            if getattr(exp_dates, 'tz', None) is not None:
                exp_dates = exp_dates.tz_convert(None)
            calc_date = params.calculation_date
            if getattr(calc_date, 'tzinfo', None) is not None:
                calc_date = calc_date.astimezone(dt.timezone.utc).replace(tzinfo=None)
            min_exp_days = (exp_dates.min() - calc_date).days
            max_exp_days = (exp_dates.max() - calc_date).days
            min_strike = surface_df.columns.min() if len(surface_df.columns) else 0
            max_strike = surface_df.columns.max() if len(surface_df.columns) else 0
            return {
                'status': 'OK',
                'instrument_code': code,
                'strikes': strikes,
                'expiries': expiries,
                'min_exp': f'{min_exp_days}d',
                'max_exp': f'{max_exp_days}d',
                'min_strike': f'{min_strike / spot * 100:.1f}%',
                'max_strike': f'{max_strike / spot * 100:.1f}%',
                'notes': '',
            }
        except Exception as e:
            last_error = str(e)
    return {
        'status': 'FAIL',
        'instrument_code': candidates[0] if candidates else '',
        'strikes': '',
        'expiries': '',
        'min_exp': '',
        'max_exp': '',
        'min_strike': '',
        'max_strike': '',
        'notes': last_error,
    }


def main():
    universe = parse_universe(UNIVERSE_TEXT)
    results = []

    for entry in universe:
        print(f"Processing {entry['name']} / {entry['isin']}...")
        info = get_surface_info(entry)
        results.append({
            'Name': entry['name'],
            'ISIN': entry['isin'],
            'InstrumentCode': info['instrument_code'],
            'Status': info['status'],
            'Strikes': info['strikes'],
            'Expiries': info['expiries'],
            'Min Exp': info['min_exp'],
            'Max Exp': info['max_exp'],
            'Min Strike': info['min_strike'],
            'Max Strike': info['max_strike'],
            'Notes': info['notes'],
        })

    df = pd.DataFrame(results)
    df.to_csv('eq_vol_surface_universe_coverage.csv', index=False)
    print('Saved eq_vol_surface_universe_coverage.csv')
    print(df)


if __name__ == '__main__':
    main()
