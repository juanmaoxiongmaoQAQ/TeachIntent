#!/usr/bin/env python3
"""Generic pilot baseline CLI: run a frozen pilot block through Hy3.

Usage:
    .venv/bin/python scripts/run_pilot.py            # Block A (default)
    .venv/bin/python scripts/run_pilot.py block_a
    .venv/bin/python scripts/run_pilot.py block_b
    .venv/bin/python scripts/run_pilot.py block_c

Requires a .env file (copy .env.example, fill HY3_API_KEY / HY3_BASE_URL /
HY3_MODEL=tencent/hy3). The API key is NEVER written to any artifact.

Exit code 0 only if every case succeeds; 1 if any case fails; 2 on preflight
failure (aborted before any API call) or unknown block.
"""

from __future__ import annotations

import sys

from teachintent.pilot_runner import run_pilot_cli

if __name__ == "__main__":
    block = sys.argv[1] if len(sys.argv) > 1 else "block_a"
    sys.exit(run_pilot_cli(block))
