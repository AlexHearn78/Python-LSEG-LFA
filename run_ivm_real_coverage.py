import datetime as dt
import math
import time
from pathlib import Path

import pandas as pd

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
except Exception as exc:
    raise RuntimeError(
        'Unable to import lseg_analytics. Live LSEG SDK access is required and no mocks may be used.'
    ) from exc

INPUT_TXT = Path('universe_full.txt')
OVERRIDE_CSV = Path('ric_overrides.csv')
OUTPUT_CSV = Path('coverage_results_may6_2026.csv')
MAPPING_CSV = Path('bbg_to_ric_may6_2026.csv')
PROGRESS_CSV = Path('coverage_progress_may6_2026.csv')

CALC_DATE = dt.datetime(2026, 5, 6)
BATCH_SIZE = 25
BATCH_DELAY_SECONDS = 1.0

KNOWN_INDEX_RICS = {
    'SPX': '.SPX@RIC',
    'NDX': '.NDX@RIC',
    'RTY': '.RUT@RIC',
    'DAX': '.GDAXI@RIC',
    'CAC': '.FCHI@RIC',
    'UKX': '.FTSE@RIC',
    'SX5E': '.STOXX50E@RIC',
    'SXXP': '.STOXX@RIC',
    'NKY': '.N225@RIC',
    'TPX': '.TOPX@RIC',
    'HSI': '.HSI@RIC',
    'HSCEI': '.HSCE@RIC',
    'AS51': '.AXJO@RIC',
    'SMI': '.SSMI@RIC',
    'N225': '.N225@RIC',
    'IBEX': '.IBEX@RIC',
    'KOSPI': '.KS11@RIC',
    'NSEI': '.NSEI@RIC',
    'OMX': '.OMXS30@RIC',
    'STOXX50E': '.STOXX50E@RIC',
    'ESX5': '.STOXX50E@RIC',
    'EUROSTOXX': '.STOXX50E@RIC',
    'EUX': '.STOXX50E@RIC',
    'FTMIB': '.FTMIB@RIC',
    'CCMP': '.IXIC@RIC',
    'DJI': '.DJI@RIC',
    'JKSE': '.JKSE@RIC',
    'SSEC': '.SSEC@RIC',
}

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
            'Name': lines[i],
            'LongName': lines[i + 1],
            'Currency': lines[i + 2],
            'ISIN': lines[i + 3],
        }
        key = (entry['Name'], entry['ISIN'], entry['Currency'])
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    return pd.DataFrame(entries)


def load_overrides(path):
    if not path.exists():
        raise FileNotFoundError(f'Override file not found: {path}')
    overrides = {}
    with open(path, 'r', encoding='utf-8') as f:
        header = f.readline().strip().split(',', 2)
        for line in f:
            if not line.strip():
                continue
            parts = line.rstrip('\n').split(',', 2)
            if len(parts) < 2:
                continue
            key = parts[0].strip()
            override_ric = parts[1].strip()
            if key and override_ric:
                overrides[key] = override_ric
    return overrides

OVERRIDES = load_overrides(OVERRIDE_CSV)

SUFFIX_TO_RIC = {
    'US': ['.P@RIC', '@RIC', '.K@RIC', '.O@RIC', '.N@RIC'],
    'LN': ['.L@RIC'],
    'GB': ['.L@RIC'],
    'GR': ['.DE@RIC'],
    'DE': ['.DE@RIC'],
    'FP': ['.PA@RIC'],
    'FR': ['.PA@RIC'],
    'NA': ['.AS@RIC'],
    'NL': ['.AS@RIC'],
    'SM': ['.MC@RIC'],
    'IM': ['.MI@RIC'],
    'IT': ['.MI@RIC'],
    'SW': ['.S@RIC'],
    'CH': ['.SW@RIC'],
    'HK': ['.HK@RIC'],
    'JP': ['.T@RIC'],
    'AU': ['.AX@RIC'],
    'CN': ['.SS@RIC', '.SZ@RIC'],
    'CA': ['.TO@RIC', '.CN@RIC'],
    'ES': ['.MC@RIC'],
    'KR': ['.KS@RIC'],
    'IN': ['.NS@RIC'],
    'ID': ['.JK@RIC'],
    'PL': ['.WA@RIC'],
    'SE': ['.ST@RIC'],
    'NO': ['.OL@RIC'],
    'DK': ['.CO@RIC'],
    'FI': ['.HE@RIC'],
}

