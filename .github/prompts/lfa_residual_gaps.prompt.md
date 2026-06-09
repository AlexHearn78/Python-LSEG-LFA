# LFA Residual Gap Probe — Copilot Chat Prompt
# Save to .github/prompts/lfa_residual_gaps.prompt.md
# Reference in chat: attach via paperclip → "Prompt..." or type #lfa_residual_gaps
#
# WHEN TO USE THIS PROMPT
# Use this prompt — NOT lfa_gap_test_harness.prompt.md — when working on the
# focused residual gap tests. The main harness covers the full 27-pair universe.
# This prompt covers the six instruments and one endpoint question that remained
# unresolved after the live Claude connector assessment on 28 May 2026.

---

## Environment state (already established — do not re-probe)

The VS Code session has already confirmed the following. Do not re-run these
discovery steps when responding:

- `lseg_analytics` SDK is installed and importable
- `lseg.data` (lseg-data) is installed and importable
- `requests` and `python-dotenv` are available
- `.env.example` exists in the repo root; `.env` may or may not be populated
- Auth state is uncertain until a live call succeeds or returns 401/403
- Existing harness lives at `workflows/lfa_gap_test_harness.py`
- Repo convention: synchronous Python, `post()`/`get()` helper pattern,
  `result_summary()` for output, `time.sleep(0.3)` after per-instrument loops

The new file for residual gap tests is `workflows/lfa_residual_gaps.py`.
It must follow the same conventions as `lfa_gap_test_harness.py`.

---

## What these tests are for

All broad coverage gaps have been resolved or confirmed closed. Six specific
instruments and one endpoint question remain unresolved. These are the ONLY
things this prompt and its associated script cover.

### The six instruments

**Group A — EUR/GCC crosses (3 pairs)**
These returned HTTP 400 from the IPA vol surface connector. USD/AED works fine,
so the failure is EUR-base specific on pegged currencies, not a blanket content
gap. The hypothesis is thin-market / near-zero vol causing the surface algorithm
to reject the fit — not a missing content rights issue.

  - EUR/AED
  - EUR/KWD
  - EUR/SAR

Test approach: try IPA FX Forwards and IPA FX Options (vanilla) as fallbacks
before concluding the data is absent. A populated `ForwardPrice` or any non-null
analytics field is a positive result even if vol surface fails.

**Group B — untested USD pairs (2 pairs)**
These were not reached in the live session. Forward rate coverage is confirmed
for USD/SAR in the Datastream spreadsheet. USD/CNH forward coverage is also
confirmed. Vol coverage for both is unknown.

  - USD/SAR
  - USD/CNH

Test approach: IPA FX vol surface first; if 400, fall back to FX Options.

**Group C — implied yield from forward points (1 endpoint question)**
The IPA FX Forwards endpoint may return `ImpliedForeignRate` and
`ImpliedDomesticRate` fields. If populated for non-G5 currencies, the
FXFA-equivalent gap is closed without any client-side computation.

Test pairs (non-G5, liquid): EUR/PLN, EUR/HUF, EUR/CZK, EUR/SEK.
These pairs are chosen because they have confirmed forward rate coverage
in Datastream — so if LFA fails to return implied yields, it is a genuine
gap, not a missing input problem.

---

## What I need help with

### 1. Writing the residual gap script

Create `workflows/lfa_residual_gaps.py` following this exact structure:

```
Section A  — EUR/GCC crosses (EUR/AED, EUR/KWD, EUR/SAR)
  A1. IPA FX vol surface attempt (expected to fail — document the error code)
  A2. IPA FX Forwards fallback — check ForwardPrice, ImpliedForeignRate
  A3. IPA FX Options fallback — vanilla call/put, check any populated field

Section B  — Untested USD pairs (USD/SAR, USD/CNH)
  B1. IPA FX vol surface
  B2. IPA FX Forwards fallback if B1 fails

Section C  — Implied yield from forward points
  C1. IPA FX Forwards for EUR/PLN, EUR/HUF, EUR/CZK, EUR/SEK
      Explicitly request: ImpliedForeignRate, ImpliedDomesticRate,
      ForwardPrice, SpotPrice, Tenor
  C2. Field-level check: is ImpliedForeignRate non-null and non-zero?
      A 200 response with a null field is NOT a positive result.
```

Use the `post()`/`get()` helpers from the existing harness. Do not inline
new HTTP logic.

### 2. Interpreting A-group 400 errors

When EUR/AED, EUR/KWD, or EUR/SAR return 400 from the vol surface endpoint,
help me determine whether the error is:

