import pandas as pd
import matplotlib.pyplot as plt

# Load data
df_sx5e = pd.read_csv('fwd_cof_sx5e_weekly.csv')
df_fwd_sx5e = pd.read_csv('fwd_cof_sx5e_forwards.csv')

# Get 3M-to-1Y forward: from_maturity == '1Y', to_maturity == '3M'
df_fwd_3m_to_1y = df_fwd_sx5e[(df_fwd_sx5e['from_maturity'] == '1Y') & (df_fwd_sx5e['to_maturity'] == '3M')]

# Get spot 1Y
df_spot_1y = df_sx5e[df_sx5e['maturity'] == '1Y']

# Merge on date
df_plot = pd.merge(df_fwd_3m_to_1y[['date', 'fwdCofDiv100pct']], df_spot_1y[['date', 'cofDiv100pct']], on='date')

# Convert to bps
df_plot['fwd_bps'] = df_plot['fwdCofDiv100pct'] * 10000
df_plot['spot_bps'] = df_plot['cofDiv100pct'] * 10000

# Sort by date
df_plot['date'] = pd.to_datetime(df_plot['date'])
df_plot = df_plot.sort_values('date')

# Plot
plt.figure(figsize=(12, 6))
plt.plot(df_plot['date'], df_plot['fwd_bps'], label='9M-starting-3M Forward COF (bps)', marker='o')
plt.plot(df_plot['date'], df_plot['spot_bps'], label='1Y Spot COF (bps)', marker='s')
plt.title('9M-starting-3M Forward Cof vs Spot 1Y Cof — both as of date shown')
plt.suptitle('These are contemporaneous observations, not a predictive test', fontsize=10, y=0.95)
plt.xlabel('Date')
plt.ylabel('COF (bps)')
plt.legend()
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('fwd_cof_vs_spot_v2.png', dpi=200)
print("Chart saved as fwd_cof_vs_spot_v2.png")