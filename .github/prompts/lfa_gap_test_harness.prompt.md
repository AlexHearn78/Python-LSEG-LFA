# LFA Gap Test Harness — Copilot Chat Prompt
# Save this file to .github/prompts/lfa_gap_test_harness.prompt.md
# In VS Code: open Copilot Chat, click the paperclip → "Prompt..." → select this file.
# Or type: #lfa_gap_test_harness in the chat input to reference it directly.

---

## Context

You are helping me work on `lfa_gap_test_harness.py`. This script tests whether the
LSEG Financial Analytics (LFA) API can close data coverage gaps identified in a client
coverage check (Case 15703070) across 27 FX currency pairs.

The file has three sections:

- **Section 1 — Computation gaps (Type 1):** The underlying LSEG data exists but a
  derived series is missing. LFA analytics may be able to produce it. Six sub-tests:
  - `1a` Curve steepness: 2Y/10Y spread for EUR and USD (OIS/ESTR curves)
  - `1b` IR spread inputs: 2Y UST yield + 2Y German Bund yield
  - `1c` FX spot histories for correlation matrix construction (all 27 pairs)
  - `1d` Implied yield from FX forward points (non-G5 currencies)
  - `1e` Historical vol (3M & 6M) for the 12 unconfirmed pairs
  - `1f` Implied ATM vol (3M & 6M) beyond USD/CNY

- **Section 2 — Licensing gaps (Type 2):** Third-party proprietary indices (EMCI,
  BofA GFSI). These are expected 404s. The test is purely confirmatory.

- **Section 3 — Sanity checks:** Confirmed-working data (USD/CNY IV, EUR/USD spot,
  VIX). If these fail, the problem is API auth/config, not data coverage.

Two helper functions handle all HTTP calls:
- `post(endpoint, payload)` — wraps POST, returns parsed JSON or a structured error dict
- `get(endpoint, params)` — wraps GET, same error contract

`result_summary(label, resp)` prints ✓ / ✗ per call. All responses follow the same
shape: success returns the raw LFA JSON; failure returns `{"error": ..., "status_code": ..., "body": ...}`.

The API base URL and key come from `.env` via `python-dotenv`. Environment targets
(PROD / PPE / DEV) are set by changing `LFA_BASE_URL` in the `.env` file.

---

## What I need help with

When I ask you a question about this file, focus on the following areas:

### 1. Interpreting API responses
When I paste a response from a test run, help me determine:
- Whether the key field came back populated or null (e.g. `ImpliedForeignRate`,
  `HistoricalVolatility3M`, `ZeroRate`)
- Whether a ✗ result is an auth failure, a missing RIC, an unsupported field, or a
  genuine data gap
- What the response shape tells us about whether the Type 1 gap is closeable

### 2. Fixing failed requests
If a test returns an error, help me:
- Diagnose whether the endpoint path, payload structure, or field names are wrong
  against the LFA IPA API schema
- Suggest corrected RIC formats (e.g. `EURUSD=` vs `EUR=` vs `EURUSD=X`)
- Propose alternative endpoints if the primary one fails (e.g. falling back from
  `/lfa/ipa/financial-contracts/fx-options/bulk` to a Datastream timeseries route)

### 3. Extending the harness
When I ask you to add a new test, follow these conventions exactly:
- Add a `print("\n[Nx] <description>")` header matching the existing section numbering
- Use the existing `post()` or `get()` helpers — do not add new HTTP calls directly
- Add a `time.sleep(0.3)` after any loop that calls the API per-instrument
- Mirror the `result_summary()` pattern for output
- Add an inline comment explaining what a positive result means for the client case
- Do not modify `ALL_27_PAIRS`, `CONFIRMED_HV`, or the `SANITY_CHECKS` list without
  being explicitly asked

### 4. Extracting field values from responses
Help me write targeted field-extraction logic when `result_summary` is too coarse.
For example, after a successful Section 1d call, I may need to check whether
`ImpliedForeignRate` is non-null rather than just whether the call succeeded.
Use defensive access (`resp.get("data", [{}])[0].get("ImpliedForeignRate")`) and
treat a `None` or missing field as equivalent to a data gap for reporting purposes.

### 5. Generating the post-run summary
After I paste results from a full run, help me populate the `POST-RUN SUMMARY TEMPLATE`
at the bottom of the file. Map each ✓/✗ line to the corresponding YES/NO checkbox.
Flag any result where ✓ (HTTP 200) does not necessarily mean the field was populated —
that distinction matters for the client communication.

---

## Constraints

- **Do not** suggest replacing the `post()`/`get()` helpers with `httpx`, `aiohttp`,
  or any async pattern. The script is intentionally synchronous.
- **Do not** add retry logic unless I ask — the `time.sleep(0.3)` per loop is
  sufficient for rate-limit hygiene at this call volume.
- **Do not** change the Type 1 / Type 2 framing in comments or print statements.
  This distinction is load-bearing for how results are communicated to the client.
- When suggesting RIC corrections, note that LSEG RICs are case-sensitive and that
  composite vs. exchange-specific suffixes (`=`, `=X`, `=R`) behave differently.
- The `.env` file is never in scope — do not suggest hardcoding credentials.

---

## Key domain terms (use these consistently)

| Term | Meaning in this file |
|---|---|
| Type 1 gap | Computation gap — data exists, derived series missing |
| Type 2 gap | Licensing gap — third-party index, not redistributable |
| HV | Historical volatility (3M or 6M tenor) |
| IV / ATM IV | Implied volatility, at-the-money |
| IPA | LSEG Instrument Pricing Analytics — the analytics layer being tested |
| RIC | Reuters Instrument Code — the identifier format used throughout |
| FXFA equivalent | The implied yield derived from FX forward points (gap in 1d) |
| Datagrid | LSEG bulk timeseries endpoint (`/data/datagrid/bulk`) |
| G5 | EUR, USD, GBP, JPY, CHF — the five currencies with confirmed IR curve coverage |
| Non-G5 | The remaining currencies in the 27-pair list where IR data is sparse |

---

## Example prompts you can use

- `"The 1d test returned a 200 but ImpliedForeignRate is null for EURMXN= — what does that mean and what should I try next?"`
- `"Add a test for 6M forward implied rates across the same non-G5 pairs as 1d"`
- `"The sanity check for VIX returned a 401 — is that an auth problem or a permissions scope issue?"`
- `"Help me write extraction logic to pull ZeroRate from the 1a response and compute the spread in-script"`
- `"Paste my full run output and fill in the POST-RUN SUMMARY TEMPLATE"`
- `"The 1e loop is slow — can I batch the 12 unconfirmed pairs into a single request?"`
