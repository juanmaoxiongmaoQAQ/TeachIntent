"""CLI for the Prompt v0.2-rc.1 development generation runner.

Two explicit modes:

* ``--dry-run``  — discover the 30 Pilot inputs, verify they match the canonical
  population (A=12, B=12, C=6, unique), and print the generation plan. No Hy3 /
  OpenRouter call is made and no result directory is created.
* ``--execute``  — REAL generation of the 30 cases with the candidate Prompt
  **v0.2-rc.1** through the frozen Generator service (``generate_speech_plan``).
  Exactly one first-call attempt per case; no retry, no self-repair.

The experimental condition for ``--execute`` is STRICTLY FIXED and must not be
influenced by ambient shell environment variables:

* The only accepted credential is ``OPENROUTER_API_KEY`` (no fallback to
  ``HY3_API_KEY``). If it is missing/empty, the run aborts with exit 2 BEFORE any
  API call or result-directory creation.
* The connection/model are hard-coded: OpenRouter
  (``https://openrouter.ai/api/v1``) with model ``tencent/hy3``. Pre-existing
  ``HY3_BASE_URL`` / ``HY3_MODEL`` environment variables are deliberately ignored
  (the client is constructed explicitly, not via ``from_env``).
* ``prompt_version="v0.2-rc.1"`` (explicit, never the service default),
  ``temperature=0``, ``retry=False``, ``self_repair=False``.

Exactly one of ``--dry-run`` / ``--execute`` is required. Running with neither
flag, or with both, fails fast with a usage message (exit 2) and never performs
a real API call.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from teachintent.generator.client import Hy3Client
from teachintent.prompt_development.development_runner import (
    API_GATEWAY,
    CANDIDATE_PROMPT_VERSION,
    GENERATOR_MODEL,
    run_development_batch,
)

# Explicit, strictly-fixed experimental condition for --execute. These are NOT
# read from the environment; the client is built with these exact values so the
# real run can never be polluted by ambient HY3_* shell variables.
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_EXECUTE_MODEL = GENERATOR_MODEL  # "tencent/hy3"

# Explicit, unambiguous usage string shown on fail-fast (no flag / both flags).
_USAGE = (
    "usage: run_prompt_v0_2_rc1_development.py {--dry-run | --execute}\n"
    "  --dry-run   Discover + validate the 30 Pilot inputs and print the plan (no API call).\n"
    "  --execute   REAL generation of the 30 cases with Prompt v0.2-rc.1 "
    "(requires OPENROUTER_API_KEY).\n"
    "  Exactly one of --dry-run / --execute is required; neither or both is an error."
)


def _require_api_key() -> int | None:
    """Fail-fast credential check for ``--execute``.

    Returns ``None`` if ``OPENROUTER_API_KEY`` is present and non-empty, or the
    exit code (``2``) if it is missing/empty. No fallback to ``HY3_API_KEY`` is
    performed. Must be called BEFORE constructing the client or creating any
    result directory.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        print(
            "ERROR: OPENROUTER_API_KEY is required for --execute and is "
            "missing/empty. Aborting before any Hy3 API call.",
            file=sys.stderr,
        )
        return 2
    return None


def main(argv: list[str] | None = None, *, client: Any | None = None) -> int:
    """CLI entry point. Returns a process exit code.

    Parameters
    ----------
    argv:
        Argument vector (defaults to ``sys.argv[1:]``).
    client:
        Optional pre-built :class:`Hy3Completer` injected for tests. When ``None``
        (production), ``--execute`` builds the real, strictly-fixed client.
    """
    parser = argparse.ArgumentParser(
        prog="run_prompt_v0_2_rc1_development.py",
        description="Prompt v0.2-rc.1 development generation runner.",
        usage=_USAGE,
        add_help=True,
    )
    # Exactly one of the two modes is required; argparse enforces exclusivity and
    # the required-ness, failing fast (exit 2) with usage otherwise.
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover + validate the 30 Pilot inputs and print the plan (no API call).",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="REAL generation of the 30 cases with Prompt v0.2-rc.1 (requires OPENROUTER_API_KEY).",
    )
    args = parser.parse_args(argv)

    # ---- --dry-run: discovery + validation + plan, no API call, no artifacts ----
    if args.dry_run:
        run_development_batch(None, dry_run=True, prompt_version=CANDIDATE_PROMPT_VERSION)
        return 0

    # ---- --execute: real generation ----
    # 1. Load .env (only to surface OPENROUTER_API_KEY if the user keeps it there;
    #    dotenv does NOT override already-set env vars, so this cannot clobber or
    #    pollute the fixed base_url/model below).
    from dotenv import load_dotenv

    load_dotenv()

    # 2. Credential preflight — before any client build / result dir.
    blocked = _require_api_key()
    if blocked is not None:
        return blocked

    # 3. Build the real client with the STRICTLY FIXED condition. No from_env(),
    #    so ambient HY3_BASE_URL / HY3_MODEL / HY3_API_KEY cannot leak in.
    if client is None:
        client = Hy3Client(
            api_key=os.environ["OPENROUTER_API_KEY"].strip(),
            base_url=_OPENROUTER_BASE_URL,
            model=_EXECUTE_MODEL,
        )

    # 4. Run: explicit candidate prompt_version; never the service default.
    run_development_batch(
        client, dry_run=False, prompt_version=CANDIDATE_PROMPT_VERSION
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