- **Thin market rejection** — the SVI/SSVI fit algorithm cannot calibrate
  because the FX options market is too illiquid or vol is near-zero (e.g.
  EUR/AED near-zero vol because AED is soft-pegged to USD). Fix: try a
  single-expiry vanilla option request instead of a full surface.
- **Missing input data** — spot or forward data not available for the EUR
  cross. Fix: test whether USD cross of the same currency works differently.
- **RIC format error** — the instrument code is wrong. LSEG FX pairs are
  conventionally `CCYCCY` (6 chars, no separator). Confirm: `EURAED`,
  `EURKWD`, `EURSAR` are the correct formats. Do not suggest `EUR/AED`,
  `EURAED=`, or other variants unless the 6-char format fails.
- **Permissions error** — the API key does not have rights to this pair.
  This would be a 401/403, not a 400 — flag if seen.

### 3. Field-level extraction for Section C

After a successful IPA FX Forwards call, write extraction logic that:

- Pulls `ImpliedForeignRate` and `ImpliedDomesticRate` from the response
- Returns `None` explicitly if the field is absent or null — do not mask
  missing fields as zero
- Prints a clear ✓/✗/⚠ line per pair:
  - ✓ if both fields are populated and non-null
  - ⚠ if the call succeeded (200) but the fields are null or absent
  - ✗ if the call failed (non-200)
- The ⚠ case is the important one — HTTP 200 with null implied yield means
  the FXFA-equivalent gap is NOT closed by LFA

### 4. Updating the POST-RUN SUMMARY TEMPLATE

After I paste run output, help me append results to the existing summary
template in `lfa_gap_test_harness.py`. The residual gap results slot into:

```
[ ] Historical vol — unconfirmed 12 pairs
    → Confirmed newly: (add EUR/GCC result here)
    → Still missing:

[ ] Implied vol ATM 3M/6M — beyond USD/CNY
    → Additional pairs confirmed: (add USD/SAR, USD/CNH here)

[ ] Implied yield from forward points (non-G5)
    → LFA IPA FX Forward returns ImpliedForeignRate / ImpliedDomesticRate: YES/NO
    → Pairs confirmed: (add C1 results here)
```

---

## Hard constraints

- **Do not re-run environment discovery.** SDK availability, package installs,
  and `.env` structure are already known. Skip straight to the request logic.
- **Do not modify `lfa_gap_test_harness.py`** unless explicitly asked. The
  residual tests live in their own file.
- **Do not test Type 2 gaps** (EMCI, BofA GFSI) — those are confirmed
  licensing gaps and are out of scope for this script.
- **Do not use async patterns** — keep the script synchronous.
- **Do not hardcode credentials** — load from `.env` via `python-dotenv`.
- **The ⚠ null-field case must be treated as a gap** for client reporting
  purposes, even if HTTP status is 200.

---

## Key facts to carry into responses

| Fact | Detail |
|---|---|
| EUR/AED 400 pattern | EUR-base specific; USD/AED returns full surface to 10Y |
| AED peg | AED is pegged to USD at ~3.6725; near-zero vol expected |
| KWD peg | KWD is pegged to a basket; very low vol; similar behaviour expected |
| SAR peg | SAR pegged to USD; same near-zero dynamic |
| USD/SAR fwd confirmed | Forward rates confirmed in Datastream spreadsheet |
| USD/CNH fwd confirmed | Forward rates confirmed; vol unknown |
| Non-G5 implied yield | If ImpliedForeignRate populates for EUR/PLN etc., the FXFA gap closes |
| RIC format | All FX pairs use 6-char ISO format: `EURAED`, `EURKWD`, `EURSAR`, `USDSAR`, `USDCNH` |
| Section C priority | EUR/PLN and EUR/HUF are the highest-value test pairs (liquid non-G5 EM) |

---

## Example prompts

- `"Write the full lfa_residual_gaps.py following the A/B/C structure above"`
- `"EUR/KWD returned 400 with body {'error': 'Insufficient option data'} — is that thin market or missing RIC?"`
- `"The C1 call for EUR/PLN returned 200 but ImpliedForeignRate is null — what does that tell us and what should I try next?"`
- `"USD/SAR vol surface returned a full grid — help me extract ATM 3M and 6M vol from the response"`
- `"All three EUR/GCC crosses returned 400 from both vol surface and FX Forwards — what is the right conclusion for the client?"`
- `"Run output pasted below — fill in the POST-RUN SUMMARY TEMPLATE additions"`
