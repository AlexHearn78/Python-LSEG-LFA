"""
Forward Curve Test — Confirming the outputs parameter
Tests whether the vol surface request accepts outputs array with ForwardCurve, etc.
"""

import json
import datetime as dt
import inspect
import math
from lseg_analytics.pricing.market_data import eq_volatility as ev

print("="*80)
print("FORWARD CURVE TEST — Outputs Parameter Validation")
print("="*80)

# ============================================================================
# TEST 1: Find where outputs parameter lives
# ============================================================================
print("\n" + "="*80)
print("TEST 1: Inspect signatures and attributes for 'outputs' parameter")
print("="*80)

print("\n=== calculate() signature ===")
sig = inspect.signature(ev.calculate)
print(sig)

print("\n=== EtiVolatilitySurfaceRequestItem.__init__() signature ===")
try:
    sig = inspect.signature(ev.EtiVolatilitySurfaceRequestItem.__init__)
    print(sig)
except Exception as e:
    print(f"Error: {e}")

print("\n=== EtiSurfaceParameters.__init__() signature ===")
try:
    sig = inspect.signature(ev.EtiSurfaceParameters.__init__)
    print(sig)
except Exception as e:
    print(f"Error: {e}")

print("\n=== SurfaceOutput.__init__() signature ===")
try:
    sig = inspect.signature(ev.SurfaceOutput.__init__)
    print(sig)
except Exception as e:
    print(f"Error: {e}")

print("\n=== EtiVolatilitySurfaceRequestItem attributes ===")
req_attrs = [a for a in dir(ev.EtiVolatilitySurfaceRequestItem) if not a.startswith('_')]
for attr in req_attrs:
    if any(kw in attr.lower() for kw in ['output', 'return', 'additional']):
        print(f">>> {attr} <<<")
if not any(any(kw in a.lower() for a in req_attrs) for kw in ['output', 'return', 'additional']):
    print("(No output-related attributes found)")
print(f"Sample: {req_attrs[:10]}")

print("\n=== EtiSurfaceParameters attributes ===")
param_attrs = [a for a in dir(ev.EtiSurfaceParameters) if not a.startswith('_')]
for attr in param_attrs:
    if any(kw in attr.lower() for kw in ['output', 'return', 'additional']):
        print(f">>> {attr} <<<")
if not any(any(kw in a.lower() for a in param_attrs) for kw in ['output', 'return', 'additional']):
    print("(No output-related attributes found)")
print(f"Sample: {param_attrs[:10]}")

print("\n=== SurfaceOutput attributes ===")
output_attrs = [a for a in dir(ev.SurfaceOutput) if not a.startswith('_')]
for attr in output_attrs:
    if any(kw in attr.lower() for kw in ['output', 'return', 'additional']):
        print(f">>> {attr} <<<")
if not any(any(kw in a.lower() for a in output_attrs) for kw in ['output', 'return', 'additional']):
    print("(No output-related attributes found)")
print(f"Sample: {output_attrs[:10]}")

# ============================================================================
# TEST 2: Build request with outputs and inspect response
# ============================================================================
print("\n" + "="*80)
print("TEST 2: Build request with outputs parameter")
print("="*80)

