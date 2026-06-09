# Final Dividend / Implied q / Repo Audit

**Generated:** 2026-05-12 22:35:00  
**Test period:** 6 instruments across USD/EUR/GBP, dividend yields 0–9%

---

## Executive Summary

**The IPA surface DOES NOT price dividend yields.** All test instruments show implied dividend yields (q) near 0%, regardless of expected dividend yield (7–9% for T, MO, VOD.L; 0% for GME). The forward curve is calibrated as if the underlying pays no dividends. Discrete dividend schedules are completely unavailable.

---

## Test Setup

| RIC | Company | Expected Div % | Currency | Purpose |
|-----|---------|---|----------|---------|
| T@RIC | AT&T | 7.2 | USD | High-yield US, minimal buyback |
| MO@RIC | Altria | 7.8 | USD | Highest expected yield, minimal buyback |
| BNPP.PA@RIC | BNP Paribas | 5.5 | EUR | Single annual payment, FX test |
| VOD.L@RIC | Vodafone | 9.0 | GBP | Cross-currency, semi-annual |
| GME@RIC | GameStop | 0.0 | USD | No dividend, borrow cost test |
| AAPL.O@RIC | Apple | 0.4 | USD | Buyback-distorted, low div profile |

---

## Dividend Schedule Availability

### Dividends Field Response (all names)

| RIC | Type | Structure | Points |
|-----|------|-----------|--------|
| T@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |
| MO@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |
| BNPP.PA@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |
| VOD.L@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |
| GME@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |
| AAPL.O@RIC | HistoricalYield | DIVTYPE:CONT UI:SEC | 1 |

**Finding:** All names return a continuous yield curve (HistoricalYield) with `DIVTYPE:CONT` tag. No discrete cash dividend schedules are available. The single point in each curve is a zero-yield placeholder (for AAPL, confirmed at 0%).

### DIVTYPE Parameterization Probe

**Available dividend enums in SDK:** None found

**Able to override DIVTYPE in request:** No — the SurfaceParameters class does not expose a dividend-type parameter. The API is committed to continuous-yield mode only.

**Verdict:** API exposes **continuous yield curves only; no discrete dividend data**

---

## Implied q vs Expected Dividend Yield (at ~1Y forward)

| RIC | Currency | Spot | Expected Div % | Implied q % | Residual % |
|-----|----------|------|---|---|---|
| T@RIC | USD | 25.16 | 7.2 | 0.083 | **-7.117** |
| MO@RIC | USD | 53.93 | 7.8 | 0.074 | **-7.726** |
| BNPP.PA@RIC | EUR | 55.76 | 5.5 | 0.052 | **-5.448** |
| VOD.L@RIC | GBP | 124.82 | 9.0 | 0.120 | **-8.880** |
| GME@RIC | USD | 25.46 | 0.0 | 0.074 | **+0.074** |
| AAPL.O@RIC | USD | 293.32 | 0.4 | 0.083 | **-0.317** |

### Key Observations

1. **Implied q is near-zero across ALL names** (~0.07–0.12%, systematic near-zero)
   - For T (7.2% div): got 0.083% → missing 7.1%
   - For MO (7.8% div): got 0.074% → missing 7.7%
   - For VOD.L (9.0% div): got 0.120% → missing 8.9%

2. **Residual is almost exactly the expected dividend yield**
   - T: residual -7.1% ≈ expected div 7.2%
   - MO: residual -7.7% ≈ expected div 7.8%
   - This is not a coincidence; the surface has zero dividend content

3. **Cross-currency pattern is consistent**
   - EUR (BNPP.PA): residual -5.4% (expected 5.5%)
   - GBP (VOD.L): residual -8.9% (expected 9.0%)
   - USD: consistent pattern
   - **Conclusion:** No FX-specific correction; systematic zero-dividend calibration across all currencies

4. **GME test (no dividend, high borrow)**
   - Expected yield: 0%, Implied q: 0.074%
   - Residual is almost zero, matches AAPL (which has minimal dividends)
   - **Conclusion:** Borrow cost is NOT showing up; surface is dividend-only with zero content

