#!/usr/bin/env python3
"""Run the frozen Block A Hy3 baseline (backward-compatible entry point).

Equivalent to ``scripts/run_pilot.py block_a``. Requires a .env file (copy
.env.example, fill HY3_API_KEY / HY3_BASE_URL / HY3_MODEL=tencent/hy3).
"""

from __future__ import annotations

import sys

from teachintent.pilot_runner import run_pilot_cli

if __name__ == "__main__":
    sys.exit(run_pilot_cli("block_a"))