REGION_GROUPS = {
    'Americas': {'US', 'CN', 'CA'},
    'EMEA': {
        'LN', 'GR', 'FP', 'NA', 'SM', 'IM', 'SW', 'BB', 'DC', 'NO', 'SS', 'FH',
        'AV', 'ID', 'IT', 'CP', 'SJ', 'LI', 'GB', 'DE', 'FR', 'NL', 'CH',
    },
    'APAC': {'HK', 'JP', 'AU'},
}

ETF_INDICATORS = ['ETF', 'TRUST', 'FUND', 'SHARES']

US_ETF_SUFFIXES = ['.P@RIC', '@RIC', '.K@RIC', '.O@RIC', '.N@RIC']
US_NON_ETF_SUFFIXES = ['.O@RIC', '.N@RIC', '@RIC']

SURFACE_PARAMS = ev.EtiSurfaceParameters(
    calculation_date=CALC_DATE,
    time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
    input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
    volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
    moneyness_type=ev.MoneynessTypeEnum.SPOT,
    price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
    x_axis=ev.XAxisEnum.STRIKE,
    y_axis=ev.YAxisEnum.DATE,
)
SURFACE_LAYOUT = ev.SurfaceOutput(format=ev.FormatEnum.MATRIX)


def parse_bbg_name(name: str):
    name = str(name).strip()
    parts = name.split()
    if len(parts) <= 1:
        return name, None
    return ' '.join(parts[:-1]), parts[-1]


def classify_instrument(row):
    ticker, suffix = parse_bbg_name(row['Name'])
    long_name = str(row.get('LongName', '') or '')

    if suffix is None:
        if ticker.upper() in KNOWN_INDEX_RICS:
            return 'Index', 'Indices'
        return 'Index', 'Indices'

    if suffix == 'US' and any(tok in long_name.upper() for tok in ETF_INDICATORS):
        type_group = 'US ETF'
    else:
        type_group = 'Single name'

    region = 'Other'
    for group, codes in REGION_GROUPS.items():
        if suffix in codes:
            region = group
            break
    return type_group, region


def normalize_ric_string(ric: str) -> str:
    return str(ric).strip()


def expand_override_candidates(override_ric: str):
    ric = normalize_ric_string(override_ric)
    candidates = [ric]
    upper = ric.upper()

    if upper.endswith('.OQ@RIC'):
        candidates.append(ric[:-len('.OQ@RIC')] + '.O@RIC')
    elif upper.endswith('.OQ') and '^' not in ric:
        base = ric[:-len('.OQ')]
        candidates.append(base + '.O@RIC')
        candidates.append(base + '.O')

    # preserve order and remove duplicates
    return list(dict.fromkeys(candidates))