---

## Borrow Cost Analysis

### GME Residual vs Dividend Names

| Name | Residual % | Character |
|------|---|---|
| GME | +0.074% | No dividend, hard-to-borrow stock |
| T | -7.117% | High div, normal borrow |
| MO | -7.726% | High div, normal borrow |
| Difference (GME - T) | **7.191 bps** | ← Should show borrow if present |

### Verdict: **Borrow cost is NOT visible**

- If borrow were priced, GME would show a **higher** residual (elevated q due to costs).
- Instead, GME is on the same footing as AAPL: residuals are near zero, matching the pattern of names with minimal expected dividends.
- **Conclusion:** The surface forwards are calibrated as `S × exp(r×T)` with **no equity-specific adjustment** for either dividends or borrow.

---

## Discrete Dividend Schedules

**Result:** UNAVAILABLE

The Dividends field returned by the API contains only:
- Curve type: `HistoricalYield`
- Curve parameters: `DIVTYPE:CONT UI:SEC` (continuous dividend yield by security ID)
- Points: 1 point (zero-yield placeholder for most names; exact value depends on ex-date proximity)

**No ex-dates, payment dates, or cash amounts are provided.** If your models require discrete dividend dates and amounts (e.g., for dividend stripping or trade settlement), they must be sourced separately (FactSet, Bloomberg, LSEG reference-data API).

---

## Repo Module Final Verdict

**Module:** `lseg_analytics.pricing.instruments.repo`

**Type:** Bond repo pricer

**Signature of repo.price:**
```
repo.price(definitions: List[RepoDefinitionInstrument], ...)
```

**Accepts 'instrument_code' parameter:** NO

**Supports equity collateral:** NO

The repo module is designed exclusively for bond collateral (coupons, accruals, settlement conventions). Its `RepoDefinitionInstrument` class can accept arbitrary instrument definitions via kwargs, but will fail at pricing time if passed an equity RIC or will return meaningless results (e.g., treating share price as a bond face value).

**Verdict:** Equity repo pricing is **NOT AVAILABLE** via the LSEG Analytics SDK.

---

## Bottom Line for Client Conversation

### What IPA Does NOT Provide

1. **Discrete dividend schedules.**  
   The API returns only continuous yield curves (DIVTYPE:CONT), a smooth function of time. No ex-dates, record dates, or cash amounts.

2. **Dividend-aware forwards.**  
   The implied q (dividend yield) across all test instruments is near-zero (~0.07%), far below realised yields (7–9% for T, MO, VOD.L). The forward curve is essentially `S × exp(r×T)` with no dividend content.

3. **Equity borrow cost.**  
   GameStop (hard-to-borrow) shows the same near-zero implied q as AAPL and T. Borrow cost is either not priced or is inseparable from the near-zero dividend assumption. Either way, **borrow is not separately visible**.

4. **Equity repo pricing.**  
   The repo module (`lseg_analytics.pricing.instruments.repo`) prices bonds only.

### What IPA Does Provide

1. **Forward curve** calibrated to listed options (useful for surface visualization and option-implied vol studies)
2. **Spot prices** (useful for spot-hedge calculations)
3. **Interest rate curves** (USD OIS, EUR EON, GBP SONIA, etc., valid)
4. **Cross-currency adjustments** (FX forwards appear calibrated correctly despite zero-dividend treatment)

### Recommended Action

If you need dividend-aware pricing:

1. **Source discrete dividends separately** (FactSet, Bloomberg, LSEG reference-data API).
2. **Construct or override the IPA dividend curve** using your own assumptions.
3. **Adjust IPA forwards** upward by the PV of discrete dividends.
4. **Do NOT use IPA's implied q as a measure of realised dividend yield** — it is systematically biased low by 500–800 bps.

The surface is suitable for **volatility surface visualization and option Greeks**, but **not for production equity derivative pricing** requiring dividend accuracy.

---

## Files Generated

- `implied_q_audit_final.csv` — Full results table with residuals
- `audit_summary.md` — This report
