import pandas as pd
import numpy as np

# Load the CSV
df = pd.read_csv('/Users/alexanderhearn/Downloads/basket_stocks_by_date.csv', header=None)

print(f"CSV shape: {df.shape}")

# Row 0 is dates
dates = df.iloc[0, :].tolist()
print(f"Date range: {dates[0]} to {dates[-1]}")

# Rows 1+ are tickers
tickers_df = df.iloc[1:, :]
print(f"Number of tickers: {len(tickers_df)}")

# Look for AAPL US and NVDA US
for ticker_idx, (idx, row) in enumerate(tickers_df.iterrows()):
    first_val = str(row.iloc[0]).strip()
    if first_val == 'AAPL US':
        print(f"\nAAPL US found at row {ticker_idx}:")
        # Count how many dates it appears on
        present_count = sum(1 for val in row if pd.notna(val) and str(val).strip() == 'AAPL US')
        print(f"  Present on {present_count} dates")
        # Find specific dates
        for col_idx, val in enumerate(row):
            if pd.notna(val) and str(val).strip() == 'AAPL US':
                date = dates[col_idx]
                print(f"    {date}")
                if '12-Feb-25' in str(date):
                    print(f"      ^ Contains 12-Feb-25!")
                if '22-Apr-26' in str(date):
                    print(f"      ^ Contains 22-Apr-26!")
    
    if first_val == 'NVDA US':
        print(f"\nNVDA US found at row {ticker_idx}:")
        # Count how many dates it appears on
        present_count = sum(1 for val in row if pd.notna(val) and str(val).strip() == 'NVDA US')
        print(f"  Present on {present_count} dates")
        # Find specific dates
        for col_idx, val in enumerate(row):
            if pd.notna(val) and str(val).strip() == 'NVDA US':
                date = dates[col_idx]
                print(f"    {date}")
                if '12-Feb-25' in str(date):
                    print(f"      ^ Contains 12-Feb-25!")
                if '22-Apr-26' in str(date):
                    print(f"      ^ Contains 22-Apr-26!")
