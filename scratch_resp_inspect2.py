import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
from lseg_analytics.pricing.market_data.interest_rate_curves import load

for name in ['USD_SOFR_Swap_ZC_Curve','EUR_ESTR_Swap_ZC_Curve']:
    c = load(name=name)
    resp = c.calculate(fields='')
    print('---', name)
    print('resource description', c.description)
    analytics = resp.analytics
    print('analytics type', type(analytics))
    print('analytics keys', [k for k in analytics.keys()])
    if hasattr(analytics, 'zc_curves'):
        zc = analytics.zc_curves
        print('zc_curves type', type(zc), 'len', len(zc))
        for curve in zc:
            print('curve type', type(curve), dir(curve)[:50])
            if hasattr(curve, 'nodes'):
                print('nodes len', len(curve.nodes))
                for node in curve.nodes[:10]:
                    print(' node', type(node), node)
            if hasattr(curve, 'market_data'):
                md = curve.market_data
                print('market_data type', type(md), 'keys', [k for k in md.keys()])
    if hasattr(analytics, 'constituents'):
        print('constituents len', len(analytics.constituents))
        for cpt in analytics.constituents[:5]:
            print(' cp', type(cpt), cpt)
    print('analytics as_dict keys', list(analytics.as_dict().keys()))
    print('analytics as_dict sample', analytics.as_dict()[:2] if hasattr(analytics.as_dict(), '__getitem__') else analytics.as_dict())
