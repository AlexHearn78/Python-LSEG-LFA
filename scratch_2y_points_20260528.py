import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load
from lseg_analytics.pricing._basic_client.models import _models

pricing = _models.InterestRateCurveCalculationParameters(valuation_date='2026-05-28')
CURVES = ['USD_SOFR_Swap_ZC_Curve', 'EUR_ESTR_Swap_ZC_Curve']

for name in CURVES:
    c = load(name=name)
    resp = c.calculate(pricing_preferences=pricing, fields='')
    zc = resp.analytics.zc_curves[0]
    pts = zc.points
    point = None
    for pt in pts:
        if hasattr(pt, 'tenor') and pt.tenor == '2Y':
            point = pt
            break
    if point is None:
        print(name, 'no 2Y point found')
        continue
    rate = point.rate.value if hasattr(point.rate, 'value') else point.rate['value']
    start_date = getattr(point, 'startDate', None) or getattr(point, 'start_date', None)
    end_date = getattr(point, 'endDate', None) or getattr(point, 'end_date', None)
    print(name, '2Y tenor', point.tenor, 'rate', rate, 'unit', point.rate.unit)
    print(' start_date', start_date, 'end_date', end_date)
