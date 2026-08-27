#!/usr/bin/env python3
"""Run the frozen Block A Hy3 baseline generation batch.

Loads the frozen 12-case Block A JSONL, runs each case sequentially through the
existing Generator service with the frozen experimental condition (OpenRouter,
tencent/hy3, temperature=0, no structured output, no retry, no self-repair),
and saves per-case + run-level artifacts under results/pilot/block_a/<run_id>/.

Frozen experimental condition:
  API gateway:     OpenRouter (HY3_BASE_URL=https://openrouter.ai/api/v1)
  model:           tencent/hy3
  temperature:     0
  structured output: disabled
  retry:           disabled
  self-repair:     disabled

Usage:
    .venv/bin/python scripts/run_pilot_block_a.py

Requires a .env file (copy .env.example, fill HY3_API_KEY / HY3_BASE_URL /
HY3_MODEL=tencent/hy3). The API key is NEVER written to any artifact.

Exit code 0 only if every case succeeds; non-zero if any case fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from teachintent.generator import Hy3Client
from teachintent.pilot_runner import (
    BLOCK_A_DATASET_PATH,
    FROZEN_CONDITIONS,
    PreflightError,
    run_pilot_block_a,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results" / "pilot" / "block_a"


def main() -> int:
    load_dotenv()

    client = Hy3Client.from_env()

    print(f"Dataset:  {BLOCK_A_DATASET_PATH}")
    print(f"Endpoint: {client.endpoint}")
    print(f"Model:    {client.model} (requested)")
    print(f"Condition: {FROZEN_CONDITIONS}")
    print()

    try:
        manifest = run_pilot_block_a(client, BLOCK_A_DATASET_PATH, RESULTS_DIR)
    except PreflightError as exc:
        print(f"PREFLIGHT FAILED: {exc}")
        print("Aborted before any Hy3 API call. No cases were generated.")
        return 2

    # Per-case summary.
    for entry in manifest.cases:
        status = "PASS" if entry["outcome"] == "success" else "FAIL"
        detail = ""
        if entry["outcome"] != "success":
            detail = f"  [{entry['exception_class']}]"
        print(
            f"  {status}  {entry['case_id']}"
            f"  ({entry['duration_seconds']:.3f}s){detail}"
        )

    print()
    print(
        f"Aggregate: {manifest.pass_count}/{manifest.case_count} passed, "
        f"{manifest.fail_count} failed."
    )
    print(f"Artifacts: {RESULTS_DIR / manifest.run_id}")
    return 0 if manifest.fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
