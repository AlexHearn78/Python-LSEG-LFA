from lseg_analytics.pricing.market_data import eq_volatility as ev
import datetime as dt
import pandas as pd
import json

def test_forward_curve_extraction(ric):
    """Test if forward curve is available in default response"""
    print(f"\n=== Testing {ric} ===")

    try:
        surface_definition = ev.EtiSurfaceDefinition(instrument_code=ric)
        surface_parameters = ev.EtiSurfaceParameters(
            calculation_date=dt.datetime(2026, 5, 10),
            time_stamp=ev.CurvesAndSurfacesTimeStampEnum.DEFAULT,
            input_volatility_type=ev.InputVolatilityTypeEnum.IMPLIED,
            volatility_model=ev.CurvesAndSurfacesVolatilityModelEnum.SSVI,
            moneyness_type=ev.MoneynessTypeEnum.SPOT,
            price_side=ev.CurvesAndSurfacesPriceSideEnum.MID,
            x_axis=ev.XAxisEnum.STRIKE,
            y_axis=ev.YAxisEnum.DATE,
        )

        request_item = ev.EtiVolatilitySurfaceRequestItem(
            surface_tag=f"{ric}_test",
            underlying_definition=surface_definition,
            surface_parameters=surface_parameters,
            underlying_type=ev.CurvesAndSurfacesUnderlyingTypeEnum.ETI,
            surface_layout=ev.SurfaceOutput(format=ev.FormatEnum.MATRIX),
        )

        # Execute without outputs parameter
        response = ev.calculate(universe=[request_item])

        print("Response keys:", list(response.keys()) if hasattr(response, 'keys') else 'no keys')

        if 'data' in response:
            data_item = response['data'][0]
            print("Data item keys:", list(data_item.keys()) if hasattr(data_item, 'keys') else 'no keys')

            # Check for forward curve
            forward_keys = [k for k in data_item.keys() if 'forward' in k.lower()]
            print("Forward-related keys:", forward_keys)

            if forward_keys:
                for key in forward_keys:
                    val = data_item[key]
                    print(f"{key}: {type(val)} - {str(val)[:200]}...")

            # Check for interest rate curve
            rate_keys = [k for k in data_item.keys() if 'rate' in k.lower() or 'interest' in k.lower()]
            print("Rate-related keys:", rate_keys)

            # Check for spot
            spot_keys = [k for k in data_item.keys() if 'spot' in k.lower() or 'underlying' in k.lower()]
            print("Spot-related keys:", spot_keys)

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

# Test the identifiers
identifiers = ['AAPL.O@RIC', 'MSFT.O@RIC', 'EWJ@RIC', '.N225@RIC', 'VOD.L@RIC', '.SPX@RIC', 'US78462F1030']

for ident in identifiers:
    test_forward_curve_extraction(ident)