for ticker in ["AAPL.O@RIC", "NVDA.O@RIC"]:
    print(f"\n--- Testing {ticker} ---")
    
    try:
        surface_definition = ev.EtiSurfaceDefinition(instrument_code=ticker)
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2025, 4, 18),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ticker.split('.')[0]}_with_outputs",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        # Try setting outputs on the request item
        outputs_list = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve", "SurfaceInformation"]
        
        print(f"\nAttempting to set outputs = {outputs_list}")
        
        try:
            request_item.outputs = outputs_list
            print("✓ Successfully set .outputs on request_item")
        except AttributeError as e:
            print(f"✗ Cannot set .outputs on request_item: {e}")
            # Try creating it as a new attribute
            try:
                setattr(request_item, 'outputs', outputs_list)
                print("✓ Set via setattr()")
            except Exception as e2:
                print(f"✗ setattr() also failed: {e2}")
        
        # Execute the request
        print(f"\nExecuting calculate()...")
        response = ev.calculate(universe=[request_item])
        
        print("\n=== TOP-LEVEL response keys ===")
        if hasattr(response, 'keys'):
            print(list(response.keys()))
        else:
            print([x for x in dir(response) if not x.startswith('_')][:20])
        
        print("\n=== response['data'][0] keys ===")
        data_item = response['data'][0] if hasattr(response, '__getitem__') else response.data[0]
        if hasattr(data_item, 'keys'):
            data_keys = list(data_item.keys())
            print(data_keys)
        else:
            data_keys = [x for x in dir(data_item) if not x.startswith('_')]
            print(data_keys[:20])
        
        # Search for forward-related keys
        forward_found = False
        print("\n=== Searching for forward curve data ===")
        for key in ['forwardCurve', 'forward_curve', 'ForwardCurve', 'forwards', 'forward']:
            if key in data_keys or (hasattr(data_item, key)):
                forward_found = True
                print(f"✓ Found {key}")
                try:
                    val = data_item[key] if hasattr(data_item, '__getitem__') else getattr(data_item, key)
                    print(f"  Type: {type(val)}")
                    if isinstance(val, (list, dict)):
                        print(f"  Content (first 2000 chars): {str(val)[:2000]}")
                except Exception as e:
                    print(f"  Error accessing: {e}")
        
        if not forward_found:
            print("✗ No forward curve key found in response")
        
        # Search for interest rate curve
        print("\n=== Searching for interest rate curve data ===")
        rate_found = False
        for key in ['interestRateCurve', 'interest_rate_curve', 'InterestRateCurve', 'rates', 'rate_curve']:
            if key in data_keys or (hasattr(data_item, key)):
                rate_found = True
                print(f"✓ Found {key}")
                try:
                    val = data_item[key] if hasattr(data_item, '__getitem__') else getattr(data_item, key)
                    print(f"  Type: {type(val)}")
                    if isinstance(val, (list, dict)):
                        print(f"  Content (first 2000 chars): {str(val)[:2000]}")
                except Exception as e:
                    print(f"  Error accessing: {e}")
        
        if not rate_found:
            print("✗ No interest rate curve found in response")
        
        # Search for spot
        print("\n=== Searching for underlying spot ===")
        spot_found = False
        for key in ['underlyingSpot', 'underlying_spot', 'UnderlyingSpot', 'spot', 'underlyingPrice']:
            if key in data_keys or (hasattr(data_item, key)):
                spot_found = True
                print(f"✓ Found {key}")
                try:
                    val = data_item[key] if hasattr(data_item, '__getitem__') else getattr(data_item, key)
                    print(f"  Value: {val}")
                except Exception as e:
                    print(f"  Error accessing: {e}")
        
        if not spot_found:
            print("✗ No underlying spot found in response")
        
    except Exception as e:
        print(f"TEST 2 FAILED for {ticker}: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# TEST 3: Validate forward curve values
# ============================================================================
print("\n" + "="*80)
print("TEST 3: Sanity-check forward curve values")
print("="*80)

try:
    # Rerun for AAPL to extract actual values
    surface_definition = ev.EtiSurfaceDefinition(instrument_code="AAPL.O@RIC")
    surface_parameters = ev.EtiSurfaceParameters(
        calculation_date=dt.datetime(2025, 4, 18),
        time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
        volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
        moneyness_type=ev.MoneynessTypeEnum.SPOT,
        price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
        x_axis=ev.XAxisEnum.STRIKE,
        y_axis=ev.YAxisEnum.DATE,
    )
    
    request_item = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag="AAPL_validation",
        underlying_definition=surface_definition,
        surface_parameters=surface_parameters,
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    # Set outputs
    try:
        request_item.outputs = ["Data", "UnderlyingSpot", "InterestRateCurve", "ForwardCurve"]
    except:
        pass
    
    response = ev.calculate(universe=[request_item])
    data = response['data'][0]
    
    # Extract spot, forward, rates
    spot = None
    forwards = None
    rates = None
    
    # Try to get spot
    for key in ['underlyingSpot', 'underlying_spot', 'UnderlyingSpot', 'spot']:
        if key in data:
            spot = data[key]
            print(f"Spot (from {key}): {spot}")
            break
    
    # Try to get forwards
    for key in ['forwardCurve', 'forward_curve', 'ForwardCurve', 'forwards']:
        if key in data:
            forwards = data[key]
            print(f"\nForwards data found (key: {key})")
            print(f"Type: {type(forwards)}")
            if isinstance(forwards, dict):
                print(f"Keys: {list(forwards.keys())[:10]}")
            elif isinstance(forwards, list):
                print(f"Length: {len(forwards)}")
                if forwards and isinstance(forwards[0], dict):
                    print(f"First item keys: {list(forwards[0].keys())}")
            break
    
    # Try to get rates
    for key in ['interestRateCurve', 'interest_rate_curve', 'InterestRateCurve', 'rates']:
        if key in data:
            rates = data[key]
            print(f"\nInterest rate curve found (key: {key})")
            print(f"Type: {type(rates)}")
            if isinstance(rates, dict):
                print(f"Keys: {list(rates.keys())[:10]}")
            elif isinstance(rates, list):
                print(f"Length: {len(rates)}")
                if rates and isinstance(rates[0], dict):
                    print(f"First item keys: {list(rates[0].keys())}")
            break
    
    if spot and forwards and rates:
        print("\n=== Forward Curve Validation Table ===")
        print("Date         | T(yr)  | Forward | Spot   | OIS_Rate | r_implied | q+repo")
        print("-" * 75)
        
        # Try to extract and compute values
        if isinstance(forwards, list):
            for fwd_item in forwards[:5]:  # First 5 items
                try:
                    # Extract date and forward value
                    fwd_date = fwd_item.get('date') or fwd_item.get('maturityDate') or fwd_item.get('tenor')
                    fwd_value = fwd_item.get('value') or fwd_item.get('forward') or fwd_item.get('price')
                    
                    if fwd_date and fwd_value:
                        # Find corresponding rate
                        ois_rate = None
                        if isinstance(rates, list):
                            for rate_item in rates:
                                rate_date = rate_item.get('date') or rate_item.get('maturityDate')
                                if rate_date and rate_date == fwd_date:
                                    ois_rate = rate_item.get('value') or rate_item.get('rate')
                                    break
                        
                        # Compute T and implied rate
                        try:
                            calc_date = dt.datetime(2025, 4, 18)
                            if isinstance(fwd_date, str):
                                fwd_dt = dt.datetime.fromisoformat(fwd_date.split('T')[0])
                            else:
                                fwd_dt = fwd_date
                            T = (fwd_dt - calc_date).days / 365.25
                            
                            if T > 0 and float(spot) > 0:
                                r_implied = math.log(float(fwd_value) / float(spot)) / T
                                q_repo = (ois_rate if ois_rate else 0) - r_implied if ois_rate else None
                                
                                print(f"{str(fwd_date)[:10]} | {T:6.3f} | {float(fwd_value):7.2f} | {float(spot):6.2f} | {(ois_rate or 0):8.4f} | {r_implied:9.4f} | {(q_repo or 0):7.4f}")
                        except Exception as e:
                            print(f"Computation error: {e}")
                except Exception as e:
                    pass

except Exception as e:
    print(f"TEST 3 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 4: Check for dividend outputs
# ============================================================================
print("\n" + "="*80)
print("TEST 4: Test for dividend-related outputs")
print("="*80)

dividend_names = ["DividendCurve", "Dividends", "ImpliedDividends", "DividendSchedule", 
                  "Div", "ImpliedDividendCurve", "DividendTable", "DividendYield",
                  "dividend_curve", "implied_dividends"]

for output_name in dividend_names:
    try:
        surface_definition = ev.EtiSurfaceDefinition(instrument_code="AAPL.O@RIC")
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2025, 4, 18),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag="test_div",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        try:
            request_item.outputs = ["Data", output_name]
        except:
            pass
        
        response = ev.calculate(universe=[request_item])
        data_keys = list(response['data'][0].keys())
        
        if output_name in data_keys or any(output_name.lower() in k.lower() for k in data_keys):
            print(f"✓ {output_name}: ACCEPTED - response keys: {data_keys}")
        else:
            print(f"✗ {output_name}: not in response (keys: {data_keys})")
    except Exception as e:
        print(f"✗ {output_name}: ERROR - {str(e)[:80]}")

print("\n" + "="*80)
print("FORWARD CURVE TEST COMPLETE")
print("="*80)
