import pandas as pd

# Read CSV: first column is ticker names (implicit), first row is dates
df = pd.read_csv('/Users/alexanderhearn/Downloads/basket_stocks_by_date.csv', header=None)

# Extract dates and tickers properly
dates = df.iloc[0, :].tolist()  # First row is dates
print(f"Dates (first 5): {dates[:5]}")
print(f"Dates (last 5): {dates[-5:]}")

# All rows are tickers (there's no ticker column name, they're just rows 1-375)
tickers_data = df.iloc[1:, :]
print(f"Tickers count: {len(tickers_data)}")

# Find column indices for our test dates
col_idx_feb12 = None
col_idx_apr22 = None

for idx, date_str in enumerate(dates):
    date_str = str(date_str).strip()
    if date_str == '12-Feb-25':
        col_idx_feb12 = idx
    if date_str == '22-Apr-26':
        col_idx_apr22 = idx

print(f"\nColumn for 12-Feb-25: {col_idx_feb12}")
print(f"Column for 22-Apr-26: {col_idx_apr22}")

# Get tickers on each date
if col_idx_feb12 is not None:
    print(f"\nTickers on 12-Feb-25 (column {col_idx_feb12}):")
    tickers_feb = []
    for idx, row in tickers_data.iterrows():
        val = row.iloc[col_idx_feb12]
        if pd.notna(val):
            ticker = str(val).strip()
            if ticker and ticker.upper() not in ['NAN', 'NONE', '']:
                tickers_feb.append(ticker)
    print(f"  Total: {len(tickers_feb)}")
    print(f"  First 10: {tickers_feb[:10]}")
    # Check for AAPL and NVDA
    aapl_found = [t for t in tickers_feb if 'AAPL' in t.upper()]
    nvda_found = [t for t in tickers_feb if 'NVDA' in t.upper()]
    print(f"  AAPL variants: {aapl_found}")
    print(f"  NVDA variants: {nvda_found}")

if col_idx_apr22 is not None:
    print(f"\nTickers on 22-Apr-26 (column {col_idx_apr22}):")
    tickers_apr = []
    for idx, row in tickers_data.iterrows():
        val = row.iloc[col_idx_apr22]
        if pd.notna(val):
            ticker = str(val).strip()
            if ticker and ticker.upper() not in ['NAN', 'NONE', '']:
                tickers_apr.append(ticker)
    print(f"  Total: {len(tickers_apr)}")
    print(f"  First 10: {tickers_apr[:10]}")
    # Check for AAPL and NVDA
    aapl_found = [t for t in tickers_apr if 'AAPL' in t.upper()]
    nvda_found = [t for t in tickers_apr if 'NVDA' in t.upper()]
    print(f"  AAPL variants: {aapl_found}")
    print(f"  NVDA variants: {nvda_found}")

# Find dates where AAPL and NVDA appear
print(f"\nSearching for AAPL and NVDA across all dates...")
aapl_dates = []
nvda_dates = []

for col_idx, date_str in enumerate(dates):
    for row_idx, row in tickers_data.iterrows():
        val = str(row.iloc[col_idx]).strip()
        if val == 'AAPL US':
            aapl_dates.append(date_str)
        if val == 'NVDA US':
            nvda_dates.append(date_str)

print(f"\nAAPL US appears on {len(aapl_dates)} dates: {aapl_dates[:10]}")
print(f"NVDA US appears on {len(nvda_dates)} dates: {nvda_dates[:10]}")
