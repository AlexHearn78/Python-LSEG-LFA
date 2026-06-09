import lseg_analytics.pricing.market_data.interest_rate_curves as irc
from lseg_analytics.pricing._basic_client.models._models import InterestRateCurveCalculationParameters

# Load templates
eur_template = irc.load(resource_id='c7a3eff1-abe8-4061-9f5e-83a76c09ee09')
usd_template = irc.load(resource_id='ce157336-e0c3-49e4-8b23-c1489bfb3c19')

# Parameters for 2024-04-02
params = InterestRateCurveCalculationParameters(valuation_date='2024-04-02')

# Calculate EUR
eur_result = eur_template.calculate(pricing_preferences=params)
eur_dict = eur_result.as_dict()
print("EUR keys:", list(eur_dict.keys()))
print("EUR analytics keys:", list(eur_dict.get('analytics', {}).keys()) if 'analytics' in eur_dict else "No analytics")
if 'analytics' in eur_dict and 'zcCurves' in eur_dict['analytics']:
    eur_points = eur_dict['analytics']['zcCurves'][0]['points']
    eur_1y = next((p for p in eur_points if p['tenor'] in ['12M', '1Y']), None)
    if eur_1y:
        eur_rate = eur_1y['rate']['value'] / 100  # to decimal
        print(f"EUR ESTR 1Y on 2024-04-02: {eur_rate:.4f}")
    else:
        print("EUR 1Y not found")
else:
    print("No zcCurves in EUR analytics")

# Calculate USD
usd_result = usd_template.calculate(pricing_preferences=params)
usd_dict = usd_result.as_dict()
print("USD keys:", list(usd_dict.keys()))
print("USD analytics keys:", list(usd_dict.get('analytics', {}).keys()) if 'analytics' in usd_dict else "No analytics")
if 'analytics' in usd_dict and 'zcCurves' in usd_dict['analytics']:
    usd_points = usd_dict['analytics']['zcCurves'][0]['points']
    usd_1y = next((p for p in usd_points if p['tenor'] in ['12M', '1Y']), None)
    if usd_1y:
        usd_rate = usd_1y['rate']['value'] / 100  # to decimal
        print(f"USD SOFR 1Y on 2024-04-02: {usd_rate:.4f}")
    else:
        print("USD 1Y not found")
else:
    print("No zcCurves in USD analytics")