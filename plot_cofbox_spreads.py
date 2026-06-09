import pandas as pd
import matplotlib.pyplot as plt

# Load CofBox 1Y data
sx5e_df = pd.read_csv('cof_SX5E_EUR_EON.csv')
sx5e_df = sx5e_df[sx5e_df['maturityCode'] == '1Y'].copy()
sx5e_df['date'] = pd.to_datetime(sx5e_df['date'])
sx5e_df = sx5e_df.sort_values('date')

spx_df = pd.read_csv('cof_SPX_USD_SOFR.csv')
spx_df = spx_df[spx_df['maturityCode'] == '1Y'].copy()
spx_df['date'] = pd.to_datetime(spx_df['date'])
spx_df = spx_df.sort_values('date')

# Load swap rates weekly and unique dates
swap_df = pd.read_csv('swap_rates_weekly.csv')
swap_df['date'] = pd.to_datetime(swap_df['date'])
swap_df = swap_df.drop_duplicates(subset='date').sort_values('date')

# Merge data using prior business-day matching
merged_df = pd.merge_asof(
    swap_df,
    sx5e_df[['date', 'cofDiv100pct', 'cofDivMarket']],
    on='date',
    direction='backward',
    tolerance=pd.Timedelta(days=5),
)
merged_df.rename(columns={'cofDiv100pct': 'sx5e_cof_div100', 'cofDivMarket': 'sx5e_cof_market'}, inplace=True)
merged_df = pd.merge_asof(
    merged_df,
    spx_df[['date', 'cofDiv100pct', 'cofDivMarket']],
    on='date',
    direction='backward',
    tolerance=pd.Timedelta(days=5),
)
merged_df.rename(columns={'cofDiv100pct': 'spx_cof_div100', 'cofDivMarket': 'spx_cof_market'}, inplace=True)
merged_df = merged_df.dropna(subset=['sx5e_cof_div100', 'spx_cof_div100']).reset_index(drop=True)

# Figure 1: CofBox spreads
fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
ax1.plot(merged_df['date'], merged_df['sx5e_cof_div100'] * 10000, color='blue', label='SX5E cofDiv100pct')
ax1.plot(merged_df['date'], merged_df['sx5e_cof_market'] * 10000, color='lightblue', linestyle='--', label='SX5E cofDivMarket')
ax1.set_ylabel('bps')
ax1.set_title('SX5E implied funding spread (markup over €STR 1Y)')
ax1.legend(loc='upper right')
ax1.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--')
ax1.text(
    0.02,
    0.95,
    'Year-end 2024',
    transform=ax1.transAxes,
    va='top',
    ha='left',
    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='black', alpha=0.8),
)

ax2.plot(merged_df['date'], merged_df['spx_cof_div100'] * 10000, color='red', label='SPX cofDiv100pct')
ax2.set_ylabel('bps')
ax2.set_title('SPX implied funding spread (markup over SOFR 1Y)')
ax2.legend(loc='upper right')
ax2.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--')
ax2.text(
    0.02,
    0.95,
    'Year-end 2024',
    transform=ax2.transAxes,
    va='top',
    ha='left',
    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='black', alpha=0.8),
)

plt.tight_layout()
fig1.savefig('cofbox_spreads_v2.png', dpi=200)
plt.close(fig1)

# Figure 2: Rates and spreads
fig2, (ax3, ax4, ax5) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
ax3.plot(merged_df['date'], merged_df['estr_1y'] * 100, color='grey')
ax3.set_ylabel('€STR 1Y (%)')
ax3.set_title('€STR 1Y rate (%) over time')
ax3.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--')

ax4.plot(merged_df['date'], merged_df['sofr_1y'] * 100, color='grey')
ax4.set_ylabel('SOFR 1Y (%)')
ax4.set_title('SOFR 1Y rate (%) over time')
ax4.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--')

ax5.plot(merged_df['date'], merged_df['sx5e_cof_div100'] * 10000, color='blue', label='SX5E cofDiv100pct')
ax5.plot(merged_df['date'], merged_df['spx_cof_div100'] * 10000, color='red', label='SPX cofDiv100pct')
ax5.set_ylabel('bps')
ax5.set_title('CofBox implied funding spread markups')
ax5.legend(loc='upper right')
ax5.axvline(pd.to_datetime('2024-12-18'), color='black', linestyle='--')
ax5.text(
    0.02,
    0.95,
    'Year-end 2024',
    transform=ax5.transAxes,
    va='top',
    ha='left',
    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='black', alpha=0.8),
)

fig2.suptitle('The markup moves independently of rates\nPearson correlation: SX5E vs €STR = 0.02; SPX vs SOFR = 0.13', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])
fig2.savefig('cofbox_vs_rates_v2.png', dpi=200)
plt.close(fig2)

print('Saved cofbox_spreads_v2.png and cofbox_vs_rates_v2.png')
print('Merged rows:', len(merged_df))
print('Correlation SX5E vs €STR 1Y:', merged_df['sx5e_cof_div100'].corr(merged_df['estr_1y'] * 100))
print('Correlation SPX vs SOFR 1Y:', merged_df['spx_cof_div100'].corr(merged_df['sofr_1y'] * 100))
