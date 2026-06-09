"""Thin wrappers around the LSEG SDKs.

These modules exist to:
1. Centralise boilerplate that was duplicated 16+ times across scripts.
2. Insulate the rest of the codebase from SDK rename / private-import risk
   (e.g. `lseg_analytics.socgen.cof_box._functions` is a private module today).
3. Provide one place to change response-shape parsing if LSEG changes the API.
"""
