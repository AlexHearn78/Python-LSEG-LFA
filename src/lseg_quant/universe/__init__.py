"""Identifier resolution + universe loading.

The point of this package is that everything downstream (vol surfaces, forward
curves, COFBox, IRC) needs a RIC, but you may receive ISINs, CUSIPs, Bloomberg
tickers, or just plain names. This package centralises that resolution.
"""