def build_ric_candidates(name, description=''):
    ticker, suffix = parse_bbg_name(name)
    ticker = ticker.strip()
    if not ticker:
        return []

    key = ticker if suffix is None else f'{ticker} {suffix}'
    key = key.strip()
    if key in OVERRIDES:
        override = OVERRIDES[key]
        return expand_override_candidates(override)

    # strip existing dot-suffix tickers before applying exchange suffix rules
    if '.' in ticker and not ticker.startswith('.'):
        return [ticker + '@RIC']

    # Check for known index using the base ticker name
    index_ticker = ticker.split('.')[0].upper()
    if index_ticker in KNOWN_INDEX_RICS:
        return [KNOWN_INDEX_RICS[index_ticker]]

    if suffix is None or suffix == '':
        return []

    suffix = suffix.upper()
    candidates = []
    if suffix in SUFFIX_TO_RIC:
        if suffix == 'US':
            if any(tok in description.upper() for tok in ETF_INDICATORS):
                suffix_tokens = US_ETF_SUFFIXES
            else:
                suffix_tokens = US_NON_ETF_SUFFIXES
        else:
            suffix_tokens = SUFFIX_TO_RIC[suffix]
        candidates.extend(f'{ticker}{suffix_token}' for suffix_token in suffix_tokens)
    if not candidates:
        candidates.append(f'{ticker}@RIC')
    return candidates


def save_mapping(rows):
    df = pd.DataFrame(rows)
    df.to_csv(MAPPING_CSV, index=False)
    print(f'Wrote {MAPPING_CSV}')


def build_surface_request(ric):
    return ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f'{ric}_test',
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ric),
        surface_parameters=SURFACE_PARAMS,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=SURFACE_LAYOUT,
    )


def parse_surface_response(item):
    if item.surface is None:
        raise ValueError('No surface returned')

    surface = item.surface
    headers = item.headers
    expiry_dates = item.expiry_dates

    if headers is None or expiry_dates is None:
        if not isinstance(surface, list) or not surface or not isinstance(surface[0], list):
            raise ValueError('Unable to parse surface matrix')
        expiry_dates = surface[0][1:]
        strikes = [float(row[0]) for row in surface[1:] if row and len(row) > 1]
        data = [row[1:] for row in surface[1:] if row and len(row) > 1]
        df = pd.DataFrame(data, index=strikes, columns=expiry_dates).T
    else:
        df = pd.DataFrame(surface, index=expiry_dates, columns=headers)

    df.index = pd.to_datetime(df.index, utc=False)
    df.columns = pd.to_numeric(df.columns, errors='coerce')
    spot = float(item.underlying_spot) if item.underlying_spot is not None else 100.0
    return df, spot


def interpolate_term_vol(surface_df, target_days, calc_date, spot):
    if surface_df.empty:
        return None
    target_date = calc_date + dt.timedelta(days=target_days)
    dates = pd.to_datetime(surface_df.index, utc=False)
    dates = dates.sort_values()
    if target_date < dates.min() or target_date > dates.max():
        return None

    atm_strike = surface_df.columns.values
    if len(atm_strike) == 0:
        return None

    if spot in atm_strike:
        atm_col = float(spot)
        atm_series = pd.to_numeric(surface_df[atm_col], errors='coerce')
    else:
        strikes = pd.to_numeric(surface_df.columns, errors='coerce').sort_values()
        lower = strikes[strikes <= spot].max() if any(strikes <= spot) else None
        upper = strikes[strikes >= spot].min() if any(strikes >= spot) else None
        if lower is None or upper is None or math.isnan(lower) or math.isnan(upper):
            return None
        if lower == upper:
            atm_series = pd.to_numeric(surface_df[lower], errors='coerce')
        else:
            lower_series = pd.to_numeric(surface_df[lower], errors='coerce')
            upper_series = pd.to_numeric(surface_df[upper], errors='coerce')
            ratio = (spot - lower) / (upper - lower)
            atm_series = lower_series + ratio * (upper_series - lower_series)

    atm_series.index = dates
    if target_date in atm_series.index:
        return float(atm_series.loc[target_date])

    before = atm_series.index[atm_series.index <= target_date]
    after = atm_series.index[atm_series.index >= target_date]
    if before.empty or after.empty:
        return None
    before_date = before.max()
    after_date = after.min()
    if before_date == after_date:
        return float(atm_series.loc[before_date])

    before_val = float(atm_series.loc[before_date])
    after_val = float(atm_series.loc[after_date])
    total = (after_date - before_date).days
    if total == 0:
        return float(before_val)
    weight = (target_date - before_date).days / total
    return float(before_val + (after_val - before_val) * weight)


