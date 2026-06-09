import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import search, load, calculate

usd_templates = search(tags=['currency:USD', 'indexName:SOFR'], item_per_page=500)
eur_templates = search(tags=['currency:EUR', 'indexName:ESTR'], item_per_page=500)
print('USD templates', [t['location']['name'] for t in usd_templates])
print('EUR templates', [t['location']['name'] for t in eur_templates])

def extract(resp):
    data = None
    if hasattr(resp, 'dataPoints'):
        data = resp.dataPoints
    elif hasattr(resp, 'curveData'):
        data = resp.curveData
    elif isinstance(resp, dict) and 'dataPoints' in resp:
        data = resp['dataPoints']
    if data is None:
        print('No data points on response; repr', resp)
        return None, None
    pts = []
    for pt in data:
        term = None
        if hasattr(pt, 'term'):
            term = pt.term
        elif hasattr(pt, 'tenor'):
            term = pt.tenor
        elif hasattr(pt, 'time'):
            term = pt.time
        value = None
        if hasattr(pt, 'zeroRate'):
            value = pt.zeroRate
        elif hasattr(pt, 'rate'):
            value = pt.rate
        elif hasattr(pt, 'value'):
            value = pt.value
        if term is None or value is None:
            continue
        try:
            pts.append((float(term), float(value)))
        except Exception:
            continue
    pts.sort()
    print('POINTS count', len(pts), 'first 10', pts[:10])
    for term, value in pts:
        if abs(term - 2.0) < 1e-9:
            return value, '2.0'
    lower = None
    upper = None
    for term, value in pts:
        if term < 2.0:
            lower = (term, value)
        elif term > 2.0 and upper is None:
            upper = (term, value)
    if lower and upper:
        t0, v0 = lower
        t1, v1 = upper
        interp = v0 + (v1 - v0) * ((2.0 - t0)/(t1 - t0))
        return interp, f'interpolated from {t0}/{t1}'
    return None, 'no 2y'

for label, templates in [('USD', usd_templates), ('EUR', eur_templates)]:
    if not templates:
        print(label, 'no templates')
        continue
    t = templates[0]
    print('\n---', label, t['location']['name'])
    try:
        loaded = load(t)
        print('loaded', loaded)
    except Exception as exc:
        print('load error', type(exc).__name__, exc)
        continue
    try:
        resp = calculate(definitions=[loaded], fields='')
        print('calculate type', type(resp))
        if hasattr(resp, 'dataPoints'):
            print('dataPoints len', len(resp.dataPoints))
        if hasattr(resp, 'curveData'):
            print('curveData len', len(resp.curveData))
        val, src = extract(resp)
        print('2Y:', val, src)
    except Exception as exc:
        print('calc error', type(exc).__name__, exc)
