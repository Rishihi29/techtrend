#!/usr/bin/env python
"""One-command demo: full platform run on the bundled sample slice.

    python scripts/seed_demo.py     (or: make demo)

Runs ingestion -> bronze -> silver -> gold -> data quality -> ML training
-> dbt snapshot/build, entirely locally: filesystem lake, DuckDB warehouse,
no credentials, no Docker. Finishes with the API launch command.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from techtrend.pipeline import run_all  # noqa: E402


def main() -> None:
    start = time.perf_counter()
    run_all()
    elapsed = time.perf_counter() - start
    print(
        f"\nDemo pipeline complete in {elapsed:.1f}s."
        "\nNext:  make serve      # dashboard at http://localhost:8000"
        "\n       open /docs      # interactive OpenAPI"
    )


if __name__ == "__main__":
    main()
