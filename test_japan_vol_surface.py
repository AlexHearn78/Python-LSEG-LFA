import datetime as dt
import json
from pathlib import Path
from lseg_analytics.pricing.market_data import eq_volatility as ev

def try_surface(ric, calc_date):
    surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
    surface_parameters = ev.EtiSurfaceParameters(
        calculation_date=calc_date,
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    request_item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag=f"{ric}_test",
        underlying_definition=surface_definition,
        surface_parameters=surface_parameters,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    # KEY STEP: Add outputs via dict interface (discovered in forward_curve_implementation.py)
    request_item['outputs'] = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]

    try:
        response = ev.calculate(universe=[request_item])
        data = response['data'][0]
        if 'surface' in data and data['surface']:
            return ('OK', response, None)
        else:
            return ('NO_SURFACE', response, 'Surface key missing or empty')
    except Exception as e:
        return ('ERROR', None, str(e))

# Use a recent settled Friday - 2026-05-02 (Friday)
calc_date = dt.datetime(2026, 5, 2)

print("=== Testing iShares Core MSCI Japan IMI UCITS ETF ===")
print(f"Calculation date: {calc_date.date()}")

# Step 1: Try UCITS ETF candidates
ucits_candidates = [
    "IJPA.L@RIC",      # London listing of iShares Core MSCI Japan IMI UCITS
    "SJPA.L@RIC",      # Alternate iShares Japan UCITS share class
    "EUNN.DE@RIC",     # Xetra listing of iShares MSCI Japan UCITS
    "SXR8.DE@RIC",     # Alternate Xetra RIC
    "IJPA.AS@RIC",     # Amsterdam listing
    "ICJPN.MI@RIC",    # Milan listing
]

successful_response = None
successful_ric = None
is_ucits = False

for ric in ucits_candidates:
    status, response, err = try_surface(ric, calc_date)
    print(f"\n=== {ric}: {status} ===")
    if err:
        print(f"  Error: {err}")
    if status == 'OK':
        print(f"  ✓ Surface returned. Stopping at this RIC.")
        successful_response = response
        successful_ric = ric
        is_ucits = True
        break

# Step 2: Fallback to EWJ if all UCITS variants fail
if not successful_response:
    print("\n=== All UCITS candidates failed. Trying EWJ fallback ===")
    ewj_candidates = ["EWJ.P@RIC", "EWJ@RIC", "EWJ.K@RIC"]
    for ric in ewj_candidates:
        status, response, err = try_surface(ric, calc_date)
        print(f"\n=== {ric}: {status} ===")
        if err:
            print(f"  Error: {err}")
        if status == 'OK':
            print(f"  ✓ EWJ surface returned. This is the US-listed equivalent.")
            successful_response = response
            successful_ric = ric
            is_ucits = False
            break

if not successful_response:
    print("\n!!! No RIC returned a surface for either UCITS ETF or EWJ fallback !!!")
    exit(1)

# Save the response
filename = "japan_ucits_response.json" if is_ucits else "ewj_response.json"
with open(filename, 'w') as f:
    json.dump(successful_response, f, indent=2, default=str)
print(f"\nSaved response to {filename}")

# Step 3: Extract and display the forward curve
data = successful_response['data'][0]
print("\n=== Top-level keys returned ===")
print(list(data.keys()))

# Forward curve
if 'forwardCurve' in data:
    fc = data['forwardCurve']
    print("\n=== Forward Curve ===")
    print(f"Curve structure: {fc.get('curveStructure', 'N/A')}")
    print(f"Number of forward points: {len(fc.get('dataPoints', {}))}")
    print("\nFirst 10 forward points:")
    for date, fwd in list(fc.get('dataPoints', {}).items())[:10]:
        print(f"  {date}: {fwd:.4f}")
    print("\nLast 5 forward points:")
    for date, fwd in list(fc.get('dataPoints', {}).items())[-5:]:
        print(f"  {date}: {fwd:.4f}")
else:
    print("\n!!! No forwardCurve key in response !!!")
    print("This means either:")
    print("  - The outputs parameter wasn't accepted by this SDK version")
    print("  - The forward curve isn't computed for this underlying")

# Spot
if 'underlyingSpot' in data:
    spot = data['underlyingSpot']
    if isinstance(spot, dict):
        spot = spot.get('value', spot)
    print(f"\n=== Underlying Spot: {spot} ===")

# Interest rate curve
if 'interestRateCurve' in data:
    irc = data['interestRateCurve']
    print(f"\n=== Interest Rate Curve ===")
    print(f"Currency / curve type: {list(irc.get('multiCurve', {}).keys())}")
    # Print a few key tenors
    ois = irc.get('multiCurve', {}).get('OIS', [])
    for point in ois[:5]:
        print(f"  {point.get('tenor')}: {point.get('ratePercent')}% (DF: {point.get('discountFactor')})")

# Step 4: Sanity check the forward curve
import math

if 'forwardCurve' in data and 'underlyingSpot' in data and 'interestRateCurve' in data:
    spot = data['underlyingSpot']
    if isinstance(spot, dict):
        spot = spot.get('value', spot)

    fc_points = data['forwardCurve']['dataPoints']

    # For each forward point, back out implied (r - q - repo)
    print("\n=== Forward curve implied carry check ===")
    print(f"Spot: {spot}")
    print(f"{'Date':<15} {'T (yrs)':<10} {'Forward':<12} {'r_implied':<12}")

    calc = calc_date
    for date_str, fwd in list(fc_points.items())[:8]:
        fwd_date = dt.datetime.strptime(date_str, "%Y-%m-%d")
        T = (fwd_date - calc).days / 365
        if T > 0 and spot > 0:
            r_implied = math.log(fwd / spot) / T
            print(f"{date_str:<15} {T:<10.3f} {fwd:<12.4f} {r_implied*100:<12.4f}%")

# Final summary
print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)
print(f"1. RIC that returned surface: {successful_ric}")
print(f"2. Is this the originally-requested UCITS ETF? {'YES' if is_ucits else 'NO (EWJ fallback)'}")
print(f"3. Forward curve successfully exposed: {'YES' if 'forwardCurve' in data else 'NO'}")
if 'forwardCurve' in data:
    num_points = len(data['forwardCurve'].get('dataPoints', {}))
    print(f"4. Number of forward curve points: {num_points}")

    # 1-year point
    one_year_date = (calc_date + dt.timedelta(days=365)).strftime("%Y-%m-%d")
    if one_year_date in data['forwardCurve']['dataPoints']:
        fwd_1y = data['forwardCurve']['dataPoints'][one_year_date]
        spot = data['underlyingSpot']
        if isinstance(spot, dict):
            spot = spot.get('value', spot)
        if spot > 0:
            r_implied_1y = math.log(fwd_1y / spot) / 1.0
            print(f"5. Implied carry rate at 1-year point: {r_implied_1y*100:.2f}% (sensible range: -1% to +3% for Japan equity)")
        else:
            print("5. Cannot calculate 1-year carry (spot unavailable)")
    else:
        print("5. No 1-year point available in forward curve")
else:
    print("4. Number of forward curve points: 0")
    print("5. Implied carry rate: N/A")

print(f"6. Usable result for client: {'YES' if 'forwardCurve' in data and len(data.get('forwardCurve', {}).get('dataPoints', {})) > 0 else 'NO'}")