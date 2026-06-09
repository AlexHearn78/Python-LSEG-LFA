import pandas as pd
import numpy as np

# Read the coverage results
df = pd.read_csv('coverage_results_may6_2026.csv')

# Create client-friendly version
client_df = pd.DataFrame({
    'Instrument Name': df['bbg_name'],
    'ISIN': df['isin'],
    'RIC': df['ric'],
    'Region': df['region'],
    'Country': df['country'],
    'Type': df['type'],
    'Status': np.where(df['status'] == 'OK', 'Available', 'Not Available'),
    'ATM Vol 1M': np.where(df['status'] == 'OK',
                          df['atm_vol_30d'].round(2).astype(str) + '%',
                          'N/A'),
    'ATM Vol 3M': np.where(df['status'] == 'OK',
                          df['atm_vol_90d'].round(2).astype(str) + '%',
                          'N/A'),
    'ATM Vol 1Y': np.where(df['status'] == 'OK',
                          df['atm_vol_365d'].round(2).astype(str) + '%',
                          'N/A'),
    'Strike Range': np.where(df['status'] == 'OK',
                            (df['min_strike_pct'].round(1).astype(str) + '% - ' +
                             df['max_strike_pct'].round(1).astype(str) + '%'),
                            'N/A'),
    'Expiry Range': np.where(df['status'] == 'OK',
                            (df['min_expiry_days'].fillna(0).astype(int).astype(str) + 'd - ' +
                             df['max_expiry_days'].fillna(0).astype(int).astype(str) + 'd'),
                            'N/A'),
    'Notes': np.where(df['status'] != 'OK',
                     df['error_message'].str.replace('Bad request: code=FinancialContract-API.PricingError ', ''),
                     '')
})

# Sort by status (Available first) then by region
client_df = client_df.sort_values(['Status', 'Region', 'Country', 'Instrument Name'],
                                ascending=[False, True, True, True])

# Add summary at the top
total_instruments = len(client_df)
available_count = (client_df['Status'] == 'Available').sum()
coverage_pct = (available_count / total_instruments * 100).round(1)

# Create summary row
summary_row = pd.DataFrame({
    'Instrument Name': [f'SUMMARY: {available_count}/{total_instruments} instruments available ({coverage_pct}%)'],
    'ISIN': [''], 'RIC': [''], 'Region': [''], 'Country': [''], 'Type': [''],
    'Status': [''], 'ATM Vol 1M': [''], 'ATM Vol 3M': [''], 'ATM Vol 1Y': [''],
    'Strike Range': [''], 'Expiry Range': [''], 'Notes': ['']
})

# Combine summary and data
final_df = pd.concat([summary_row, client_df], ignore_index=True)

# Save to CSV
final_df.to_csv('client_volatility_coverage_may6_2026.csv', index=False)

print(f"Client-friendly CSV created: client_volatility_coverage_may6_2026.csv")
print(f"Total instruments: {total_instruments}")
print(f"Available: {available_count} ({coverage_pct}%)")
print(f"Not available: {total_instruments - available_count}")

# Show sample of the output
print("\nSample of client CSV:")
print(final_df.head(10).to_string(index=False))