def status_from_exception(exc):
    message = str(exc) or ''
    msg_lower = message.lower()
    if '92000' in msg_lower or 'entitlement' in msg_lower:
        return 'ENTITLEMENT_92000'
    if 'no data' in msg_lower or 'no surface' in msg_lower or 'no response data' in msg_lower:
        return 'NO_DATA'
    if 'insufficient' in msg_lower:
        return 'INSUFFICIENT_DATA'
    if 'not found' in msg_lower or 'bad ric' in msg_lower or 'invalid instrument' in msg_lower or 'is not valid' in msg_lower:
        return 'BAD_RIC'
    return 'OTHER'


def build_result_row(row, ric, status, error_code, error_message, metrics):
    result = {
        'bbg_name': row['Name'],
        'isin': row['ISIN'],
        'ric': ric,
        'region': row['region'],
        'country': row['country'],
        'type': row['type'],
        'status': status,
        'error_code': error_code,
        'error_message': error_message,
        'n_strikes': metrics.get('n_strikes'),
        'n_expiries': metrics.get('n_expiries'),
        'min_expiry_days': metrics.get('min_expiry_days'),
        'max_expiry_days': metrics.get('max_expiry_days'),
        'min_strike_pct': metrics.get('min_strike_pct'),
        'max_strike_pct': metrics.get('max_strike_pct'),
        'atm_vol_30d': metrics.get('atm_vol_30d'),
        'atm_vol_90d': metrics.get('atm_vol_90d'),
        'atm_vol_365d': metrics.get('atm_vol_365d'),
    }
    return result


def run_surface_request(request):
    return ev.calculate(universe=[request])


def compute_metrics_from_item(item):
    surface_df, spot = parse_surface_response(item)
    exp_dates = pd.to_datetime(surface_df.index, utc=False)
    min_exp = (exp_dates.min() - CALC_DATE).days
    max_exp = (exp_dates.max() - CALC_DATE).days
    strikes = pd.to_numeric(surface_df.columns, errors='coerce')
    return {
        'n_strikes': int(surface_df.shape[1]),
        'n_expiries': int(surface_df.shape[0]),
        'min_expiry_days': int(min_exp),
        'max_expiry_days': int(max_exp),
        'min_strike_pct': float(strikes.min() / spot * 100) if len(strikes) else None,
        'max_strike_pct': float(strikes.max() / spot * 100) if len(strikes) else None,
        'atm_vol_30d': interpolate_term_vol(surface_df, 30, CALC_DATE, spot),
        'atm_vol_90d': interpolate_term_vol(surface_df, 90, CALC_DATE, spot),
        'atm_vol_365d': interpolate_term_vol(surface_df, 365, CALC_DATE, spot),
    }


