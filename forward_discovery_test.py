"""
Forward Curve Discovery Test — IVM Markets follow-up
Tests whether equity forward curves are accessible through lseg_analytics
"""

import json
import datetime as dt
import inspect
import sys

print("="*80)
print("FORWARD CURVE DISCOVERY TEST")
print("="*80)

# ============================================================================
# TEST 1: Inspect vol surface response for ancillary outputs
# ============================================================================
print("\n" + "="*80)
print("TEST 1: Inspect vol surface response for ancillary outputs")
print("="*80)

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    
    for ticker in ["AAPL.O@RIC", "NVDA.O@RIC"]:
        print(f"\n--- Testing {ticker} ---")
        
        req = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ticker.split('.')[0]}_discovery",
            underlying_definition=ev.EtiSurfaceDefinition(instrument_code=ticker),
            surface_parameters=ev.EtiSurfaceParameters(
                calculation_date=dt.datetime(2025, 4, 18),
                time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
                input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
                volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
                moneyness_type=ev.MoneynessTypeEnum.SPOT,
                price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
                x_axis=ev.XAxisEnum.STRIKE,
                y_axis=ev.YAxisEnum.DATE,
            ),
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        response = ev.calculate(universe=[req])
        
        print("\n=== TOP-LEVEL response keys ===")
        if hasattr(response, 'keys'):
            print(list(response.keys()))
        else:
            print([x for x in dir(response) if not x.startswith('_')])
        
        print("\n=== response['data'][0] keys ===")
        data_item = response['data'][0] if hasattr(response, '__getitem__') else response.data[0]
        if hasattr(data_item, 'keys'):
            print(list(data_item.keys()))
        else:
            print([x for x in dir(data_item) if not x.startswith('_')])
        
        print("\n=== Full response['data'][0] (truncated to 10000 chars) ===")
        try:
            full_json = json.dumps(data_item, indent=2, default=str)[:10000]
            print(full_json)
        except Exception as e:
            print(f"Could not serialize: {e}")
            print(str(data_item)[:10000])
        
        print("\n=== Searching for forward/dividend/repo/rate keywords ===")
        try:
            full_text = json.dumps(response, default=str).lower()
            keywords = ['forward', 'fwd', 'dividend', 'div_', 'repo', 'borrow', 'discount', 'risk_free', 'curve']
            found_any = False
            for keyword in keywords:
                if keyword in full_text:
                    found_any = True
                    idx = 0
                    count = 0
                    print(f"\n  Keyword '{keyword}' found:")
                    while count < 3:
                        i = full_text.find(keyword, idx)
                        if i == -1:
                            break
                        context = full_text[max(0,i-50):i+100]
                        print(f"    [{count+1}] pos {i}: ...{context}...")
                        idx = i + 1
                        count += 1
            if not found_any:
                print("  No forward/dividend/repo/rate keywords found in response")
        except Exception as e:
            print(f"  Error searching keywords: {e}")

