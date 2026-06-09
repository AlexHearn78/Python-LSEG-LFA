import pandas as pd
import pathlib

FILES = [
    'coverage_results_v2.csv',
    'coverage_results_may6_2026.csv',
]


def categorize(error_msg):
    if pd.isna(error_msg):
        return 'EMPTY_ERROR'
    m = str(error_msg).lower()
    if 'ric is unknown' in m or 'underlying ric is unknown' in m:
        return 'RIC_OR_UNKNOWN'
    if 'failed to gather enough options' in m:
        return 'INSUFFICIENT_OPTIONS'
    if 'neither mid' in m or 'no other prices' in m:
        return 'PRICING_FILTER_ERROR'
    if 'number of options' in m and 'below the minimum' in m:
        return 'TOO_FEW_OPTIONS'
    if 'json' in m or 'expecting value' in m:
        return 'JSON_PARSE_ERROR'
    if 'gateway error' in m and '401' in m:
        return 'AUTH_GATEWAY_401'
    return 'OTHER_ERROR'


for f in FILES:
    path = pathlib.Path('/Users/alexanderhearn/Desktop/PythonLSEGV2') / f
    df = pd.read_csv(path)
    total = len(df)
    ok = (df['status'] == 'OK').sum()
    other = (df['status'] == 'OTHER').sum()
    failures = df[df['status'] == 'OTHER'].copy()
    failures['category'] = failures['error_message'].apply(categorize)
    counts = failures['category'].value_counts()
    print('\n' + '=' * 60)
    print(f'FILE: {f}')
    print(f'Total {total}, OK {ok} ({100*ok/total:.1f}%), OTHER {other} ({100*other/total:.1f}%)')
    for cat, cnt in counts.items():
        print(f'  {cat:22s}: {cnt:3d} ({100*cnt/other:.1f}% of failures)')
