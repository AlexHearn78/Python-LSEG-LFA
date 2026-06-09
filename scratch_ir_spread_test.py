import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
print('AUTH:', 'SET' if os.getenv('LSEG_APP_KEY') or os.getenv('LSEG_PROFILE') else 'NOT SET')

from lseg_analytics.pricing.market_data.interest_rate_curves import search, load, calculate

# Step 1: search templates
try:
    templates = search()
    print('TEMPLATE COUNT:', len(templates))
    for t in templates:
        print('TEMPLATE:', t)
except Exception as exc:
    print('SEARCH ERROR:', type(exc).__name__, exc)
    raise

usd_candidates = []
eur_candidates = []
for t in templates:
    name = getattr(t, 'name', None) or getattr(t, 'templateName', None) or str(t)
    location = getattr(t, 'location', None) or getattr(t, 'templateId', None)
    if name and any(tok in name.upper() for tok in ['USD', 'TREASURY', 'UST', 'GOVERNMENT', 'GVT']):
        usd_candidates.append((name, location))
    if name and any(tok in name.upper() for tok in ['EUR', 'DE', 'BUND', 'GERMAN', 'GOVERNMENT', 'GVT']):
        eur_candidates.append((name, location))

print('\nUSD government-like templates:')
for name, loc in usd_candidates:
    print('  ', name, loc)
print('\nEUR/German government-like templates:')
for name, loc in eur_candidates:
    print('  ', name, loc)

if usd_candidates:
    print('\nSelected USD candidate:', usd_candidates[0])
else:
    print('\nNo USD government candidate found')
if eur_candidates:
    print('Selected EUR candidate:', eur_candidates[0])
else:
    print('No EUR government candidate found')

# Helper to extract 2Y

def extract_2y_from_points(data_points):
    pts = []
    for pt in data_points:
        term = None
        value = None
        if hasattr(pt, 'term'):
            term = pt.term
        elif hasattr(pt, 'tenor'):
            term = pt.tenor
        elif hasattr(pt, 'time'):
            term = pt.time
        if hasattr(pt, 'zeroRate'):
            value = pt.zeroRate
        elif hasattr(pt, 'value'):
            value = pt.value
        elif hasattr(pt, 'rate'):
            value = pt.rate
        if term is None or value is None:
            continue
        try:
            pts.append((float(term), float(value)))
        except Exception:
            continue
    pts.sort()
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
        interp = v0 + (v1 - v0) * ((2.0 - t0) / (t1 - t0))
        return interp, f'interpolated from {t0}/{t1}'
    return None, 'no 2Y bracket'

for label, candidates in [('USD', usd_candidates), ('EUR', eur_candidates)]:
    if not candidates:
        continue
    name, loc = candidates[0]
    print(f'\n=== Attempt load/calc for {label} candidate: {name} / {loc}')
    try:
        tm = [t for t in templates if getattr(t, 'name', None) == name]
        if tm:
            ct = load(tm[0])
        else:
            ct = load(name)
        print('Loaded:', ct)
    except Exception as exc:
        print('LOAD ERROR TYPE', type(exc).__name__, exc)
        continue
    try:
        resp = calculate(definitions=[ct], fields='')
        print('CALC OK:', type(resp))
        if hasattr(resp, 'dataPoints'):
            print('DATA POINT COUNT:', len(resp.dataPoints))
            value, source = extract_2y_from_points(resp.dataPoints)
            print('2Y extract:', value, source)
        elif hasattr(resp, 'curveData'):
            print('CURVE DATA COUNT:', len(resp.curveData))
            value, source = extract_2y_from_points(resp.curveData)
            print('2Y extract:', value, source)
        else:
            print('RESP ATTRS:', [a for a in dir(resp) if a in ('dataPoints', 'curveData')])
    except Exception as exc:
        print('CALC ERROR TYPE', type(exc).__name__, exc)
