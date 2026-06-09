"""
Historical EQ Vol Surface Availability Probe & API Output Tag Audit

This script:
1. Probes 12 regional RICs across 5 historical dates to measure API coverage
2. Audits which output enrichment tags the API accepts for dividend/forward data
3. Scans lseg_analytics package for securities finance modules

Total API calls: 60 (historical) + 1 (tag audit) = 61
"""

from __future__ import annotations

import logging
import json
import pkgutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import csv

import pandas as pd
from lseg_analytics.pricing.market_data import eq_volatility as ev
import lseg_analytics

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
)

# === CONFIGURATION ===
PROBE_RICS = {
    'US': ['AAPL.O@RIC', 'JPM.N@RIC', 'SPY.P@RIC', '.SPX@RIC'],
    'Europe': ['SAPG.DE@RIC', 'ASML.AS@RIC', 'NOVOb.CO@RIC', '.STOXX50E@RIC'],
    'APAC': ['.N225@RIC', '7203.T@RIC', '9988.HK@RIC', '.HSI@RIC']
}

PROBE_DATES = [
    '2016-01-04',
    '2018-01-02',
    '2020-01-02',
    '2022-01-03',
    '2024-01-02'
]

OUTPUT_TAGS_TO_TEST = (
    "Data",
    "UnderlyingSpot",
    "InterestRateCurve",
    "ForwardCurve",
    "SurfaceInformation",
    "Dividends",
    "DiscountCurve",
    "MoneynessStrike"
)

# === PART 1: HISTORICAL AVAILABILITY PROBE ===

