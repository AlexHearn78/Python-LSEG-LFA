import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def tenor_to_months(tenor):
    """Convert tenor string to months."""
    if tenor == '3M':
        return 3
    elif tenor == '6M':
        return 6
    elif tenor == '1Y':
        return 12
    elif tenor == '2Y':
        return 24
    return 0

def format_fwd_label(from_mat, to_mat):
    """Convert API convention to market convention label."""
    from_months = tenor_to_months(from_mat)
    to_months = tenor_to_months(to_mat)
    length_months = from_months - to_months
    
    # Format the length
    if length_months == 3:
        length_str = '3M'
    elif length_months == 6:
        length_str = '6M'
    elif length_months == 9:
        length_str = '9M'
    elif length_months == 12:
        length_str = '1Y'
    elif length_months == 18:
        length_str = '18M'
    elif length_months == 21:
        length_str = '21M'
    else:
        length_str = f'{length_months}M'
    
    return f'{length_str} fwd {to_mat}'

# Load data
df_sx5e = pd.read_csv('fwd_cof_sx5e_weekly.csv')
df_spx = pd.read_csv('fwd_cof_spx_weekly.csv')
df_fwd_sx5e = pd.read_csv('fwd_cof_sx5e_forwards.csv')
df_fwd_spx = pd.read_csv('fwd_cof_spx_forwards.csv')

# Find latest date
latest_date = max(df_sx5e['date'].max(), df_spx['date'].max())

# Filter to latest
df_sx5e_latest = df_sx5e[df_sx5e['date'] == latest_date]
df_spx_latest = df_spx[df_spx['date'] == latest_date]
df_fwd_sx5e_latest = df_fwd_sx5e[df_fwd_sx5e['date'] == latest_date]
df_fwd_spx_latest = df_fwd_spx[df_fwd_spx['date'] == latest_date]

# X positions
maturities = ['3M', '6M', '1Y', '2Y']
x_pos = {mat: i for i, mat in enumerate(maturities)}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9))

# Panel A: SX5E
spots_sx5e = df_sx5e_latest.set_index('maturity')['cofDiv100pct'] * 10000
ax1.plot([x_pos[m] for m in spots_sx5e.index], spots_sx5e.values, 'o-', 
         label='Spot COF', markersize=10, linewidth=2, color='#2E86AB')

# Create a dict to track forward labels to avoid duplicates
fwd_labels_added = {}

# Forwards
for _, row in df_fwd_sx5e_latest.iterrows():
    to_mat = row['to_maturity']
    if to_mat in x_pos:
        fwd_bps = row['fwdCofDiv100pct'] * 10000
        x = x_pos[to_mat]
        label = format_fwd_label(row['from_maturity'], to_mat)
        
        # Add label only once per unique label
        if label not in fwd_labels_added:
            ax1.plot(x, fwd_bps, 's', markersize=8, label=label, color='#A23B72')
            fwd_labels_added[label] = True
        else:
            ax1.plot(x, fwd_bps, 's', markersize=8, color='#A23B72')

ax1.set_xticks(list(x_pos.values()))
ax1.set_xticklabels(maturities)
ax1.set_title('SX5E: Spot and Forward COF Curves', fontsize=13, fontweight='bold')
ax1.set_ylabel('COF (bps)', fontsize=11)
ax1.legend(fontsize=9, loc='best')
ax1.grid(True, alpha=0.3)

# Panel B: SPX
spots_spx = df_spx_latest.set_index('maturity')['cofDiv100pct'] * 10000
ax2.plot([x_pos[m] for m in spots_spx.index], spots_spx.values, 'o-', 
         label='Spot COF', markersize=10, linewidth=2, color='#2E86AB')

fwd_labels_added = {}

# Forwards
for _, row in df_fwd_spx_latest.iterrows():
    to_mat = row['to_maturity']
    if to_mat in x_pos:
        fwd_bps = row['fwdCofDiv100pct'] * 10000
        x = x_pos[to_mat]
        label = format_fwd_label(row['from_maturity'], to_mat)
        
        if label not in fwd_labels_added:
            ax2.plot(x, fwd_bps, 's', markersize=8, label=label, color='#A23B72')
            fwd_labels_added[label] = True
        else:
            ax2.plot(x, fwd_bps, 's', markersize=8, color='#A23B72')

ax2.set_xticks(list(x_pos.values()))
ax2.set_xticklabels(maturities)
ax2.set_title('SPX: Spot and Forward COF Curves', fontsize=13, fontweight='bold')
ax2.set_ylabel('COF (bps)', fontsize=11)
ax2.legend(fontsize=9, loc='best')
ax2.grid(True, alpha=0.3)

plt.suptitle(f"Forward Curve Term Structure ({latest_date})", fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('fwd_cof_term_structure_v2.png', dpi=200)
print(f"Chart saved as fwd_cof_term_structure_v2.png")
print(f"Latest date: {latest_date}")