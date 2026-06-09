import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Load data
df_sx5e = pd.read_csv('fwd_cof_sx5e_weekly.csv')
df_spx = pd.read_csv('fwd_cof_spx_weekly.csv')
df_fwd_sx5e = pd.read_csv('fwd_cof_sx5e_forwards.csv')
df_fwd_spx = pd.read_csv('fwd_cof_spx_forwards.csv')

# Latest date
latest_date = '2026-04-22'  # Assuming this is the latest

# Filter
df_sx5e_latest = df_sx5e[df_sx5e['date'] == latest_date]
df_spx_latest = df_spx[df_spx['date'] == latest_date]
df_fwd_sx5e_latest = df_fwd_sx5e[df_fwd_sx5e['date'] == latest_date]
df_fwd_spx_latest = df_fwd_spx[df_fwd_spx['date'] == latest_date]

# Get values
spot_1y_sx5e = df_sx5e_latest[df_sx5e_latest['maturity'] == '1Y']['cofDiv100pct'].values[0] * 10000
spot_2y_sx5e = df_sx5e_latest[df_sx5e_latest['maturity'] == '2Y']['cofDiv100pct'].values[0] * 10000
fwd_1y_sx5e = df_fwd_sx5e_latest[(df_fwd_sx5e_latest['from_maturity'] == '2Y') & (df_fwd_sx5e_latest['to_maturity'] == '1Y')]['fwdCofDiv100pct'].values[0] * 10000

spot_1y_spx = df_spx_latest[df_spx_latest['maturity'] == '1Y']['cofDiv100pct'].values[0] * 10000
spot_2y_spx = df_spx_latest[df_spx_latest['maturity'] == '2Y']['cofDiv100pct'].values[0] * 10000
fwd_1y_spx = df_fwd_spx_latest[(df_fwd_spx_latest['from_maturity'] == '2Y') & (df_fwd_spx_latest['to_maturity'] == '1Y')]['fwdCofDiv100pct'].values[0] * 10000

# Plot
fig, ax = plt.subplots(figsize=(10, 6))

# Positions
x = np.arange(2)
width = 0.2

# SX5E bars
ax.bar(x - width, [spot_1y_sx5e, spot_2y_sx5e], width, label='SX5E Spot 1Y', color='blue', alpha=0.7)
ax.bar(x, [fwd_1y_sx5e, 0], width, label='SX5E 1Y-fwd-1Y', color='blue', hatch='/')

# SPX bars
ax.bar(x + width, [spot_1y_spx, spot_2y_spx], width, label='SPX Spot 1Y', color='red', alpha=0.7)
ax.bar(x + 2*width, [fwd_1y_spx, 0], width, label='SPX 1Y-fwd-1Y', color='red', hatch='/')

ax.set_xticks(x)
ax.set_xticklabels(['1Y', '2Y'])
ax.set_ylabel('COF (bps)')
ax.set_title('Spot vs Forward COF: SX5E vs SPX')
ax.legend()
ax.grid(True, axis='y')

# Annotations
ax.text(0 - width/2, spot_1y_sx5e + 5, f'{spot_1y_sx5e:.0f}', ha='center')
ax.text(0 + width/2, fwd_1y_sx5e + 5, f'{fwd_1y_sx5e:.0f}', ha='center')
ax.text(0 + 3*width/2, spot_1y_spx + 5, f'{spot_1y_spx:.0f}', ha='center')
ax.text(0 + 5*width/2, fwd_1y_spx + 5, f'{fwd_1y_spx:.0f}', ha='center')

# Spread annotations
spread_sx5e = fwd_1y_sx5e - spot_1y_sx5e
spread_spx = fwd_1y_spx - spot_1y_spx
ax.annotate(f'SX5E spread: +{spread_sx5e:.0f} bps', xy=(0.5, fwd_1y_sx5e + 10), ha='center')
ax.annotate(f'SPX spread: +{spread_spx:.0f} bps', xy=(0.5, fwd_1y_spx + 10), ha='center')

plt.tight_layout()
plt.savefig('forward_cof_insight.png', dpi=200)
print("Chart saved as forward_cof_insight.png")