def probe_surface_minimal(ric: str, as_of_date: str) -> dict:
    """
    Call surface API with minimal payload (no output enrichment).
    
    Args:
        ric: RIC code (e.g., 'AAPL.O@RIC')
        as_of_date: Date string (YYYY-MM-DD)
    
    Returns:
        dict with keys: status, n_expiries, error
    """
    try:
        # Parse date - API will serialize datetime to ISO 8601 format automatically
        # datetime object without timezone will be converted to ISO format with time component
        calc_date_obj = datetime.strptime(as_of_date, '%Y-%m-%d')
        calc_datetime = datetime(calc_date_obj.year, calc_date_obj.month, calc_date_obj.day, 0, 0, 0)
        
        # Build surface definition
        surface_def = ev.EtiSurfaceDefinition(instrument_code=ric)
        
        # Build surface parameters with required enums
        surface_params = ev.EtiSurfaceParameters(
            calculation_date=calc_datetime,
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        # Build request item
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=ric,
            underlying_definition=surface_def,
            surface_parameters=surface_params,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        # Call API with minimal payload
        response = ev.calculate(universe=[request_item])
        
        # Check if response has data
        if not response or not response.get('data'):
            return {
                'status': 'NO_DATA',
                'n_expiries': 0,
                'error': 'Empty response'
            }
        
        # Count expiries (surface matrix column count)
        data_item = response['data'][0]
        
        if 'surface' not in data_item or not data_item['surface']:
            return {
                'status': 'NO_SURFACE',
                'n_expiries': 0,
                'error': 'No surface matrix in response'
            }
        
        surface = data_item['surface']
        # First row contains expiry dates (after strike column)
        if len(surface) > 0 and isinstance(surface[0], list):
            n_expiries = len(surface[0]) - 1  # Subtract strike column
            
            if n_expiries > 0:
                return {
                    'status': 'AVAILABLE',
                    'n_expiries': n_expiries,
                    'error': None
                }
            else:
                return {
                    'status': 'EMPTY_SURFACE',
                    'n_expiries': 0,
                    'error': 'No expiries in surface'
                }
        
        return {
            'status': 'MALFORMED',
            'n_expiries': 0,
            'error': 'Unexpected surface structure'
        }
    
    except Exception as e:
        error_msg = str(e)
        
        # Classify error
        if 'unknown' in error_msg.lower():
            status = 'UNKNOWN_RIC'
        elif 'delisted' in error_msg.lower():
            status = 'DELISTED'
        elif 'insufficient' in error_msg.lower() or 'not enough' in error_msg.lower():
            status = 'INSUFFICIENT_DATA'
        else:
            status = 'API_ERROR'
        
        return {
            'status': status,
            'n_expiries': 0,
            'error': error_msg[:100]  # Truncate long errors
        }


def run_historical_probe() -> pd.DataFrame:
    """
    Probe all RIC+date combinations and record availability.
    
    Returns:
        DataFrame with columns: ric, region, probe_date, status, n_expiries, error
    """
    results = []
    total_probes = sum(len(rics) for rics in PROBE_RICS.values()) * len(PROBE_DATES)
    probe_count = 0
    
    for region, rics in PROBE_RICS.items():
        for ric in rics:
            for date_str in PROBE_DATES:
                probe_count += 1
                logger.info(f"[{probe_count}/{total_probes}] Probing {ric} @ {date_str}")
                
                result = probe_surface_minimal(ric, date_str)
                
                results.append({
                    'ric': ric,
                    'region': region,
                    'probe_date': date_str,
                    'status': result['status'],
                    'n_expiries': result['n_expiries'],
                    'error': result['error']
                })
    
    return pd.DataFrame(results)


# === PART 2: OUTPUT TAGS AUDIT ===

def audit_output_tags(ric: str = 'AAPL.O@RIC') -> dict:
    """
    Test which output enrichment tags are accepted by the API.
    
    Args:
        ric: RIC to test with (default: AAPL.O@RIC)
    
    Returns:
        dict with keys: accepted, rejected, errors
    """
    logger.info(f"Auditing output tags for {ric}...")
    
    # Use datetime without microseconds/timezone
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    
    accepted = []
    rejected = []
    errors = []
    
    # Test with all output tags
    try:
        # Build request with all output tags
        surface_def = ev.EtiSurfaceDefinition(instrument_code=ric)
        
        surface_params = ev.EtiSurfaceParameters(
            calculation_date=today,
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )
        
        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=ric,
            underlying_definition=surface_def,
            surface_parameters=surface_params,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )
        
        response = ev.calculate(
            universe=[request_item],
            fields=','.join(OUTPUT_TAGS_TO_TEST)
        )
        
        if response and response.get('data'):
            data_item = response['data'][0]
            
            # Map response keys to output tags
            response_keys = set(data_item.keys())
            
            for tag in OUTPUT_TAGS_TO_TEST:
                # Map tag name to response key name
                tag_key_map = {
                    'Data': 'surface',
                    'UnderlyingSpot': 'underlyingSpot',
                    'InterestRateCurve': 'interestRateCurve',
                    'ForwardCurve': 'forwardCurve',
                    'SurfaceInformation': 'surfaceInformation',
                    'Dividends': 'dividends',
                    'DiscountCurve': 'discountCurve',
                    'MoneynessStrike': 'moneynessStrike'
                }
                
                if tag_key_map.get(tag) in response_keys:
                    accepted.append(tag)
                else:
                    rejected.append(tag)
    
    except Exception as e:
        errors.append(str(e))
    
    return {
        'accepted': accepted,
        'rejected': rejected,
        'errors': errors
    }


# === PART 3: MODULE AUDIT ===

def audit_lseg_modules() -> dict:
    """
    Scan lseg_analytics package for relevant module paths.
    
    Returns:
        dict with keys: repo, borrow, securities_finance, dividend
    """
    logger.info("Scanning lseg_analytics modules...")
    
    found_modules = {
        'repo': [],
        'borrow': [],
        'securities_finance': [],
        'dividend': []
    }
    
    keywords = {
        'repo': ['repo'],
        'borrow': ['borrow'],
        'securities_finance': ['securities_finance'],
        'dividend': ['dividend']
    }
    
    for importer, modname, ispkg in pkgutil.walk_packages(
        path=lseg_analytics.__path__,
        prefix='lseg_analytics.',
        onerror=lambda x: None
    ):
        for category, keyword_list in keywords.items():
            if any(kw in modname.lower() for kw in keyword_list):
                found_modules[category].append(modname)
    
    return found_modules