def evaluate_requests(entries):
    results = []
    requests = []
    index_to_entry = []

    for entry in entries:
        if entry['resolution_method'] == 'unresolved' or not entry['ric_candidates']:
            results.append(build_result_row(entry, '', 'BAD_RIC', '', 'Unable to resolve a RIC', {}))
            continue
        entry['current_candidate_index'] = 0
        index_to_entry.append(entry)
        requests.append(build_surface_request(entry['ric_candidates'][0]))

    def write_progress():
        pd.DataFrame(results).to_csv(PROGRESS_CSV, index=False)

    for batch_start in range(0, len(index_to_entry), BATCH_SIZE):
        batch_slice = index_to_entry[batch_start:batch_start + BATCH_SIZE]
        batch_requests = [build_surface_request(entry['ric_candidates'][entry['current_candidate_index']]) for entry in batch_slice]
        batch_success = True
        batch_resp = None
        first_batch = batch_start == 0
        first_batch_ok = False

        try:
            batch_resp = ev.calculate(universe=batch_requests)
            if batch_resp is None or not getattr(batch_resp, 'data', None):
                raise RuntimeError('Batch response returned no data')
        except Exception as batch_exc:
            batch_success = False
            print(f'Batch failed for rows {batch_start}-{batch_start+len(batch_slice)-1}: {batch_exc}')

        if batch_success:
            for entry, item in zip(batch_slice, batch_resp.data):
                candidate = entry['ric_candidates'][entry['current_candidate_index']]
                try:
                    if item.surface is None:
                        raise ValueError('No surface returned')
                    metrics = compute_metrics_from_item(item)
                    results.append(build_result_row(entry, candidate, 'OK', '', '', metrics))
                except Exception as item_exc:
                    status = status_from_exception(item_exc)
                    msg = str(item_exc)
                    if entry['current_candidate_index'] + 1 < len(entry['ric_candidates']):
                        entry['current_candidate_index'] += 1
                        try:
                            metrics = process_single_candidate(entry)
                            results.append(metrics)
                            continue
                        except Exception as fallback_exc:
                            status = status_from_exception(fallback_exc)
                            msg = str(fallback_exc)
                    results.append(build_result_row(entry, candidate, status, '', msg, {}))
        else:
            for entry in batch_slice:
                try:
                    if entry['current_candidate_index'] + 1 < len(entry['ric_candidates']):
                        entry['current_candidate_index'] += 1
                    single_result = process_single_candidate(entry)
                    results.append(single_result)
                except Exception as single_exc:
                    status = status_from_exception(single_exc)
                    results.append(build_result_row(entry,
                                                  entry['ric_candidates'][entry['current_candidate_index']],
                                                  status,
                                                  '',
                                                  str(single_exc),
                                                  {}))
        write_progress()
        print(f'Wrote progress for {len(results)} instruments')
        time.sleep(BATCH_DELAY_SECONDS)

    return results


def process_single_candidate(entry):
    for idx in range(entry['current_candidate_index'], len(entry['ric_candidates'])):
        candidate = entry['ric_candidates'][idx]
        request = build_surface_request(candidate)
        try:
            resp = ev.calculate(universe=[request])
            if resp is None or not getattr(resp, 'data', None):
                raise ValueError('No response data returned from single request')
            item = resp.data[0]
            if item.surface is None:
                raise ValueError('No surface returned')
            metrics = compute_metrics_from_item(item)
            return build_result_row(entry, candidate, 'OK', '', '', metrics)
        except Exception as exc:
            status = status_from_exception(exc)
            if status != 'OK' and idx + 1 < len(entry['ric_candidates']):
                continue
            raise
    raise RuntimeError('All candidate RICs failed for this instrument')


