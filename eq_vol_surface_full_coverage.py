import pandas as pd
from eq_vol_surface_pull_universe import get_surface_info

UNIVERSE_PATH = 'universe_full.txt'
OUTPUT_PATH = 'eq_vol_surface_full_universe_coverage.csv'


def load_universe_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if len(lines) % 4 == 3:
        lines.append('')
    if len(lines) % 4 != 0:
        raise ValueError(
            f'Universe file must contain groups of 4 non-empty lines: got {len(lines)} lines'
        )

    entries = []
    seen = set()
    for i in range(0, len(lines), 4):
        entry = {
            'name': lines[i],
            'long_name': lines[i + 1],
            'currency': lines[i + 2],
            'isin': lines[i + 3],
        }
        key = (entry['name'], entry['isin'], entry['currency'])
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    return entries


def main():
    universe = load_universe_text(UNIVERSE_PATH)
    print(f'Loaded {len(universe)} unique universe entries from {UNIVERSE_PATH}')

    results = []
    for entry in universe:
        print(f"Processing {entry['name']} / {entry['isin']}...")
        info = get_surface_info(entry)
        results.append({
            'Name': entry['name'],
            'LongName': entry['long_name'],
            'Currency': entry['currency'],
            'ISIN': entry['isin'],
            'InstrumentCode': info['instrument_code'],
            'Status': info['status'],
            'Strikes': info['strikes'],
            'Expiries': info['expiries'],
            'MinExp': info['min_exp'],
            'MaxExp': info['max_exp'],
            'MinStrike': info['min_strike'],
            'MaxStrike': info['max_strike'],
            'Notes': info['notes'],
        })

    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f'Wrote {OUTPUT_PATH}')
    print('Status counts:')
    print(df['Status'].value_counts(dropna=False))


if __name__ == '__main__':
    main()
