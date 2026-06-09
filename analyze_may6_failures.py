import pandas as pd
import pathlib

# Load May 6 results
df = pd.read_csv('/Users/alexanderhearn/Desktop/PythonLSEGV2/coverage_results_may6_2026.csv')

# Filter failures
failures = df[df['status'] == 'OTHER'].copy()

# More detailed categorization
def detailed_cat(error_msg):
    if pd.isna(error_msg):
        return 'EMPTY_ERROR'
    m = str(error_msg).lower()
    if 'ric is unknown' in m or 'underlying ric is unknown' in m:
        return 'RIC_UNKNOWN_EXPLICIT'
    elif 'failed to gather enough options' in m and 'ric is unknown' not in m:
        return 'INSUFFICIENT_OPTIONS_ONLY'
    elif 'neither mid' in m or 'no other prices' in m:
        return 'PRICING_FILTER_ERROR'
    elif 'number of options' in m and 'below the minimum' in m:
        return 'TOO_FEW_OPTIONS'
    elif 'json' in m or 'expecting value' in m:
        return 'JSON_PARSE_ERROR'
    elif 'gateway error' in m and '401' in m:
        return 'AUTH_GATEWAY_401'
    else:
        return 'OTHER_ERROR'

failures['detailed_cat'] = failures['error_message'].apply(detailed_cat)

print("=" * 80)
print("MAY 6, 2026 FAILURE ANALYSIS")
print("=" * 80)
print(f"Total failures: {len(failures)}")
print()

# Group by detailed category
cat_counts = failures['detailed_cat'].value_counts()
for cat, count in cat_counts.items():
    pct = 100 * count / len(failures)
    print(f"{cat:25s}: {count:3d} ({pct:5.1f}%)")

print()
print("=" * 80)
print("PURE RIC-MAPPING ISSUES (explicit 'RIC unknown')")
print("=" * 80)
ric_unknown = failures[failures['detailed_cat'] == 'RIC_UNKNOWN_EXPLICIT']
print(f"Count: {len(ric_unknown)}")
for _, row in ric_unknown.iterrows():
    print(f"  {row['bbg_name']:15s} {row['ric']:15s} {row['region']:10s} {row['country']:5s}")

print()
print("=" * 80)
print("EXPLICIT PRICING/FILTER ERRORS")
print("=" * 80)
pricing_errors = failures[failures['detailed_cat'].isin(['PRICING_FILTER_ERROR', 'TOO_FEW_OPTIONS'])]
print(f"Count: {len(pricing_errors)}")
for _, row in pricing_errors.iterrows():
    print(f"  {row['bbg_name']:15s} {row['ric']:15s} {row['region']:10s} {row['country']:5s}")

print()
print("=" * 80)
print("AMBIGUOUS 'INSUFFICIENT OPTIONS' (could be RIC or data)")
print("=" * 80)
insuff_options = failures[failures['detailed_cat'] == 'INSUFFICIENT_OPTIONS_ONLY']
print(f"Count: {len(insuff_options)}")
for _, row in insuff_options.iterrows():
    print(f"  {row['bbg_name']:15s} {row['ric']:15s} {row['region']:10s} {row['country']:5s}")