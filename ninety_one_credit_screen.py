"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Ninety One Private Credit Screener                                          ║
║  Starmine Combined Credit Risk (CCR) Analysis                                ║
║  Universe: MTN Group | Safaricom | Dangote Cement | Access Bank              ║
║  Data source: LSEG Data Library (lseg-data)                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Purpose:
    Screens four African/EM market-leading companies against Ninety One's
    private credit investment criteria using Starmine's Combined Credit Risk
    model.  Ninety One targets:
        • Market-dominant, blue-chip corporates
        • Leverage < 3.5x Debt/EBITDA
        • Sponsorless (no PE backer)
        • Strong asset base and management team
        • Sectors: Telecoms, Financials, Industrials, Infrastructure

Usage:
    1. Activate your venv:  source .venv/bin/activate
    2. Install deps:         pip install -r requirements.txt
    3. Set credentials:      export LSEG_APP_KEY="your-app-key"
                             (or configure ~/.lseg/credentials.ini)
    4. Run:                  python ninety_one_credit_screen.py
"""

import os
import warnings
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime

warnings.filterwarnings("ignore")

# ── Try importing LSEG Data Library ──────────────────────────────────────────
try:
    import lseg.data as ld
    LSEG_AVAILABLE = True
except ImportError:
    LSEG_AVAILABLE = False
    print("⚠  lseg-data not installed. Running in DEMO MODE with synthetic data.")
    print("   Install with: pip install lseg-data\n")


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  UNIVERSE & FIELD CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

COMPANIES = {
    "MTN Group":      {"ric": "MTNJ.J",     "sector": "Telecoms",          "country": "South Africa"},
    "Safaricom":      {"ric": "SCOM.NR",    "sector": "Telecoms / Fintech","country": "Kenya"},
    "Dangote Cement": {"ric": "DANGCEM.LG", "sector": "Industrials",       "country": "Nigeria"},
    "Access Bank":    {"ric": "ACCESS.LG",  "sector": "Financials",        "country": "Nigeria"},
}

RICS  = [v["ric"]  for v in COMPANIES.values()]
NAMES = list(COMPANIES.keys())

# Starmine + fundamental fields
FIELDS = [
    # ── Starmine Combined Credit Risk ──────────────────────────────────────
    "TR.StarMineCombinedCreditRiskScore",           # CCR score  (0–100)
    "TR.StarMineCombinedCreditRiskPercentile",      # Global percentile rank
    "TR.StarMineSmartRatiosScore",                  # Fundamental sub-score
    "TR.StarMineStructuralCreditRiskScore",         # Market-implied sub-score
    # ── Ninety One screening fundamentals ─────────────────────────────────
    "TR.TotalDebt2TotalEquityReported",             # Leverage proxy
    "TR.NetDebt2EBITDA",                            # Net leverage
    "TR.EBITDAMargin",                              # Margin quality
    "TR.InterestCoverageRatio",                     # Debt service capacity
    "TR.TotalAssetsReported",                       # Asset base size (USD m)
    "TR.TotalDebt",                                 # Total debt load (USD m)
    "TR.RevenueMean",                               # Revenue scale (USD m)
    "TR.ROE",                                       # Return on equity
]

# ── Ninety One screening criteria ─────────────────────────────────────────────
CRITERIA = {
    "CCR Score ≥ 50":       {"field": "TR.StarMineCombinedCreditRiskScore",    "threshold": 50,   "direction": "above", "weight": 0.30},
    "Net Debt/EBITDA ≤ 3.5x":{"field": "TR.NetDebt2EBITDA",                   "threshold": 3.5,  "direction": "below", "weight": 0.30},
    "Interest Cover ≥ 3x":  {"field": "TR.InterestCoverageRatio",             "threshold": 3.0,  "direction": "above", "weight": 0.20},
    "EBITDA Margin ≥ 15%":  {"field": "TR.EBITDAMargin",                      "threshold": 15.0, "direction": "above", "weight": 0.20},
}

# Tier labels for composite scores
def tier_label(score: float) -> str:
    if score >= 75:   return "★  Strong Candidate"
    elif score >= 50: return "◆  Monitor"
    else:             return "✗  Caution"


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  DATA RETRIEVAL  (live LSEG or demo fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_live_data() -> pd.DataFrame:
    """Pull Starmine + fundamentals from LSEG Data Library."""
    print("Opening LSEG session…")
    ld.open_session()

    print("Fetching Starmine CCR data…")
    df = ld.get_data(universe=RICS, fields=FIELDS)

    ld.close_session()
    print("✓  LSEG session closed.\n")
    return df


def demo_data() -> pd.DataFrame:
    """
    Synthetic data for offline development / demos.
    Values are plausible but NOT real — replace with live data for production.
    """
    data = {
        "Instrument":                                RICS,
        "TR.StarMineCombinedCreditRiskScore":        [68,  72,  55,  48],
        "TR.StarMineCombinedCreditRiskPercentile":   [71,  75,  58,  50],
        "TR.StarMineSmartRatiosScore":               [65,  70,  52,  45],
        "TR.StarMineStructuralCreditRiskScore":      [70,  74,  58,  51],
        "TR.TotalDebt2TotalEquityReported":          [1.2, 0.8, 0.9, 4.1],
        "TR.NetDebt2EBITDA":                         [1.8, 1.2, 2.4, 3.8],
        "TR.EBITDAMargin":                           [32,  42,  38,  22],
        "TR.InterestCoverageRatio":                  [5.2, 8.1, 6.4, 2.9],
        "TR.TotalAssetsReported":                    [14200, 3800, 4600, 22000],
        "TR.TotalDebt":                              [4100, 900, 1200, 6800],
        "TR.RevenueMean":                            [12400, 2200, 2800, 4100],
        "TR.ROE":                                    [18.4, 31.2, 22.7, 14.1],
    }
    return pd.DataFrame(data)


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  SCREENING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_screen(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Apply Ninety One criteria to each company and compute a weighted
    composite score (0–100).
    """
    ric_to_name    = {v["ric"]: k for k, v in COMPANIES.items()}
    ric_to_sector  = {v["ric"]: v["sector"]  for v in COMPANIES.values()}
    ric_to_country = {v["ric"]: v["country"] for v in COMPANIES.values()}

    df_raw = df_raw.copy()
    df_raw["Company"] = df_raw["Instrument"].map(ric_to_name)
    df_raw["Sector"]  = df_raw["Instrument"].map(ric_to_sector)
    df_raw["Country"] = df_raw["Instrument"].map(ric_to_country)
    df_raw = df_raw.set_index("Company")

    rows = []
    for company in df_raw.index:
        row = df_raw.loc[company]
        total_w = 0.0
        pass_w  = 0.0
        criteria_detail = {}

        for label, params in CRITERIA.items():
            fld       = params["field"]
            threshold = params["threshold"]
            direction = params["direction"]
            weight    = params["weight"]

            try:
                value = float(row.get(fld, np.nan))
            except (TypeError, ValueError):
                value = np.nan

            if np.isnan(value):
                result = "N/A"
            elif direction == "below":
                result = "PASS" if value <= threshold else "FAIL"
            else:
                result = "PASS" if value >= threshold else "FAIL"

            criteria_detail[label] = {"value": value, "result": result}
            total_w += weight
            if result == "PASS":
                pass_w += weight

        composite = round((pass_w / total_w) * 100, 1) if total_w else 0.0

        rows.append({
            "Company":            company,
            "Sector":             row["Sector"],
            "Country":            row["Country"],
            "CCR Score":          row.get("TR.StarMineCombinedCreditRiskScore"),
            "CCR Percentile":     row.get("TR.StarMineCombinedCreditRiskPercentile"),
            "SmartRatios Score":  row.get("TR.StarMineSmartRatiosScore"),
            "Struct. CR Score":   row.get("TR.StarMineStructuralCreditRiskScore"),
            "Net Debt/EBITDA":    row.get("TR.NetDebt2EBITDA"),
            "Interest Cover":     row.get("TR.InterestCoverageRatio"),
            "EBITDA Margin %":    row.get("TR.EBITDAMargin"),
            "ROE %":              row.get("TR.ROE"),
            "Revenue (USD m)":    row.get("TR.RevenueMean"),
            "Total Assets (USD m)":row.get("TR.TotalAssetsReported"),
            "Composite Score":    composite,
            "Tier":               tier_label(composite),
            "_criteria":          criteria_detail,     # keep for detailed print
        })

    df_out = pd.DataFrame(rows).set_index("Company")
    return df_out.sort_values("Composite Score", ascending=False)


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  CONSOLE OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(df: pd.DataFrame, mode: str) -> None:
    now = datetime.today().strftime("%d %B %Y")
    print()
    print("═" * 76)
    print("  NINETY ONE PRIVATE CREDIT SCREENER — STARMINE CCR ANALYSIS")
    print(f"  Run date: {now}   |   Data mode: {mode}")
    print("═" * 76)

    display_cols = [
        "Sector", "Country", "CCR Score", "CCR Percentile",
        "Net Debt/EBITDA", "Interest Cover", "EBITDA Margin %",
        "Composite Score", "Tier",
    ]
    print(df[display_cols].to_string())

    print()
    print("─" * 76)
    print("  CRITERION-BY-CRITERION DETAIL")
    print("─" * 76)
    for company, row in df.iterrows():
        print(f"\n  {company}  (Composite: {row['Composite Score']:.0f}%  |  {row['Tier']})")
        for label, detail in row["_criteria"].items():
            val    = detail["value"]
            result = detail["result"]
            val_str = f"{val:.1f}" if not np.isnan(val) else "n/a"
            flag   = "✓" if result == "PASS" else ("–" if result == "N/A" else "✗")
            print(f"    {flag}  {label:<28}  {val_str:>8}   [{result}]")

    print()
    print("─" * 76)
    print("  INVESTMENT RECOMMENDATION SUMMARY")
    print("─" * 76)
    for rank, (company, row) in enumerate(df.iterrows(), 1):
        print(f"  {rank}. {company:<20}  Score: {row['Composite Score']:>5.1f}%   {row['Tier']}")
    print()


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  VISUALISATION
# ═══════════════════════════════════════════════════════════════════════════════

