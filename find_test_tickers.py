import pandas as pd

df = pd.read_csv('/Users/alexanderhearn/Downloads/basket_stocks_by_date.csv', header=None)
dates = df.iloc[0, :].tolist()
tickers_df = df.iloc[1:, :]

# Look for any AAPL or NVDA
all_values = set()
for row in tickers_df.itertuples(index=False):
    for val in row:
        if pd.notna(val):
            val_str = str(val).strip()
            if 'AAPL' in val_str or 'NVDA' in val_str:
                all_values.add(val_str)

print("All AAPL/NVDA variants found:")
for val in sorted(all_values):
    print(f"  {val}")

# Also find tickers that appear on 2025-02-12 and 2026-04-22
col_idx_feb = None
col_idx_apr = None

for idx, date in enumerate(dates):
    if '12-Feb-25' in str(date):
        col_idx_feb = idx
    if '22-Apr-26' in str(date):
        col_idx_apr = idx

print(f"\n2025-02-12 column index: {col_idx_feb}")
print(f"2026-04-22 column index: {col_idx_apr}")

if col_idx_feb is not None:
    print(f"\nTickers on 2025-02-12:")
    tickers_feb = []
    for idx, row in tickers_df.iterrows():
        val = row.iloc[col_idx_feb]
        if pd.notna(val):
            ticker = str(val).strip()
            tickers_feb.append(ticker)
    print(f"  Count: {len(tickers_feb)}")
    print(f"  Sample: {tickers_feb[:5]}")

if col_idx_apr is not None:
    print(f"\nTickers on 2026-04-22:")
    tickers_apr = []
    for idx, row in tickers_df.iterrows():
        val = row.iloc[col_idx_apr]
        if pd.notna(val):
            ticker = str(val).strip()
            tickers_apr.append(ticker)
    print(f"  Count: {len(tickers_apr)}")
    print(f"  Sample: {tickers_apr[:5]}")
