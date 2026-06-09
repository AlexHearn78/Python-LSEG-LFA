"""Run-stamped output writer.

`write_run_outputs("forwards", long=df, summary=df, failures=[...])` writes to
`data/outputs/<YYYYMMDD-HHMMSS>_<domain>/long.csv` etc. and returns the run dir.

This kills the file-naming-as-versioning anti-pattern (`_v2`, `_final`,
`_may6_2026`).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pandas as pd

from lseg_quant.config import settings


def make_run_dir(domain: str, *, root: Path | None = None) -> Path:
    """Create and return `data/outputs/<timestamp>_<domain>/`."""
    root = root or settings.output_root
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = root / f"{stamp}_{domain}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_outputs(
    domain: str,
    *,
    run_dir: Path | None = None,
    **frames: pd.DataFrame | list | dict | None,
) -> Path:
    """Write each named frame as `<name>.csv` (or `.json` for non-tabular) into the run dir.

    Returns the run directory path. Pass `None` for any frame to skip it.
    Example:
        write_run_outputs("forwards", long=long_df, summary=summary_df, failures=fails_list)
    """
    run_dir = run_dir or make_run_dir(domain)
    for name, frame in frames.items():
        if frame is None:
            continue
        path = run_dir / name
        if isinstance(frame, pd.DataFrame):
            frame.to_csv(path.with_suffix(".csv"), index=False)
        elif isinstance(frame, (list, dict)):
            with path.with_suffix(".json").open("w", encoding="utf-8") as f:
                json.dump(frame, f, indent=2, default=str)
        else:
            raise TypeError(f"Unsupported frame type for {name!r}: {type(frame).__name__}")
    return run_dir


def write_run_log(run_dir: Path, content: str) -> Path:
    """Write a human-readable run log alongside the data files."""
    log_path = run_dir / "run_log.txt"
    log_path.write_text(content, encoding="utf-8")
    return log_path


def write_run_metadata(run_dir: Path, metadata: dict[str, Any]) -> Path:
    """Write a machine-readable manifest of what produced this run."""
    meta_path = run_dir / "metadata.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, default=str)
    return meta_path
