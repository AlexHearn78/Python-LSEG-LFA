import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load

CURVES = ['USD_SOFR_Swap_ZC_Curve', 'EUR_ESTR_Swap_ZC_Curve']

def get_2y(rate_curve):
    points = rate_curve.analytics.zc_curves[0].points
    target = None
    for pt in points:
        if hasattr(pt, 'tenor') and pt.tenor == '2Y':
            target = pt
            break
        if hasattr(pt, 'tenor') and pt.tenor == '24M':
            target = pt
    if target is None:
        for pt in points:
            if hasattr(pt, 'tenor') and pt.tenor == '2.0':
                target = pt
                break
    if target is None:
        return None, None
    rate = None
    if hasattr(target, 'rate'):
        rate = target.rate
    elif isinstance(target, dict) and 'rate' in target:
        rate = target['rate']
    if rate is None:
        return None, 'no-rate'
    if hasattr(rate, 'value'):
        return float(rate.value), target.tenor
    if isinstance(rate, dict) and 'value' in rate:
        return float(rate['value']), target.tenor
    return None, 'rate-type-unknown'

for name in CURVES:
    c = load(name=name)
    resp = c.calculate(fields='')
    rate, tenor = get_2y(resp)
    print(name, '->', rate, tenor)
