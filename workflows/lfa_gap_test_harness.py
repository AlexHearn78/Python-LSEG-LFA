"""LFA Gap Test Harness

This workflow is designed to probe whether LSEG analytics / IPA can surface the
coverage required for the gap analysis described in the project prompt.

It uses the installed `lseg_analytics` and `lseg.data` SDKs when available, and
also supports a direct LFA HTTP path if `LFA_BASE_URL` + `LFA_API_KEY` are set.

Authentication is loaded from a repo-root `.env` file if present.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from lseg_analytics.pricing.market_data import fx_forward_curves, fx_volatility, interest_rate_curves

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / '.env'

# This is a minimal sample list of non-G5 FX pairs. Adjust or expand as needed.
NON_G5_PAIRS = [
    'EURMXN=',
    'USDZAR=',
    'EURTRY=',
    'USDMXN=',
]
SAMPLE_ATM_VOL_PAIRS = ['EURUSD=', 'USDJPY=', 'USDCNY=']


def load_environment() -> None:
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=False)
        logger.info('Loaded environment variables from %s', ENV_PATH)
    else:
        logger.info('No .env file found at %s; using process environment only', ENV_PATH)


def get_direct_api_config() -> dict[str, str | None]:
    return {
        'base_url': os.getenv('LFA_BASE_URL'),
        'api_key': os.getenv('LFA_API_KEY'),
        'api_key_header': os.getenv('LFA_API_KEY_HEADER', 'Authorization'),
        'api_key_prefix': os.getenv('LFA_API_KEY_PREFIX', 'Bearer'),
    }


def sdk_auth_available() -> bool:
    return bool(os.getenv('LSEG_APP_KEY') or os.getenv('LSEG_PROFILE'))


def serialize_response(response: Any) -> Any:
    if response is None:
        return None
    if hasattr(response, 'dict'):
        return response.dict()
    if hasattr(response, 'to_dict'):
        return response.to_dict()
    return response


def post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = get_direct_api_config()
    base_url = config['base_url']
    api_key = config['api_key']
    if not base_url or not api_key:
        return {
            'error': 'Direct LFA API auth not configured; set LFA_BASE_URL and LFA_API_KEY',
            'status_code': None,
            'body': None,
        }

    headers = {'Content-Type': 'application/json'}
    auth_header = config['api_key_header'] or 'Authorization'
    auth_prefix = config['api_key_prefix'] or 'Bearer'
    if auth_header.lower() == 'authorization':
        headers['Authorization'] = f'{auth_prefix} {api_key}'.strip()
    else:
        headers[auth_header] = api_key

    url = base_url.rstrip('/') + '/' + endpoint.lstrip('/')
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        body = None
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.ok:
            return serialize_response(body)
        return {'error': 'HTTP error', 'status_code': response.status_code, 'body': body}
    except requests.RequestException as exc:
        return {'error': str(exc), 'status_code': None, 'body': None}


def get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    config = get_direct_api_config()
    base_url = config['base_url']
    api_key = config['api_key']
    if not base_url or not api_key:
        return {
            'error': 'Direct LFA API auth not configured; set LFA_BASE_URL and LFA_API_KEY',
            'status_code': None,
            'body': None,
        }

    headers = {}
    auth_header = config['api_key_header'] or 'Authorization'
    auth_prefix = config['api_key_prefix'] or 'Bearer'
    if auth_header.lower() == 'authorization':
        headers['Authorization'] = f'{auth_prefix} {api_key}'.strip()
    else:
        headers[auth_header] = api_key

    url = base_url.rstrip('/') + '/' + endpoint.lstrip('/')
    try:
        response = requests.get(url, headers=headers, params=params or {}, timeout=60)
        body = None
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if response.ok:
            return serialize_response(body)
        return {'error': 'HTTP error', 'status_code': response.status_code, 'body': body}
    except requests.RequestException as exc:
        return {'error': str(exc), 'status_code': None, 'body': None}


def result_summary(label: str, resp: Any) -> bool:
    if isinstance(resp, dict) and resp.get('error'):
        print(f'[✗] {label}: {resp.get("error")} (status={resp.get("status_code")})')
        return False
    if resp is None:
        print(f'[✗] {label}: no response')
        return False
    print(f'[✓] {label}')
    return True


def parse_date(date_string: str | None) -> dt.datetime:
    if date_string:
        return dt.datetime.fromisoformat(date_string)
    return dt.datetime.now(dt.UTC)


def fetch_ir_curve(ric: str, as_of: dt.datetime) -> dict[str, Any] | None:
    definition = interest_rate_curves.IrCurveDefinitionInstrument(code=ric)
    try:
        response = interest_rate_curves.calculate(definitions=[definition], fields='')
        return serialize_response(response)
    except Exception as exc:
        logger.exception('Failed interest rate curve request for %s', ric)
        return {'error': str(exc)}


def fetch_fx_forward_curve(ric: str) -> dict[str, Any] | None:
    definition = fx_forward_curves.FxForwardCurveDefinitionInstrument(code=ric)
    try:
        response = fx_forward_curves.calculate(definitions=[definition], fields='')
        return serialize_response(response)
    except Exception as exc:
        logger.exception('Failed FX forward request for %s', ric)
        return {'error': str(exc)}


def fetch_fx_vol_surface(ric: str, as_of: dt.datetime) -> dict[str, Any] | None:
    surface_definition = fx_volatility.FxVolatilitySurfaceDefinition(instrument_code=ric.rstrip('='))
    pricing_params = fx_volatility.FxVolatilityPricingParameters(
        calculation_date=as_of,
        time_stamp=fx_volatility.CurvesAndSurfacesTimeStampEnum.DEFAULT,
        price_side=fx_volatility.CurvesAndSurfacesPriceSideEnum.MID,
        volatility_model=fx_volatility.CurvesAndSurfacesVolatilityModelEnum.SVI,
        x_axis=fx_volatility.XAxisEnum.STRIKE,
        y_axis=fx_volatility.YAxisEnum.DATE,
    )
    request_item = fx_volatility.FxVolatilitySurfaceRequestItem(
        surface_tag=ric,
        underlying_definition=surface_definition,
        surface_parameters=pricing_params,
        underlying_type=fx_volatility.CurvesAndSurfacesUnderlyingTypeEnum.Fx,
        surface_layout=fx_volatility.SurfaceOutput(format=fx_volatility.FormatEnum.MATRIX),
    )
    try:
        response = fx_volatility.calculate(universe=[request_item], fields='')
        return serialize_response(response)
    except Exception as exc:
        logger.exception('Failed FX volatility request for %s', ric)
        return {'error': str(exc)}


def run_connectivity() -> None:
    print('\n[Connect] SDK auth')
    if sdk_auth_available():
        print('[✓] LSEG SDK auth appears configured')
    else:
        print('[✗] LSEG SDK auth not found; set LSEG_APP_KEY or LSEG_PROFILE')

    direct = get_direct_api_config()
    print('\n[Connect] Direct LFA HTTP config')
    print(f"base_url={direct['base_url']}, api_key_set={bool(direct['api_key'])}")


def run_1a_curve_steepness(as_of: dt.datetime) -> None:
    print('\n[1a] Curve steepness probe for EUR and USD')
    for ric in ('EUR=', 'USD='):
        resp = fetch_ir_curve(ric, as_of)
        result_summary(f'Interest rate curve for {ric}', resp)
        time.sleep(0.3)


def run_1d_fx_forward(as_of: dt.datetime, pairs: list[str]) -> None:
    print('\n[1d] FX forward / implied rate probe for non-G5 pairs')
    for ric in pairs:
        resp = fetch_fx_forward_curve(ric)
        result_summary(f'FX forward curve for {ric}', resp)
        time.sleep(0.3)


def run_1f_fx_atm_vol(as_of: dt.datetime, pairs: list[str]) -> None:
    print('\n[1f] FX ATM volatility surface probe')
    for ric in pairs:
        resp = fetch_fx_vol_surface(ric, as_of)
        result_summary(f'FX vol surface for {ric}', resp)
        time.sleep(0.3)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run LFA analytics coverage probes.')
    parser.add_argument('--as-of', default=None, help='Valuation date (YYYY-MM-DD or ISO)')
    parser.add_argument('--pairs', nargs='+', default=NON_G5_PAIRS, help='Non-G5 FX pair RICs')
    parser.add_argument('--atm-vol-pairs', nargs='+', default=SAMPLE_ATM_VOL_PAIRS, help='FX pairs for ATM vol surface tests')
    parser.add_argument('--skip-connectivity', action='store_true', help='Skip the auth/connectivity check')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_environment()
    args = parse_args(argv)
    as_of = parse_date(args.as_of)

    if not args.skip_connectivity:
        run_connectivity()

    run_1a_curve_steepness(as_of)
    run_1d_fx_forward(as_of, args.pairs)
    run_1f_fx_atm_vol(as_of, args.atm_vol_pairs)

    print('\nCompleted LFA analytics probe. If auth failed, configure .env or environment variables and rerun.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