except Exception as e:
    print(f"TEST 1 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 2: Inspect eq_volatility module for hidden classes
# ============================================================================
print("\n" + "="*80)
print("TEST 2: Inspect eq_volatility module for hidden classes")
print("="*80)

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    
    print("\n=== All members of eq_volatility ===")
    members = []
    for name, obj in inspect.getmembers(ev):
        if not name.startswith('_'):
            kind = type(obj).__name__
            members.append(f"  {name}: {kind}")
            if any(kw in name.lower() for kw in ['forward', 'dividend', 'curve', 'rate', 'term']):
                print(f">>> {name}: {kind} <<<")
    
    if not any('>>>' in m for m in members):
        print("  [No forward/dividend/curve/rate/term keywords found]")
        print("\n  Sample members:")
        for m in members[:20]:
            print(m)

except Exception as e:
    print(f"TEST 2 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 3: Inspect parent pricing.market_data namespace
# ============================================================================
print("\n" + "="*80)
print("TEST 3: Inspect parent pricing.market_data namespace")
print("="*80)

try:
    from lseg_analytics.pricing import market_data
    import pkgutil
    
    print("\n=== Submodules under pricing.market_data ===")
    submodules = []
    for finder, name, ispkg in pkgutil.iter_modules(market_data.__path__):
        kind = "package" if ispkg else "module"
        submodules.append(f"  {name} ({kind})")
        if any(kw in name.lower() for kw in ['forward', 'dividend', 'curve', 'rate', 'eq', 'equity']):
            print(f">>> {name} ({kind}) <<<")
    
    if not any('>>>' in s for s in submodules):
        print("  [No equity/forward/dividend modules found]")
        print("\n  Available modules:")
        for s in submodules:
            print(s)

except Exception as e:
    print(f"TEST 3 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 4: Check EtiSurfaceParameters for output-control fields
# ============================================================================
print("\n" + "="*80)
print("TEST 4: Check EtiSurfaceParameters for output-control fields")
print("="*80)

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    
    print("\n=== EtiSurfaceParameters constructor signature ===")
    sig = inspect.signature(ev.EtiSurfaceParameters.__init__)
    print(sig)
    
    print("\n=== EtiSurfaceParameters all attributes ===")
    attrs = [x for x in dir(ev.EtiSurfaceParameters) if not x.startswith('_')]
    for attr in attrs:
        if any(kw in attr.lower() for kw in ['forward', 'dividend', 'curve', 'rate', 'return', 'output', 'include']):
            print(f">>> {attr} <<<")
    if not any(any(kw in a.lower() for a in attrs) for kw in ['forward', 'dividend', 'curve', 'rate']):
        print("  [No forward/dividend/curve/rate attributes found]")
        print(f"  Attributes: {attrs[:15]}")
    
    print("\n=== EtiVolatilitySurfaceRequestItem signature ===")
    sig = inspect.signature(ev.EtiVolatilitySurfaceRequestItem.__init__)
    print(sig)
    
    print("\n=== SurfaceOutput signature ===")
    sig = inspect.signature(ev.SurfaceOutput.__init__)
    print(sig)

except Exception as e:
    print(f"TEST 4 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 5: Check calculate() function for undocumented parameters
# ============================================================================
print("\n" + "="*80)
print("TEST 5: Check calculate() function for undocumented parameters")
print("="*80)

try:
    from lseg_analytics.pricing.market_data import eq_volatility as ev
    
    print("\n=== ev.calculate() signature ===")
    sig = inspect.signature(ev.calculate)
    print(sig)
    
    # Try with return_market_data if such a param exists
    print("\n=== Attempting to call with return_market_data=True ===")
    req = ev.EtiVolatilitySurfaceRequestItem(
        surface_tag="test_md",
        underlying_definition=ev.EtiSurfaceDefinition(instrument_code="AAPL.O@RIC"),
        surface_parameters=ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2025, 4, 18),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        ),
        underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
        surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
    )
    
    try:
        response = ev.calculate(universe=[req], return_market_data=True)
        print("✓ return_market_data=True ACCEPTED!")
        print("Response keys:", list(response.keys()) if hasattr(response, 'keys') else dir(response))
        if hasattr(response, 'data'):
            print("Data item keys:", list(response.data[0].keys()) if hasattr(response.data[0], 'keys') else dir(response.data[0]))
    except TypeError as e:
        print(f"✗ return_market_data not accepted: {e}")

except Exception as e:
    print(f"TEST 5 FAILED: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 6: Try to find option pricing and dividend/rate inputs
# ============================================================================
print("\n" + "="*80)
print("TEST 6: Try to find option pricing and dividend/rate inputs")
print("="*80)

try:
    import lseg_analytics
    import pkgutil
    
    print("\n=== Searching for forward/dividend/option/eti/eq/equity modules ===")
    found_modules = []
    for finder, name, ispkg in pkgutil.walk_packages(lseg_analytics.__path__, prefix='lseg_analytics.'):
        if any(kw in name.lower() for kw in ['forward', 'dividend', 'option', 'eti', 'eq', 'equity']):
            found_modules.append(name)
            print(f">>> {name}")
    
    if not found_modules:
        print("  [No matching modules found]")
    
    # Try to import option pricer if it exists
    print("\n=== Attempting to import option pricing modules ===")
    option_paths = [
        'lseg_analytics.pricing.financial_contracts.option_value',
        'lseg_analytics.pricing.financial_contracts.eti_option',
        'lseg_analytics.pricing.financial_contracts',
    ]
    
    for path in option_paths:
        try:
            parts = path.split('.')
            mod = __import__(path, fromlist=[parts[-1]])
            print(f"✓ {path} imported successfully")
            print(f"  Contents: {[x for x in dir(mod) if not x.startswith('_')][:10]}")
        except ImportError:
            print(f"✗ {path} not found")

except Exception as e:
    print(f"TEST 6 FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("DISCOVERY TEST COMPLETE")
print("="*80)
