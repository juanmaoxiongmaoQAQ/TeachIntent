#!/usr/bin/env python3
"""Run the frozen Block B (cross_domain_generalization) Hy3 baseline.

Equivalent to ``scripts/run_pilot.py block_b``. Requires a .env file (copy
.env.example, fill HY3_API_KEY / HY3_BASE_URL / HY3_MODEL=tencent/hy3).
Artifacts are saved under results/pilot/block_b/<run_id>/.
"""

from __future__ import annotations

import sys

from teachintent.pilot_runner import run_pilot_cli

if __name__ == "__main__":
    sys.exit(run_pilot_cli("block_b"))
