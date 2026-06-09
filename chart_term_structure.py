import pandas as pd
import matplotlib.pyplot as plt

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

# Maturity to months
mat_to_months = {'3M': 3, '6M': 6, '1Y': 12, '2Y': 24}

# Function to get label
def get_label(row):
    from_mat = row['from_maturity']
    to_mat = row['to_maturity']
    length = mat_to_months[from_mat] - mat_to_months[to_mat]
    return f"{length}M fwd {to_mat}"

# X positions
maturities = ['3M', '6M', '1Y', '2Y']
x_pos = {mat: i for i, mat in enumerate(maturities)}

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

# Panel A: SX5E
spots_sx5e = df_sx5e_latest.set_index('maturity')['cofDiv100pct'] * 10000
ax1.plot([x_pos[m] for m in spots_sx5e.index], spots_sx5e.values, 'o-', label='Spot COF (bps)', markersize=8)

# Forwards
labels_used = set()
for _, row in df_fwd_sx5e_latest.iterrows():
    to_mat = row['to_maturity']
    if to_mat in x_pos:
        fwd_bps = row['fwdCofDiv100pct'] * 10000
        x = x_pos[to_mat]
        label = get_label(row)
        if label not in labels_used:
            ax1.plot(x, fwd_bps, 's', markersize=6, label=label)
            labels_used.add(label)
        else:
            ax1.plot(x, fwd_bps, 's', markersize=6)

ax1.set_xticks(list(x_pos.values()))
ax1.set_xticklabels(maturities)
ax1.set_title('SX5E: Spot and Forward COF Curves')
ax1.set_ylabel('COF (bps)')
ax1.legend()
ax1.grid(True)

# Panel B: SPX
spots_spx = df_spx_latest.set_index('maturity')['cofDiv100pct'] * 10000
ax2.plot([x_pos[m] for m in spots_spx.index], spots_spx.values, 'o-', label='Spot COF (bps)', markersize=8)

# Forwards
labels_used = set()
for _, row in df_fwd_spx_latest.iterrows():
    to_mat = row['to_maturity']
    if to_mat in x_pos:
        fwd_bps = row['fwdCofDiv100pct'] * 10000
        x = x_pos[to_mat]
        label = get_label(row)
        if label not in labels_used:
            ax2.plot(x, fwd_bps, 's', markersize=6, label=label)
            labels_used.add(label)
        else:
            ax2.plot(x, fwd_bps, 's', markersize=6)

ax2.set_xticks(list(x_pos.values()))
ax2.set_xticklabels(maturities)
ax2.set_title('SPX: Spot and Forward COF Curves')
ax2.set_ylabel('COF (bps)')
ax2.legend()
ax2.grid(True)

plt.suptitle(f"Today's Forward Curve ({latest_date})")
plt.tight_layout()
plt.savefig('fwd_cof_term_structure_v2.png', dpi=200)
print("Chart saved as fwd_cof_term_structure_v2.png")