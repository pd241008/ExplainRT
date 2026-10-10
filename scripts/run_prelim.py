#!/usr/bin/env python3
"""Preliminary R1 run executor (ADR-008 rev 2; ADR-009 provenance).

LightGBM pilot entry point (ADR-010 §5 rev 2): verifies the manifest, then
delegates to ``runner.pilot.main`` — the actual training/evaluation path on
the 10% subset, validation side only, tagged ``pilot-10pct``.

The old reference-pipeline behavior (``runner.execution.run_pipeline``) is
kept under ``--reference`` for repro pulls; default mode now trains.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logger.manifest import dataset_hash, verify_data  # noqa: E402


def main() -> int:  # pragma: no cover - thin delegation
    verify_data(["bodmas_features"])
    print(f"dataset_hash = {dataset_hash(['bodmas_features'])[:12]}")
    from runner.pilot import main as pilot_main

    return pilot_main()


if __name__ == "__main__":
    raise SystemExit(main())