PALETTE = ["#003366", "#0066CC", "#3399FF", "#99CCFF"]

def build_charts(df: pd.DataFrame, output_path: str = "ninety_one_credit_screen.png") -> None:
    companies = df.index.tolist()
    n = len(companies)
    cols = PALETTE[:n]

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        "Ninety One Private Credit Screen — Starmine CCR Analysis\n"
        f"Universe: {', '.join(companies)}",
        fontsize=13, fontweight="bold", y=1.01
    )

    def hbar(ax, values, title, xlabel, vline=None, vline_label=None, fmt=".1f"):
        vals = [float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else 0 for v in values]
        bars = ax.barh(companies, vals, color=cols, edgecolor="white", height=0.55)
        if vline is not None:
            ax.axvline(vline, color="crimson", linestyle="--", linewidth=1.4,
                       label=vline_label or f"Threshold ({vline})")
            ax.legend(fontsize=8)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xlabel(xlabel, fontsize=9)
        ax.tick_params(axis="y", labelsize=9)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_width() + max(vals) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{val:{fmt}}", va="center", fontsize=9)

    # ── Panel A: Composite Score ──────────────────────────────────────────
    ax = axes[0][0]
    hbar(ax,
         df["Composite Score"].tolist(),
         "A.  Ninety One Criteria — Composite Score",
         "Composite Score  (%)",
         vline=75, vline_label="Strong Candidate (75%)",
         fmt=".0f")
    ax.set_xlim(0, 115)
    # Add a second reference line
    ax.axvline(50, color="orange", linestyle=":", linewidth=1.2, label="Monitor (50%)")
    ax.legend(fontsize=8)

    # ── Panel B: CCR Score ────────────────────────────────────────────────
    ax = axes[0][1]
    hbar(ax,
         df["CCR Score"].tolist(),
         "B.  Starmine Combined Credit Risk Score  (0–100)",
         "CCR Score  (higher = better credit quality)",
         vline=50, vline_label="Mid-point (50)")
    ax.set_xlim(0, 110)

    # ── Panel C: Net Debt / EBITDA ────────────────────────────────────────
    ax = axes[1][0]
    hbar(ax,
         df["Net Debt/EBITDA"].tolist(),
         "C.  Net Debt / EBITDA — vs Ninety One Ceiling",
         "Net Debt / EBITDA  (x)",
         vline=3.5, vline_label="Ninety One max (3.5x)")

    # ── Panel D: EBITDA Margin vs Interest Cover scatter ─────────────────
    ax = axes[1][1]
    margins = [float(v) if v is not None else 0 for v in df["EBITDA Margin %"].tolist()]
    covers  = [float(v) if v is not None else 0 for v in df["Interest Cover"].tolist()]
    for i, (m, c, co, comp) in enumerate(zip(margins, covers, companies, df.index.tolist())):
        ax.scatter(m, c, color=PALETTE[i], s=180, zorder=5)
        ax.annotate(comp, (m, c), textcoords="offset points", xytext=(6, 4),
                    fontsize=8, color=PALETTE[i], fontweight="bold")
    ax.axvline(15, color="crimson", linestyle="--", linewidth=1.2, label="Margin threshold (15%)")
    ax.axhline(3.0, color="orange",  linestyle=":",  linewidth=1.2, label="Cover threshold (3.0x)")
    ax.set_xlabel("EBITDA Margin  (%)", fontsize=9)
    ax.set_ylabel("Interest Coverage Ratio  (x)", fontsize=9)
    ax.set_title("D.  Quality Quadrant: Margin vs Coverage", fontsize=10, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Add a legend for company colours
    patches = [mpatches.Patch(color=PALETTE[i], label=companies[i]) for i in range(n)]
    fig.legend(handles=patches, loc="lower center", ncol=n,
               fontsize=9, frameon=False, bbox_to_anchor=(0.5, -0.03))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"✓  Chart saved → {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  EXPORT TO CSV
# ═══════════════════════════════════════════════════════════════════════════════

def export_csv(df: pd.DataFrame, path: str = "ninety_one_credit_screen.csv") -> None:
    export_cols = [c for c in df.columns if c != "_criteria"]
    df[export_cols].to_csv(path)
    print(f"✓  Data exported → {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # ── Choose live vs demo data ──────────────────────────────────────────
    use_live = LSEG_AVAILABLE and os.environ.get("LSEG_APP_KEY")

    if use_live:
        df_raw = fetch_live_data()
        mode   = "LIVE (LSEG)"
    else:
        df_raw = demo_data()
        mode   = "DEMO (synthetic)"

    # ── Run screener ──────────────────────────────────────────────────────
    df_results = run_screen(df_raw)

    # ── Console report ────────────────────────────────────────────────────
    print_report(df_results, mode)

    # ── Charts ────────────────────────────────────────────────────────────
    build_charts(df_results)

    # ── CSV export ────────────────────────────────────────────────────────
    export_csv(df_results)


if __name__ == "__main__":
    main()
