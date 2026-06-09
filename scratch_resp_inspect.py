import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load

def inspect_resp(name):
    c = load(name=name)
    print('---', name)
    resp = c.calculate(fields='')
    print('resp type', type(resp))
    keys = [k for k in dir(resp) if not k.startswith('_')]
    print('resp attrs', keys)
    print('resource type', type(resp.resource))
    print('resource attrs', [a for a in dir(resp.resource) if not a.startswith('_')])
    print('analytics type', type(resp.analytics))
    print('analytics attrs', [a for a in dir(resp.analytics) if not a.startswith('_')])
    for attr in ['dataPoints','curveData','items','analytics']:
        if hasattr(resp, attr):
            val = getattr(resp, attr)
            print(attr, 'len', len(val) if hasattr(val, '__len__') else 'n/a', type(val))
            if hasattr(val, '__iter__'):
                for i, pt in enumerate(val[:5]):
                    print('  ', attr, i, type(pt), repr(pt)[:400])

for name in ['USD_SOFR_Swap_ZC_Curve','EUR_ESTR_Swap_ZC_Curve']:
    inspect_resp(name)
