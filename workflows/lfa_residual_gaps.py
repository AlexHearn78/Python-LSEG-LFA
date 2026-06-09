"""LFA Residual Gap Probe

Focused API probe for the remaining residual instruments and implied-yield
fields described in `.github/prompts/lfa_residual_gaps.prompt.md`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from lseg_analytics.pricing.market_data import fx_forward_curves, fx_volatility

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / '.env'

EUR_GCC_PAIRS = ['EURAED', 'EURKWD', 'EURSAR']
USD_PAIRS = ['USDSAR', 'USDCNH']
NON_G5_IMPLIED_PAIRS = ['EURPLN', 'EURHUF', 'EURCZK', 'EURSEK']


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


def result_summary(label: str, resp: Any) -> bool:
    if isinstance(resp, dict) and resp.get('error'):
        print(f'[✗] {label}: {resp.get("error")} (status={resp.get("status_code")})')
        return False
    if resp is None:
        print(f'[✗] {label}: no response')
        return False
    print(f'[✓] {label}')
    return True


def warning_summary(label: str, message: str) -> None:
    print(f'[⚠] {label}: {message}')


def fetch_fx_vol_surface(ric: str, as_of: dt.datetime) -> dict[str, Any] | None:
    surface_definition = fx_volatility.FxVolatilitySurfaceDefinition(instrument_code=ric)
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
        logger.exception('Failed FX vol surface request for %s', ric)
        return {'error': str(exc), 'status_code': None, 'body': None}


def fetch_fx_forward_curve_sdk(ric: str) -> dict[str, Any] | None:
    definition = fx_forward_curves.FxForwardCurveDefinitionInstrument(code=ric)
    try:
        response = fx_forward_curves.calculate(definitions=[definition], fields='')
        return serialize_response(response)
    except Exception as exc:
        logger.exception('Failed FX forward request for %s', ric)
        return {'error': str(exc), 'status_code': None, 'body': None}


def flatten_response(resp: Any) -> dict[str, Any] | None:
    if isinstance(resp, dict):
        return resp
    if hasattr(resp, 'dict'):
        return resp.dict()
    return None


def get_field_value(resp: dict[str, Any], field_name: str) -> Any:
    if not isinstance(resp, dict):
        return None
    return resp.get(field_name)


def check_implied_yield_fields(resp: dict[str, Any], ric: str) -> None:
    implied_foreign = get_field_value(resp, 'ImpliedForeignRate')
    implied_domestic = get_field_value(resp, 'ImpliedDomesticRate')
    if implied_foreign is not None and implied_domestic is not None:
        if implied_foreign != 0 and implied_domestic != 0:
            print(f'[✓] {ric} implied yield fields populated')
            print(f'      ImpliedForeignRate={implied_foreign}, ImpliedDomesticRate={implied_domestic}')
            return
        warning_summary(ric, 'HTTP 200 but implied fields are zero or invalid')
        return
    warning_summary(ric, 'HTTP 200 but ImpliedForeignRate or ImpliedDomesticRate is missing/null')


def section_A(as_of: dt.datetime) -> None:
    print('\n[Section A] EUR/GCC crosses')
    for ric in EUR_GCC_PAIRS:
        print(f'\n[A1] FX vol surface attempt for {ric}')
        resp = fetch_fx_vol_surface(ric, as_of)
        if not result_summary(f'Vol surface {ric}', resp):
            print(f'  Fallback A2: FX forward curve for {ric}')
            resp_fwd = fetch_fx_forward_curve_sdk(ric)
            if result_summary(f'FX forward curve {ric}', resp_fwd):
                print('  Positive fallback if forward curve data returned')
            print(f'  Fallback A3: single-point FX vol probe for {ric}')
            resp_point = fetch_fx_vol_surface(ric, as_of)
            result_summary(f'FX vol single-point fallback {ric}', resp_point)
        time.sleep(0.3)


def section_B(as_of: dt.datetime) -> None:
    print('\n[Section B] Untested USD pairs')
    for ric in USD_PAIRS:
        print(f'\n[B1] FX vol surface attempt for {ric}')
        resp = fetch_fx_vol_surface(ric, as_of)
        if not result_summary(f'Vol surface {ric}', resp):
            print(f'  Fallback B2: FX forward curve for {ric}')
            resp_fwd = fetch_fx_forward_curve_sdk(ric)
            result_summary(f'FX forward curve {ric}', resp_fwd)
        time.sleep(0.3)


def section_C(as_of: dt.datetime) -> None:
    print('\n[Section C] Implied yield from forward points')
    for ric in NON_G5_IMPLIED_PAIRS:
        print(f'\n[C1] FX forward curve probe for {ric}')
        resp = fetch_fx_forward_curve_sdk(ric)
        if result_summary(f'FX forward curve {ric}', resp):
            resp_dict = flatten_response(resp) or {}
            check_implied_yield_fields(resp_dict, ric)
        time.sleep(0.3)


def parse_date(date_string: str | None) -> dt.datetime:
    if date_string:
        return dt.datetime.fromisoformat(date_string)
    return dt.datetime.now(dt.UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run LFA residual gap probes.')
    parser.add_argument('--as-of', default=None, help='Valuation date (YYYY-MM-DD or ISO)')
    parser.add_argument('--skip-connectivity', action='store_true', help='Skip auth/connectivity check')
    return parser.parse_args(argv)


def run_connectivity() -> None:
    print('\n[Connectivity] SDK auth check')
    if sdk_auth_available():
        print('[✓] LSEG SDK auth appears configured')
    else:
        print('[✗] LSEG SDK auth not found; set LSEG_APP_KEY or LSEG_PROFILE')

    direct = get_direct_api_config()
    print('\n[Connectivity] Direct LFA HTTP config')
    print(f"base_url={direct['base_url']}, api_key_set={bool(direct['api_key'])}")


def main(argv: list[str] | None = None) -> int:
    load_environment()
    args = parse_args(argv)
    as_of = parse_date(args.as_of)

    if not args.skip_connectivity:
        run_connectivity()

    section_A(as_of)
    section_B(as_of)
    section_C(as_of)

    print('\nCompleted LFA residual gap probe. If auth failed, configure .env or environment variables and rerun.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
