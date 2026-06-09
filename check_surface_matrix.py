import pandas as pd
import sys
from lseg_analytics.pricing.market_data import eq_volatility as ev
import eq_vol_surface_pull_universe as u

coverage = pd.read_csv('eq_vol_surface_universe_coverage.csv')
ok_codes = coverage[coverage['Status'] == 'OK']['InstrumentCode'].tolist()
for code in ok_codes:
    request = ev.EtiVolatilitySurfaceRequestItem(
        surface_layout=u.surface_layout,
        surface_parameters=u.params,
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=code),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
    )
    resp = ev.calculate(universe=[request])
    surface_df, spot = u.parse_surface_response(resp)
    date_axis = pd.api.types.is_datetime64_any_dtype(surface_df.index) or surface_df.index.inferred_type == 'datetime'
    strike_axis = pd.api.types.is_numeric_dtype(surface_df.columns)
    missing = int(surface_df.isna().sum().sum())
    complete = missing == 0
    print(
        f"{code}: shape={surface_df.shape}, date_axis={date_axis}, strike_axis={strike_axis}, "
        f"complete={complete}, missing={missing}, spot={spot}, "
        f"strike_range=[{surface_df.columns.min():.3f},{surface_df.columns.max():.3f}]"
    )