def print_summary(results):
    df = pd.DataFrame(results)
    if df.empty:
        print('No results to summarize.')
        return

    df['is_ok'] = df['status'] == 'OK'
    df['is_full_term_ok'] = df['is_ok'] & (df['max_expiry_days'] >= 365)

    def build_summary(index_field):
        total = pd.pivot_table(df, index=index_field, values='bbg_name', aggfunc='count', fill_value=0)
        ok = pd.pivot_table(df[df['is_ok']], index=index_field, values='bbg_name', aggfunc='count', fill_value=0)
        full_term = pd.pivot_table(df[df['is_full_term_ok']], index=index_field, values='bbg_name', aggfunc='count', fill_value=0)
        summary = total.join(ok, rsuffix='_ok').join(full_term, rsuffix='_full').fillna(0)
        summary.columns = ['Total', 'OK', '1Y OK']
        summary['OK %'] = (summary['OK'] / summary['Total'] * 100).round(1)
        summary['1Y OK %'] = (summary['1Y OK'] / summary['Total'] * 100).round(1)
        return summary

    print('\nSummary counts by region:')
    print(build_summary('region'))

    print('\nSummary counts by country:')
    print(build_summary('country'))

    resolved = df[df['status'] != 'BAD_RIC']
    ok = df[df['status'] == 'OK']
    full_term = ok[ok['max_expiry_days'] >= 365]

    total = len(df)
    total_resolved = len(resolved)
    total_ok = len(ok)
    full_term_ok = len(full_term)

    print('\nOverall counts:')
    print(f'  Total instruments: {total}')
    print(f'  RIC resolved: {total_resolved} ({total_resolved/total:.1%})')
    print(f'  Surface OK: {total_ok} ({total_ok/total_resolved:.1%} of resolved)' if total_resolved else '  Surface OK: 0')
    print(f'  Full-term (>=1Y) OK: {full_term_ok} ({full_term_ok/total_ok:.1%} of OK)' if total_ok else '  Full-term (>=1Y) OK: 0')

    if not df.empty:
        print('\nTop 10 failure modes by error message:')
        failure_counts = df[df['status'] != 'OK']['error_message'].value_counts().head(10)
        for msg, count in failure_counts.items():
            print(f'{count}: {msg}')

    print('\nTop failure names for countries with >30% failure rate:')
    country_total = pd.pivot_table(df, index='country', values='bbg_name', aggfunc='count', fill_value=0)
    country_ok = pd.pivot_table(df[df['is_ok']], index='country', values='bbg_name', aggfunc='count', fill_value=0)
    country_summary = pd.DataFrame({
        'Tested': country_total['bbg_name'],
        'OK': country_ok['bbg_name'],
    }).fillna(0)
    country_summary['Fail%'] = (1 - country_summary['OK'] / country_summary['Tested']) * 100
    failing_countries = country_summary[country_summary['Fail%'] > 30].index.tolist()
    for country in failing_countries:
        subset = df[(df['country'] == country) & (df['status'] != 'OK')]
        if subset.empty:
            continue
        print(f'\nCountry {country} top failures:')
        print(subset[['bbg_name', 'ric', 'error_message']].head(5).to_string(index=False))


def main():
    if not INPUT_TXT.exists():
        raise FileNotFoundError(f'Input TXT not found: {INPUT_TXT}')

    df = load_universe_text(INPUT_TXT)
    print(f'Loaded {len(df)} unique universe entries from {INPUT_TXT}')
    if len(df) < 350:
        raise RuntimeError(f'Expected at least 350 unique entries after expansion, got {len(df)}. Universe file may be truncated.')

    rows = []
    mapping_rows = []
    for _, row in df.iterrows():
        ticker, suffix = parse_bbg_name(row['Name'])
        type_group, region = classify_instrument(row)
        ric_candidates = build_ric_candidates(row['Name'], row.get('LongName', ''))
        resolution_method = 'rule' if ric_candidates else 'unresolved'
        primary_ric = ric_candidates[0] if ric_candidates else ''
        rows.append({
            'Name': row['Name'],
            'LongName': row.get('LongName', ''),
            'Currency': row.get('Currency', ''),
            'ISIN': row.get('ISIN', ''),
            'type': type_group,
            'region': region,
            'country': suffix,
            'ric_candidates': ric_candidates,
            'resolution_method': resolution_method,
            'primary_ric': primary_ric,
        })
        mapping_rows.append({
            'bbg_name': row['Name'],
            'isin': row.get('ISIN', ''),
            'ric_attempt': primary_ric,
            'resolution_method': resolution_method,
        })

    stage_counts = pd.crosstab(
        index=[r['region'] for r in rows],
        columns=[r['type'] for r in rows],
        rownames=['Region'],
        colnames=['Type'],
        dropna=False,
    )
    print('Universe counts by region × type:')
    print(stage_counts)

    save_mapping(mapping_rows)
    results = evaluate_requests(rows)
    pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
    if PROGRESS_CSV.exists():
        PROGRESS_CSV.unlink()
    print(f'Wrote {OUTPUT_CSV}')
    print_summary(results)


if __name__ == '__main__':
    main()
