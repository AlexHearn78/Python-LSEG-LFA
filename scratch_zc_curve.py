import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load

c = load(name='USD_SOFR_Swap_ZC_Curve')
resp = c.calculate(fields='')
zc = resp.analytics.zc_curves
print('zc type', type(zc), 'len', len(zc))
first = zc[0]
print('first type', type(first))
print('fields', [k for k in first.keys()])
print('first as_dict keys', list(first.as_dict().keys()))
print('first as_dict item types:')
for k,v in first.as_dict().items():
    print(' ', k, type(v), repr(v)[:200])
