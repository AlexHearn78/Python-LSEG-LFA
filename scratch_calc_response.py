import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load, calculate

for name in ['USD_SOFR_Swap_ZC_Curve', 'EUR_ESTR_Swap_ZC_Curve']:
    print('---', name)
    c = load(name=name)
    defn = c.definition
    print('definition type', type(defn))
    print('definition repr', repr(defn)[:1000])
    print('definition attrs', [a for a in dir(defn) if not a.startswith('_')][:40])
    try:
        resp = calculate(definitions=[defn], fields='')
        print('calculate type', type(resp))
        attrs = [a for a in dir(resp) if not a.startswith('_')]
        print('resp attrs', attrs)
        for attr in ('curveData', 'dataPoints', 'items'):
            if hasattr(resp, attr):
                val = getattr(resp, attr)
                print(f'{attr} len', len(val) if hasattr(val, '__len__') else 'n/a')
                for i, pt in enumerate(val[:5]):
                    print(' ', attr, i, type(pt), repr(pt)[:400])
    except Exception as exc:
        print('calculate error', type(exc).__name__, exc)