# === OUTPUT FUNCTIONS ===

def save_historical_availability(df: pd.DataFrame, output_dir: Path) -> None:
    """Save historical availability probe results to CSV."""
    output_file = output_dir / 'historical_availability.csv'
    df.to_csv(output_file, index=False)
    logger.info(f"Saved historical availability to {output_file}")
    
    # Print summary
    print("\n" + "="*70)
    print("HISTORICAL AVAILABILITY SUMMARY")
    print("="*70)
    print(df.groupby('status')['ric'].count().to_string())
    print(f"\nTotal probes: {len(df)}")
    print(f"Available surfaces: {len(df[df['status'] == 'AVAILABLE'])}")
    print(f"Coverage %: {100 * len(df[df['status'] == 'AVAILABLE']) / len(df):.1f}%")
    print("="*70 + "\n")


def save_data_audit(
    tag_audit: dict,
    module_audit: dict,
    output_dir: Path,
    ric: str = 'AAPL.O@RIC'
) -> None:
    """Save audit findings to markdown."""
    output_file = output_dir / 'data_audit.md'
    
    content = f"""# EQ Vol Surface API & Data Audit Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Part 1: Output Tag Support

Tested on: `{ric}` (today's date)

### Accepted Output Tags ({len(tag_audit['accepted'])})
```
{json.dumps(tag_audit['accepted'], indent=2)}
```

### Rejected Output Tags ({len(tag_audit['rejected'])})
```
{json.dumps(tag_audit['rejected'], indent=2)}
```

### Errors During Tag Test
```
{json.dumps(tag_audit['errors'], indent=2) if tag_audit['errors'] else 'None'}
```

---

## Part 2: LSEG Analytics Module Scan

Searched for modules matching keywords: `repo`, `borrow`, `securities_finance`, `dividend`

### Dividend Modules ({len(module_audit['dividend'])})
```
{chr(10).join(module_audit['dividend']) if module_audit['dividend'] else 'None found'}
```

### Securities Finance Modules ({len(module_audit['securities_finance'])})
```
{chr(10).join(module_audit['securities_finance']) if module_audit['securities_finance'] else 'None found'}
```

### Repo Modules ({len(module_audit['repo'])})
```
{chr(10).join(module_audit['repo']) if module_audit['repo'] else 'None found'}
```

### Borrow Modules ({len(module_audit['borrow'])})
```
{chr(10).join(module_audit['borrow']) if module_audit['borrow'] else 'None found'}
```

---

## Summary

- **Total Historical Probes:** 60 (12 RICs × 5 dates)
- **Output Tags Tested:** {len(OUTPUT_TAGS_TO_TEST)}
- **Accepted Tags:** {len(tag_audit['accepted'])}
- **Module Categories Scanned:** 4
- **Total Modules Found:** {sum(len(v) for v in module_audit.values())}
"""
    
    output_file.write_text(content)
    logger.info(f"Saved audit report to {output_file}")
    print(content)


# === MAIN ===

def main() -> None:
    """Execute all probes and audits."""
    logger.info("Starting EQ Vol Surface Availability Probe...")
    logger.info(f"Total API calls planned: 60 (historical) + 1 (tags) = 61")
    
    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(f'data/outputs/{timestamp}_surface_probe')
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # Run historical probe
    logger.info("\n[PHASE 1] Running historical availability probe...")
    historical_df = run_historical_probe()
    
    # Run tag audit
    logger.info("\n[PHASE 2] Auditing output tags...")
    tag_audit = audit_output_tags('AAPL.O@RIC')
    
    # Run module audit
    logger.info("\n[PHASE 3] Scanning lseg_analytics modules...")
    module_audit = audit_lseg_modules()
    
    # Write outputs
    logger.info("\n[OUTPUT] Writing results...")
    save_historical_availability(historical_df, output_dir)
    save_data_audit(tag_audit, module_audit, output_dir)
    
    logger.info(f"\n✓ All results written to {output_dir}")


if __name__ == '__main__':
    main()
