import pandas as pd
import matplotlib.pyplot as plt
from datetime import timedelta

def predictive_test(instrument_name, fwd_file, spot_file, output_png):
    # Load data
    forwards = pd.read_csv(fwd_file)
    spot = pd.read_csv(spot_file)
    
    # Filter forward 1Y-fwd-1Y: from 2Y to 1Y
    fwd_1y_fwd = forwards[(forwards['from_maturity'] == '2Y') & (forwards['to_maturity'] == '1Y')].copy()
    fwd_1y_fwd['date'] = pd.to_datetime(fwd_1y_fwd['date'])
    
    # Spot 1Y
    spot_1y = spot[spot['maturityCode'] == '1Y'].copy()
    spot_1y['date'] = pd.to_datetime(spot_1y['date'])
    
    predictions = []
    for _, row in fwd_1y_fwd.iterrows():
        x_date = row['date']
        fwd_rate = row['fwdCofDiv100pct']
        target_date = x_date + timedelta(days=365)
        
        # Find closest spot date
        spot_1y['diff'] = (spot_1y['date'] - target_date).abs()
        closest_idx = spot_1y['diff'].idxmin()
        closest_row = spot_1y.loc[closest_idx]
        spot_rate = closest_row['cofDiv100pct']
        actual_date = closest_row['date']
        
        predictions.append({
            'date': actual_date,
            'predicted': fwd_rate,
            'actual': spot_rate
        })
    
    df = pd.DataFrame(predictions)
    
    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(df['date'], df['predicted'], label='Predicted (Forward 1Y-fwd-1Y)', marker='o')
    plt.plot(df['date'], df['actual'], label='Realised (Spot 1Y)', marker='x')
    plt.xlabel('Date')
    plt.ylabel('Cof Div 100pct')
    plt.title(f'Predictive Test: {instrument_name} Forward Cof')
    plt.legend()
    plt.grid(True)
    plt.savefig(output_png)
    plt.close()
    
    # Stats
    if len(df) > 1:
        corr = df['predicted'].corr(df['actual'])
        mae = (df['predicted'] - df['actual']).abs().mean() * 10000  # bps
        bias = (df['actual'] - df['predicted']).mean() * 10000  # bps
        print(f"{instrument_name}:")
        print(f"Sample size: {len(df)}")
        print(f"Correlation: {corr:.3f}")
        print(f"Mean Absolute Error: {mae:.1f} bps")
        if bias > 0:
            print(f"Forward under-predicts realised by {bias:.1f} bps on average")
        elif bias < 0:
            print(f"Forward over-predicts realised by {-bias:.1f} bps on average")
        else:
            print("No systematic bias")
    else:
        print(f"{instrument_name}: Insufficient data")

# SX5E
predictive_test('SX5E', 'fwd_cof_sx5e_forwards.csv', 'cof_SX5E_EUR_EON.csv', 'fwd_predictive_test_sx5e.png')

# SPX
predictive_test('SPX', 'fwd_cof_spx_forwards.csv', 'cof_SPX_USD_SOFR.csv', 'fwd_predictive_test_spx.png')