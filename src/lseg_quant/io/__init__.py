"""Output writing + canonical schemas.

Centralises the `to_csv("...")` / `csv.writer` calls that were scattered across
20+ scripts, and stamps every run's outputs into a per-run subfolder so that
`data/outputs/` never accumulates ambiguous filenames like `coverage_results.csv`
vs `coverage_results_v2.csv` vs `coverage_results_may6_2026.csv`.
"""
