import json
from lseg_analytics.socgen.cof_box._functions import post_analysis
import csv
from datetime import datetime

res = post_analysis(
    instruments=[{"instrumentCode": "SPX_USD_SOFR", "maturitiesCodes": ["3M", "6M", "1Y", "2Y"]}],
    analysis_types=["Cof", "FwdCof"],
    start_date="2024-04-02",
    end_date="2026-04-24",
    cof_types=["CofDiv100pct", "CofDivMarket"],
)

instrument = res['instruments'][0]

# Weekly CSV
with open('fwd_cof_spx_weekly.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['date', 'maturity', 'cofDiv100pct', 'cofDivMarket'])
    for cof_entry in instrument['cof']:
        date_str = cof_entry['date']
        date = datetime.fromisoformat(date_str)
        if date.weekday() == 2:  # Wednesday
            for series in cof_entry['series']:
                writer.writerow([date_str, series['maturityCode'], series['cofDiv100pct'], series['cofDivMarket']])

# Forwards CSV
with open('fwd_cof_spx_forwards.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['date', 'from_maturity', 'to_maturity', 'fwdCofDiv100pct', 'fwdCofDivMarket'])
    for fwd_entry in instrument['fwdCof']:
        date_str = fwd_entry['date']
        date = datetime.fromisoformat(date_str)
        if date.weekday() == 2:
            for series in fwd_entry['series']:
                from_mat = series['maturityCode']
                for fwd in series['fwdCofs']:
                    to_mat = fwd['maturityCode']
                    writer.writerow([date_str, from_mat, to_mat, fwd['fwdCofDiv100pct'], fwd['fwdCofDivMarket']])

# Print sample rows
print("Sample rows from fwd_cof_spx_weekly.csv:")
with open('fwd_cof_spx_weekly.csv', 'r') as f:
    lines = f.readlines()[:6]  # first 5 rows + header
    for line in lines:
        print(line.strip())

print("\nSample rows from fwd_cof_spx_forwards.csv:")
with open('fwd_cof_spx_forwards.csv', 'r') as f:
    lines = f.readlines()[:6]
    for line in lines:
        print(line.strip())