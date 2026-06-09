# Dividend, Discount Curve, Repo Audit

**Generated:** 2026-05-12 19:02:13

## Repo module verdict
- **Module:** `lseg_analytics.pricing.instruments.repo`
- **Verdict:** BOND_REPO_PRICER
- **Implication:** equity-specific borrow data is **NOT AVAILABLE** (bond pricer only)

---

## Dividend schedule (AAPL.O@RIC, val_date=2026-05-10)

### Schema
- **Shape:** nested dict
- **Raw field structure:** ['curveDefinition', 'curveParameters', 'points']

### Discrete cash dividends
- **Count:** 0
- **Last ex-date:** N/A (N/A years out)
- **CSV:** `aapl_dividends_discrete.csv`

### Continuous yield region
- **Count:** 0
- **Coverage:** N/A
- **CSV:** `aapl_dividends_yield.csv`

---

## Curves side-by-side

### Extraction
- **Projection curve (InterestRateCurve):** 33 points
- **Discount curve (DiscountCurve):** 33 points
- **Status:** ✓ Both present

### Alignment
 T_years  projection_pct  discount_pct  diff_bps
0.000000        3.717241      3.717241       0.0
0.002740        3.717241      3.717241       0.0
0.024658        3.743403      3.743403       0.0
0.043836        3.739666      3.739666       0.0
0.090411        3.745466      3.745466       0.0
... (33 rows total)

### Comparison
- **Max divergence:** 0.0 bps
- **Interpretation:** Check DiscountCurve definition

---

## Decomposition reconciliation

### Method A (simple dividend-adjusted q)
`q = r - ln(F/S)/T`

### Method B (PV-of-discrete-divs adjusted)
`F_no_divs = (S - PV(divs)) * exp(r*T)`
`Residual = F_no_divs - F_market`

### Results (sample rows)
    expiry     T  F_market  F_no_divs_pred  pv_divs  residual_F_diff  q_A_method
2026-06-18 0.107   294.475         294.497        0            0.022       0.069
2026-07-17 0.186   295.337         295.374        0            0.037       0.068
2026-08-21 0.282   296.379         296.435        0            0.056       0.067
2026-09-18 0.359   297.215         297.287        0            0.073       0.068
2026-10-16 0.436   298.054         298.144        0            0.090       0.070
2026-11-20 0.532   299.110         299.225        0            0.116       0.073
2026-12-18 0.608   299.964         300.098        0            0.135       0.074
2027-01-15 0.685   300.824         300.975        0            0.152       0.074

### Implied dividend yield (at 1Y)
- **Method A q at ~1Y:** N/A
- **Discrete PV coverage at 1Y:** 0.00

### Reconciliation verdict
- **Match quality:** ⚠ Check residuals in CSV
- **Next step:** Use Method B (discrete-div-adjusted) for decomposition if forward curve is tick-accurate; otherwise use Method A (simple) as fallback

---

## Files generated
- `repo_module_inspection.txt` — full module introspection
- `aapl_dividends_raw.json` — raw Dividends block
- `aapl_dividends_discrete.csv` — parsed cash dividend schedule
- `aapl_dividends_yield.csv` — implied yield curve points
- `aapl_curves_side_by_side.csv` — projection vs discount curves
- `aapl_decomposition_reconciliation.csv` — full decomposition table
- `dividend_discount_repo_audit.md` — this report

---

## Summary
- Repo module: **BOND_REPO_PRICER** → No equity-specific borrow data available from lseg_analytics
- Dividend data: **0 discrete + 0 yield curve points** available via API
- Curves: **33 projection, 33 discount** (aligned)
- Decomposition: Ready for Method B (discrete-adjusted) if residuals are small
