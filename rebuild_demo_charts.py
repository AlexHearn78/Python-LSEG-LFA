import argparse
from datetime import timedelta

import matplotlib.pyplot as plt
import pandas as pd


def format_fwd_label(from_mat, to_mat):
    mapping = {
        ('6M', '3M'): '3M fwd 3M',
        ('1Y', '3M'): '9M fwd 3M',
        ('1Y', '6M'): '6M fwd 6M',
        ('2Y', '3M'): '21M fwd 3M',
        ('2Y', '6M'): '18M fwd 6M',
        ('2Y', '1Y'): '1Y fwd 1Y',
    }
    return mapping.get((from_mat, to_mat), f'{from_mat}->{to_mat}')


def chart1_forward_cof_insight_v3():
    df_sx5e = pd.read_csv('fwd_cof_sx5e_weekly.csv')
    df_spx = pd.read_csv('fwd_cof_spx_weekly.csv')
    df_fwd_sx5e = pd.read_csv('fwd_cof_sx5e_forwards.csv')
    df_fwd_spx = pd.read_csv('fwd_cof_spx_forwards.csv')

    latest_date = max(df_sx5e['date'].max(), df_spx['date'].max())

    def extract_values(df_spot, df_fwd, label):
        spot_val = (
            df_spot[(df_spot['date'] == latest_date) & (df_spot['maturity'] == '1Y')]
            ['cofDiv100pct'].iloc[0] * 10000
        )
        fwd_val = (
            df_fwd[(df_fwd['date'] == latest_date) &
                   (df_fwd['from_maturity'] == '2Y') &
                   (df_fwd['to_maturity'] == '1Y')]
            ['fwdCofDiv100pct'].iloc[0] * 10000
        )
        return round(spot_val, 1), round(fwd_val, 1)

    sx5e_spot, sx5e_fwd = extract_values(df_sx5e, df_fwd_sx5e, 'SX5E')
    spx_spot, spx_fwd = extract_values(df_spx, df_fwd_spx, 'SPX')

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    fig.patch.set_facecolor('white')
    colors = {'spot': '#9AA5B7', 'fwd': '#2F5AC8'}

    chart_data = [
        ('SX5E', sx5e_spot, sx5e_fwd),
        ('SPX', spx_spot, spx_fwd),
    ]

    for ax, (name, spot_val, fwd_val) in zip(axes, chart_data):
        x = [0, 1]
        labels = ['Spot 1Y', '1Y-fwd-1Y']
        values = [spot_val, fwd_val]
        colors_list = [colors['spot'], colors['fwd']]
        bars = ax.bar(x, values, color=colors_list, width=0.55)
        ax.set_title(name, fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylim(0, max(values) * 1.6)  # Increased headroom
        ax.grid(axis='y', alpha=0.25)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 5,  # Moved higher
                f'{int(round(value))}',
                ha='center', va='bottom', fontsize=12, fontweight='bold'
            )

        diff = int(round(fwd_val - spot_val))
        y_line = max(values) + 15  # Higher bracket
        ax.plot([0, 1], [y_line, y_line], color='black', lw=1.8)
        ax.plot([0, 0], [spot_val + 3, y_line], color='black', lw=1.8)
        ax.plot([1, 1], [fwd_val + 3, y_line], color='black', lw=1.8)
        ax.text(0.5, y_line + 4, f'+{diff} bps', ha='center', va='bottom', fontsize=16, fontweight='bold')

    fig.suptitle(
        'Forward Cof carries +19 bps in EU vs +7 bps in US',
        fontsize=18,
        fontweight='bold',
        y=0.97,
    )
    fig.text(
        0.5,
        0.93,
        '1Y-forward-1Y vs spot 1Y, as of 22 April 2026',
        ha='center',
        fontsize=12,
    )
    fig.text(
        0.5,
        0.03,
        'SocGen CofBox via LSEG API. Spot Cof correlation with €STR / SOFR: 0.02 / 0.13.',
        ha='center',
        fontsize=10,
        color='#4D4D4D',
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.92])
    fig.savefig('forward_cof_insight_v3.png', dpi=200)
    plt.close(fig)
    print('DONE - forward_cof_insight_v3.png saved. Visually verify labels and annotations do not overlap.')


