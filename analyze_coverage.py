import pandas as pd
from collections import Counter
import datetime as dt

# Load the CSV
df = pd.read_csv('/Users/alexanderhearn/Desktop/PythonLSEGV2/coverage_results_v2.csv')

print("=" * 80)
print("COVERAGE RESULTS ANALYSIS - April 18, 2025")
print("=" * 80)

# Overall statistics
total = len(df)
ok_count = (df['status'] == 'OK').sum()
other_count = (df['status'] == 'OTHER').sum()

print(f"\nTotal instruments: {total}")
print(f"Status = OK: {ok_count} ({100*ok_count/total:.1f}%)")
print(f"Status = OTHER (failures): {other_count} ({100*other_count/total:.1f}%)")

# Analyze error messages for failures
failures = df[df['status'] == 'OTHER'].copy()
print(f"\n" + "=" * 80)
print("FAILURE BREAKDOWN")
print("=" * 80)

# Categorize failures
def categorize_error(error_msg):
    if pd.isna(error_msg):
        return "EMPTY_ERROR"
    error_msg = str(error_msg).lower()
    
    if "ric is unknown" in error_msg or "underlying ric is unknown" in error_msg:
        return "RIC_UNKNOWN"
    elif "failed to gather enough options" in error_msg:
        return "INSUFFICIENT_OPTIONS"
    elif "json" in error_msg or "expecting value" in error_msg:
        return "JSON_PARSE_ERROR"
    elif "gateway error" in error_msg and "401" in error_msg:
        return "AUTH_GATEWAY_401"
    elif "options available" in error_msg and "cant be used" in error_msg:
        return "OPTIONS_QUALITY"
    else:
        return "OTHER_ERROR"

failures['error_category'] = failures['error_message'].apply(categorize_error)
category_counts = failures['error_category'].value_counts()

print("\nFailure Categories:")
for category, count in category_counts.items():
    pct = 100 * count / len(failures)
    print(f"  {category:30s}: {count:3d} ({pct:5.1f}%)")

# Now group these into RIC issues vs Data issues
ric_issues = (failures['error_category'].isin(['RIC_UNKNOWN'])).sum()
data_issues = (failures['error_category'].isin(['INSUFFICIENT_OPTIONS', 'OPTIONS_QUALITY'])).sum()
technical_issues = (failures['error_category'].isin(['JSON_PARSE_ERROR', 'AUTH_GATEWAY_401', 'EMPTY_ERROR', 'OTHER_ERROR'])).sum()

print(f"\n" + "=" * 80)
print("AGGREGATED FAILURE DRIVERS")
print("=" * 80)
print(f"RIC-related failures (bad RIC):          {ric_issues:3d} ({100*ric_issues/len(failures):5.1f}% of failures)")
print(f"Data-related failures (no/poor data):    {data_issues:3d} ({100*data_issues/len(failures):5.1f}% of failures)")
print(f"Technical errors (API, auth, parsing):   {technical_issues:3d} ({100*technical_issues/len(failures):5.1f}% of failures)")

print(f"\n" + "=" * 80)
print("ANSWER TO USER QUESTION")
print("=" * 80)
print(f"\nOf {total} instruments tested on April 18, 2025:")
print(f"  SUCCESS: {ok_count} surfaces ({100*ok_count/total:.1f}%)")
print(f"  FAILURE: {other_count} surfaces ({100*other_count/total:.1f}%)")
print(f"\nFAILURE ROOT CAUSE SPLIT:")
print(f"  RIC issues (bad ticker):        {ric_issues} ({100*ric_issues/other_count:.1f}% of failures)")
print(f"  No/insufficient data:           {data_issues} ({100*data_issues/other_count:.1f}% of failures)")
print(f"  Technical/gateway/parse errors: {technical_issues} ({100*technical_issues/other_count:.1f}% of failures)")

print(f"\nCONCLUSION:")
print(f"The 60% success rate is NOT purely from RIC issues.")
print(f"{data_issues} failures ({100*data_issues/other_count:.1f}% of failures) = insufficient options data")
print(f"{ric_issues} failures ({100*ric_issues/other_count:.1f}% of failures) = bad RIC mappings")
print(f"{technical_issues} failures ({100*technical_issues/other_count:.1f}% of failures) = API/technical errors")
