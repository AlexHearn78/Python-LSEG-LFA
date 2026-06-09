import pandas as pd
import matplotlib.pyplot as plt
from pandas.tseries.offsets import BDay

# 1. Load cof_SX5E_EUR_EON.csv, filter to maturityCode == '1Y', convert date
sx5e_df = pd.read_csv('cof_SX5E_EUR_EON.csv')
sx5e_df = sx5e_df[sx5e_df['maturityCode'] == '1Y'].copy()
sx5e_df['date'] = pd.to_datetime(sx5e_df['date'])
sx5e_df = sx5e_df.sort_values('date')

# 2. Load cof_SPX_USD_SOFR.csv, filter to maturityCode == '1Y', convert date
spx_df = pd.read_csv('cof_SPX_USD_SOFR.csv')
spx_df = spx_df[spx_df['maturityCode'] == '1Y'].copy()
spx_df['date'] = pd.to_datetime(spx_df['date'])
spx_df = spx_df.sort_values('date')

# 3. Load swap_rates_weekly.csv, convert date
swap_df = pd.read_csv('swap_rates_weekly.csv')
swap_df['date'] = pd.to_datetime(swap_df['date'])
swap_df = swap_df.drop_duplicates(subset='date').sort_values('date')

# 4. Merge using merge_asof
# For SX5E
merged_df = pd.merge_asof(swap_df, sx5e_df[['date', 'cofDiv100pct', 'cofDivMarket']], on='date', direction='backward', tolerance=pd.Timedelta(days=5))
merged_df.rename(columns={'cofDiv100pct': 'sx5e_cof_div100', 'cofDivMarket': 'sx5e_cof_market'}, inplace=True)

# For SPX
merged_df = pd.merge_asof(merged_df, spx_df[['date', 'cofDiv100pct', 'cofDivMarket']], on='date', direction='backward', tolerance=pd.Timedelta(days=5))
merged_df.rename(columns={'cofDiv100pct': 'spx_cof_div100', 'cofDivMarket': 'spx_cof_market'}, inplace=True)

# Drop rows with NaN in cof columns
merged_df = merged_df.dropna(subset=['sx5e_cof_div100', 'spx_cof_div100'])

print("Merged DataFrame shape:", merged_df.shape)
print("Columns:", list(merged_df.columns))
print("Sample:")
print(merged_df.head())

# Chart
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# Panel A: SX5E vs €STR
ax1.plot(merged_df['date'], merged_df['sx5e_cof_div100'], color='blue', label='SX5E cofDiv100pct (bps)')
ax1.plot(merged_df['date'], merged_df['sx5e_cof_market'], color='lightblue', linestyle='--', label='SX5E cofDivMarket (bps)')
ax1.set_ylabel('SX5E CofBox (bps)', color='blue')
ax1.tick_params(axis='y', labelcolor='blue')

ax1_twin = ax1.twinx()
ax1_twin.plot(merged_df['date'], merged_df['estr_1y'] * 100, color='grey', label='€STR 1Y (%)')
ax1_twin.set_ylabel('€STR 1Y (%)', color='grey')
ax1_twin.tick_params(axis='y', labelcolor='grey')

ax1.set_title('SX5E implied funding spread vs €STR 1Y swap')
ax1.legend(loc='upper right')

# Annotations
ax1.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--', label='Year-end 2024')
ax1.axvline(pd.to_datetime('2026-03-25'), color='black', linestyle='--', label='EU div season')

# Panel B: SPX vs SOFR
ax2.plot(merged_df['date'], merged_df['spx_cof_div100'], color='red', label='SPX cofDiv100pct (bps)')
ax2.set_ylabel('SPX CofBox (bps)', color='red')
ax2.tick_params(axis='y', labelcolor='red')

ax2_twin = ax2.twinx()
ax2_twin.plot(merged_df['date'], merged_df['sofr_1y'] * 100, color='grey', label='SOFR 1Y (%)')
ax2_twin.set_ylabel('SOFR 1Y (%)', color='grey')
ax2_twin.tick_params(axis='y', labelcolor='grey')

ax2.set_title('SPX implied funding spread vs SOFR 1Y swap')
ax2.legend(loc='upper right')

# Annotations
ax2.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--', label='Year-end 2024')

plt.tight_layout()
plt.savefig('cofbox_swap_overlay.png', dpi=200)
# plt.show()  # Remove to avoid hanging in terminal

# Statistics
sx5e_spread = merged_df['sx5e_cof_div100'] - (merged_df['estr_1y'] * 10000)  # bps
spx_spread = merged_df['spx_cof_div100'] - (merged_df['sofr_1y'] * 10000)

print(f"Correlation SX5E cofDiv100pct vs €STR 1Y: {merged_df['sx5e_cof_div100'].corr(merged_df['estr_1y'] * 100):.4f}")
print(f"Correlation SPX cofDiv100pct vs SOFR 1Y: {merged_df['spx_cof_div100'].corr(merged_df['sofr_1y'] * 100):.4f}")
print(f"Average SX5E spread (bps): {sx5e_spread.mean():.2f}")
print(f"Average SPX spread (bps): {spx_spread.mean():.2f}")
print(f"Std dev SX5E spread (bps): {sx5e_spread.std():.2f}")
print(f"Std dev SPX spread (bps): {spx_spread.std():.2f}")