def chart2_fwd_cof_term_structure_v4():
    df_sx5e = pd.read_csv('fwd_cof_sx5e_weekly.csv')
    df_spx = pd.read_csv('fwd_cof_spx_weekly.csv')
    df_fwd_sx5e = pd.read_csv('fwd_cof_sx5e_forwards.csv')
    df_fwd_spx = pd.read_csv('fwd_cof_spx_forwards.csv')

    latest_date = max(df_sx5e['date'].max(), df_spx['date'].max())

    x_order = ['3M', '6M', '1Y', '2Y']
    x_positions = {mat: idx for idx, mat in enumerate(x_order)}

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.patch.set_facecolor('white')

    for ax, df_spot, df_fwd, panel_name in [
        (ax1, df_sx5e, df_fwd_sx5e, 'SX5E'),
        (ax2, df_spx, df_fwd_spx, 'SPX'),
    ]:
        spot_data = df_spot[df_spot['date'] == latest_date].set_index('maturity')['cofDiv100pct'] * 10000
        x = [x_positions[mat] for mat in spot_data.index]
        y = spot_data.values
        ax.plot(x, y, marker='o', linestyle='-', color='#2F5AC8', linewidth=2.2, markersize=8, label='Spot COF')

        # Forwards as horizontal bars
        fwd_color = '#D1495B'
        fwd_added = False
        for _, row in df_fwd[df_fwd['date'] == latest_date].iterrows():
            from_mat = row['from_maturity']
            to_mat = row['to_maturity']
            if from_mat not in x_positions or to_mat not in x_positions:
                continue
            xmin = x_positions[to_mat]
            xmax = x_positions[from_mat]
            y_fwd = row['fwdCofDiv100pct'] * 10000
            ax.plot([xmin, xmax], [y_fwd, y_fwd], color=fwd_color, linewidth=4, solid_capstyle='butt')
            if not fwd_added:
                ax.plot([], [], color=fwd_color, linewidth=4, label='Forward')  # Dummy for legend
                fwd_added = True

        ax.set_xticks(list(x_positions.values()))
        ax.set_xticklabels(x_order, fontsize=11)
        ax.set_ylabel('COF (bps)', fontsize=11)
        ax.set_title(f'{panel_name}: Spot and Forward COF Curves', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.25)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(fontsize=9, loc='best')

    fig.suptitle('Forward COF Term Structure', fontsize=16, fontweight='bold', y=0.98)
    fig.tight_layout(rect=[0, 0.0, 1, 0.96])
    fig.savefig('fwd_cof_term_structure_v4.png', dpi=200)

    print('Chart saved as fwd_cof_term_structure_v4.png')


def chart3_fwd_predictive_test_sx5e():
    df_fwd = pd.read_csv('fwd_cof_sx5e_forwards.csv')
    df_spot = pd.read_csv('cof_SX5E_EUR_EON.csv')
    df_fwd['date'] = pd.to_datetime(df_fwd['date'])
    df_spot['date'] = pd.to_datetime(df_spot['date'])

    df_fwd = df_fwd[(df_fwd['from_maturity'] == '2Y') & (df_fwd['to_maturity'] == '1Y')]
    df_spot = df_spot[df_spot['maturityCode'] == '1Y']

    print(f'Forward rows (2Y->1Y): {len(df_fwd)}')
    print(f'Spot 1Y rows: {len(df_spot)}')

    pairs = []
    for _, row in df_fwd.iterrows():
        target = row['date'] + timedelta(days=365)
        window = df_spot[(df_spot['date'] >= target - timedelta(days=7)) & (df_spot['date'] <= target + timedelta(days=7))]
        if window.empty:
            continue
        closest = window.loc[(window['date'] - target).abs().idxmin()]
        pairs.append({
            'prediction_date': row['date'],
            'realisation_date': closest['date'],
            'predicted': row['fwdCofDiv100pct'] * 10000,
            'realised': closest['cofDiv100pct'] * 10000,
        })

    df_pairs = pd.DataFrame(pairs)
    print(f'Paired rows within ±7 days: {len(df_pairs)}')

    if df_pairs.empty:
        raise RuntimeError('No valid pairs found for SX5E predictive test.')

    df_pairs = df_pairs.sort_values('realisation_date')
    corr = df_pairs['predicted'].corr(df_pairs['realised'])
    mae = (df_pairs['predicted'] - df_pairs['realised']).abs().mean()
    bias = (df_pairs['predicted'] - df_pairs['realised']).mean()

    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('white')
    ax.plot(df_pairs['realisation_date'], df_pairs['predicted'], marker='o', linestyle='-', label='Prediction (forward)', color='#2F5AC8')
    ax.plot(df_pairs['realisation_date'], df_pairs['realised'], marker='s', linestyle='-', label='Realisation (spot)', color='#D1495B')
    ax.set_title('SX5E predictive test: 1Y-fwd-1Y forward vs realised spot', fontsize=16, fontweight='bold')
    ax.set_xlabel('Realisation date')
    ax.set_ylabel('COF (bps)')
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=11)
    fig.autofmt_xdate(rotation=25)

    note = (
        f'Sample size: {len(df_pairs)} paired points (forwards Apr 2024–Apr 2025, realised Apr 2025–Apr 2026)'
    )
    fig.text(0.02, 0.02, note, fontsize=10, color='#4D4D4D')
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])

    positive = corr > 0.5 and mae < 15
    out_name = 'fwd_predictive_test_sx5e.png' if positive else 'fwd_predictive_test_negative.png'
    fig.savefig(out_name, dpi=200)
    plt.close(fig)

    print(f'Correlation: {corr:.3f}')
    print(f'Mean absolute error: {mae:.1f} bps')
    if bias > 0:
        print(f'Forwards over-predicted realised by {bias:.1f} bps on average')
    elif bias < 0:
        print(f'Forwards under-predicted realised by {abs(bias):.1f} bps on average')
    else:
        print('No average prediction bias detected')

    if positive:
        print(f'Chart saved as {out_name}')
        print('Result is positive enough to consider for the deck.')
    else:
        print(f'Chart saved as {out_name}')
        print('Negative result: this should NOT be used in the demo deck.')


def main():
    parser = argparse.ArgumentParser(description='Rebuild selected demo charts')
    parser.add_argument('chart', choices=['chart1', 'chart2'], help='Which chart to build')
    args = parser.parse_args()

    if args.chart == 'chart1':
        chart1_forward_cof_insight_v3()
    elif args.chart == 'chart2':
        chart2_fwd_cof_term_structure_v4()


if __name__ == '__main__':
    main()
