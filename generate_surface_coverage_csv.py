import pandas as pd
from lseg_analytics.pricing.market_data import eq_volatility as ev
import eq_vol_surface_pull_universe as u

coverage = pd.read_csv('eq_vol_surface_universe_coverage.csv')
ok = coverage[coverage['Status'] == 'OK'].copy()
rows = []
for _, row in ok.iterrows():
    code = row['InstrumentCode']
    request = ev.EtiVolatilitySurfaceRequestItem(
        surface_layout=u.surface_layout,
        surface_parameters=u.params,
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=code),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
    )
    resp = ev.calculate(universe=[request])
    surface_df, spot = u.parse_surface_response(resp)
    index_dates = pd.to_datetime(surface_df.index, errors='coerce')
    has_date_axis = not index_dates.isna().any()
    missing = int(surface_df.isna().sum().sum())
    min_rel = surface_df.columns.min() / spot * 100 if len(surface_df.columns) else None
    max_rel = surface_df.columns.max() / spot * 100 if len(surface_df.columns) else None
    rows.append({
        'Name': row['Name'],
        'ISIN': row['ISIN'],
        'InstrumentCode': code,
        'Expiries': surface_df.shape[0],
        'Strikes': surface_df.shape[1],
        'HasDateAxis': has_date_axis,
        'CompleteImpliedVolMatrix': missing == 0,
        'MissingCells': missing,
        'Spot': spot,
        'MinStrikePct': round(min_rel, 1) if min_rel is not None else None,
        'MaxStrikePct': round(max_rel, 1) if max_rel is not None else None,
        'FirstExpiry': str(surface_df.index[0]) if len(surface_df.index) else '',
        'LastExpiry': str(surface_df.index[-1]) if len(surface_df.index) else '',
    })
result = pd.DataFrame(rows)
outfile = 'eq_vol_surface_matrix_coverage.csv'
result.to_csv(outfile, index=False)
print('wrote', outfile)
print(result.to_string(index=False))
