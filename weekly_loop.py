import lseg_analytics.pricing.market_data.interest_rate_curves as irc
from lseg_analytics.pricing._basic_client.models._models import InterestRateCurveCalculationParameters
import csv
import datetime

# Load templates
eur_template = irc.load(resource_id='c7a3eff1-abe8-4061-9f5e-83a76c09ee09')
usd_template = irc.load(resource_id='ce157336-e0c3-49e4-8b23-c1489bfb3c19')

# Date range
start_date = datetime.date(2024, 4, 2)
end_date = datetime.date(2026, 4, 24)

# Find first Wednesday >= start_date
current_date = start_date
while current_date.weekday() != 2:  # 2 is Wednesday
    current_date += datetime.timedelta(days=1)

# Prepare CSV
csv_file = 'swap_rates_weekly.csv'
with open(csv_file, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['date', 'estr_1y', 'sofr_1y'])

data = []
errors = []

date_count = 0
while current_date <= end_date:
    date_str = current_date.isoformat()
    print(f"Processing {date_str}...")
    
    try:
        params = InterestRateCurveCalculationParameters(valuation_date=date_str)
        
        # EUR
        eur_result = eur_template.calculate(pricing_preferences=params)
        eur_dict = eur_result.as_dict()
        eur_points = eur_dict['analytics']['zcCurves'][0]['points']
        eur_1y = next((p for p in eur_points if p['tenor'] in ['12M', '1Y']), None)
        eur_rate = eur_1y['rate']['value'] / 100 if eur_1y else None
        
        # USD
        usd_result = usd_template.calculate(pricing_preferences=params)
        usd_dict = usd_result.as_dict()
        usd_points = usd_dict['analytics']['zcCurves'][0]['points']
        usd_1y = next((p for p in usd_points if p['tenor'] in ['12M', '1Y']), None)
        usd_rate = usd_1y['rate']['value'] / 100 if usd_1y else None
        
        if eur_rate is not None and usd_rate is not None:
            data.append([date_str, eur_rate, usd_rate])
            date_count += 1
            print(f"  EUR: {eur_rate:.4f}, USD: {usd_rate:.4f}")
        else:
            errors.append(f"{date_str}: Missing 1Y rate")
            print(f"  Error: Missing 1Y rate")
    
    except Exception as e:
        errors.append(f"{date_str}: {str(e)}")
        print(f"  Error: {str(e)}")
    
    # Save every 10 dates
    if date_count % 10 == 0 and data:
        with open(csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(data[-10:])
        print(f"Saved {len(data)} dates so far")
    
    # Next Wednesday
    current_date += datetime.timedelta(days=7)

# Save remaining
if data:
    with open(csv_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data[-(date_count % 10):])

print(f"Completed. Total dates: {date_count}")
if errors:
    print("Errors:")
    for err in errors:
        print(f"  {err}")