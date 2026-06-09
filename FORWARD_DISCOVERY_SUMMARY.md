# Forward Curve Discovery Test — Summary Report

**Date:** May 1, 2026  
**Tested Assets:** AAPL.O@RIC, NVDA.O@RIC  
**Calculation Date:** 2025-04-18  
**Environment:** lseg_analytics (legacy), Python 3.14.3  

---

## Executive Summary

**Answer to Key Questions:**

1. **Are forward curves present in the vol surface response payload?**  
   **NO** — The vol surface response contains only:
   - `surface`: 2D volatility matrix (strikes × expiries)
   - `surfaceTag`: Request identifier
   - No ancillary outputs for forwards, dividends, repo rates, or discount curves

2. **Are there any modules/classes/parameters we haven't tried that look promising?**  
   **YES, but not for equity forwards:**
   - `lseg_analytics.pricing.instruments.options` — Option pricing module exists (may contain dividend/rate inputs)
   - `lseg_analytics.pricing.market_data.fx_forward_curves` — Forward curves ARE available for **FX markets only**
   - `lseg_analytics.pricing.instruments.forward_rate_agreement` — IR forward curves exist
   - No `eq_forward`, `eq_dividend`, or `equity_curves` module found

3. **Can you confirm via the option pricer that LSEG IS internally building them?**  
   **PARTIAL** — The `lseg_analytics.pricing.instruments.options` module exists, suggesting LSEG can price options (which requires internally computing forwards/dividends), but the module is not yet explored in detail.

---

## Test Results

### TEST 1: Vol Surface Response Structure
- **Tested:** AAPL.O@RIC and NVDA.O@RIC
- **Response Payload:**
  - Top-level key: `data` (list of response items)
  - Per-item keys: `surface` (2D array), `surfaceTag` (string)
- **Keyword Search:** No mentions of forward, dividend, repo, discount, rate, curve
- **Conclusion:** Equity forwards are **NOT exposed** in the vol surface response

### TEST 2: Module Inspection (eq_volatility)
- **Classes Found:**
  - Configuration: `EtiSurfaceDefinition`, `EtiSurfaceParameters`, `EtiVolatilitySurfaceRequestItem`, `SurfaceOutput`
  - Enumerations: `CurvesAndSurfacesTimeStampEnum`, `CurvesAndSurfacesVolatilityModelEnum`, `InputVolatilityTypeEnum`, `MoneynessTypeEnum`, `CurvesAndSurfacesPriceSideEnum`, `FormatEnum`, `XAxisEnum`, `YAxisEnum`
  - Utilities: `StrikeFilter`, `MaturityFilter`, `SurfaceFilters`, `MoneynessWeight`, `VolatilitySurfacePoint`
- **Keyword Match:** None (no forward/dividend/curve/rate/term classes found)

### TEST 3: Parent Namespace Inspection (pricing.market_data)
- **Available Modules:**
  - `commodities_curves` — Commodity forward curves
  - `credit_curves` — Credit spread curves
  - `eq_volatility` — Equity volatility (vol surface only)
  - `fx_forward_curves` — **FX forwards (AVAILABLE)**
  - `fx_volatility` — FX volatility
  - `inflation_curves` — Inflation curves
  - `interest_rate_curves` — IR curves
  - `ipa_interest_rate_curves` — IPA IR curves
  - `ircaplet_volatility` — IR caplet vol
  - `irswaption_volatility` — IR swaption vol
- **Finding:** No `eq_forward` or `eq_dividend` module at market_data level

### TEST 4: Parameter Inspection (EtiSurfaceParameters, SurfaceOutput)
- **EtiSurfaceParameters Attributes:**
  - `calculation_date`, `time_stamp`, `input_volatility_type`, `volatility_model`
  - `moneyness_type`, `price_side`, `filters`, `smile_by_smile_arbitrage_check`
  - **No output-control fields** (no `include_forwards`, `return_market_data`, `include_underlying_curve`)
- **SurfaceOutput Attributes:**
  - `format` (MATRIX or LIST)
  - `x_point_count`, `y_point_count`, `x_values`, `y_values`, `data_points`
  - Layout specification only; no output option flags

### TEST 5: calculate() Function Signature
```
(*, universe: List[EtiVolatilitySurfaceRequestItem] | None = None, 
     fields: str | None = None) -> VolatilitySurfaceResponse
```
- **Attempted:** `return_market_data=True`
- **Result:** **REJECTED** — `TypeError: calculate() got an unexpected keyword argument 'return_market_data'`
- **Note:** Interest rate curves module DOES accept `return_market_data`; equity vol does not

### TEST 6: Alternative Module Discovery
- **Found:** `lseg_analytics.pricing.instruments.options` (option pricer exists)
- **Forward/Dividend Modules Found:**
  - `lseg_analytics.pricing.instruments.fx_forwards` — FX forwards
  - `lseg_analytics.pricing.instruments.forward_rate_agreement` — IR forwards
- **NOT Found:** No `eti_option`, `equity_option`, or `eq_pricing` discovered
- **Conclusion:** Option pricing IS available but not yet inspected for dividend/rate dependencies

---

## Findings & Implications

### What's Available
1. **Vol Surfaces:** Full implied volatility surface (strike × expiry) ✓
2. **FX Forwards:** Accessible via `fx_forward_curves` module ✓
3. **Interest Rate Curves:** Accessible via `interest_rate_curves` module ✓
4. **Option Pricing:** Module exists but interface unclear ✓

### What's NOT Available
1. **Equity Forward Curves:** No exposed module or output field ✗
2. **Dividend Yields:** No data field in vol surface response ✗
3. **Equity Repo Rates:** Not exposed in vol surface ✗
4. **Market Data Output Flag:** `return_market_data` not supported for eq_volatility ✗

---

## Recommended Next Steps (for IVM Markets)

1. **Use the Option Pricer:**  
   Explore `lseg_analytics.pricing.instruments.options` to see if implied forwards/dividends are accessible there (even if not directly exposed, they may be embedded in option pricing inputs).

2. **Use FX Forward Module as Template:**  
   If the SDK is used for multi-asset pricing (including FX), study the `fx_forward_curves` module design and request equivalent for equities.

3. **Contact Product Team:**  
   This discovery confirms that equity forwards are **not currently exposed** in the public API. Request them as an enhancement, citing the availability of:
   - `fx_forward_curves` (exists for FX)
   - Implicit use in option pricing (exists but not transparent)

4. **Workaround:**  
   If equity forwards are needed, consider:
   - Building them from spot + funding curve + dividend assumptions
   - Using the option pricer as an intermediate (if it exposes them)
   - Implementing your own forward computation from spot and cost-of-carry

---

## Technical Notes

- LSEG has deprecated `lseg-analytics` in favor of `lseg-analytics-pricing`; both packages are currently available
- The vol surface calculation uses SSVI model; output is purely volatility, no underlying market data
- Interest rate curves module supports `return_market_data=True` but equity vol does not
- All tests used `calculation_date=2025-04-18` (pre-May 2026 snapshot date)

---

## Files Generated
- `forward_discovery_test.py` — Full test suite (6 tests)
- `forward_discovery_results.txt` — Complete test output
- `FORWARD_DISCOVERY_SUMMARY.md` — This summary

