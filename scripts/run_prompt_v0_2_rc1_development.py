"""CLI for the Prompt v0.2 development generation runner (version-parameterized).

Two explicit modes:

* ``--dry-run``  — discover the 30 Pilot inputs, verify they match the canonical
  population (A=12, B=12, C=6, unique), and print the generation plan. No Hy3 /
  OpenRouter call is made and no result directory is created.
* ``--execute``  — REAL generation of the 30 cases with the selected candidate
  Prompt (**v0.2-rc.1** or **v0.2-rc.2**) through the frozen Generator service
  (``generate_speech_plan``). Exactly one first-call attempt per case; no retry,
  no self-repair.

The candidate prompt is chosen with ``--prompt-version {v0.2-rc.1,v0.2-rc.2}``.
It defaults to **v0.2-rc.1**, so the historical rc.1 path is unchanged and rc.2
can never be selected silently — an rc.2 run always names itself explicitly.

The experimental condition for ``--execute`` is STRICTLY FIXED and must not be
influenced by ambient shell environment variables:

* The only accepted credential is ``OPENROUTER_API_KEY`` (no fallback to
  ``HY3_API_KEY``). If it is missing/empty, the run aborts with exit 2 BEFORE any
  API call or result-directory creation.
* The connection/model are hard-coded: OpenRouter
  (``https://openrouter.ai/api/v1``) with model ``tencent/hy3``. Pre-existing
  ``HY3_BASE_URL`` / ``HY3_MODEL`` environment variables are deliberately ignored
  (the client is constructed explicitly, not via ``from_env``).
* ``prompt_version`` selected via ``--prompt-version`` (default ``v0.2-rc.1``),
  passed explicitly to the Generator; ``temperature=0``, ``retry=False``,
  ``self_repair=False``.

Each candidate version writes to its own results directory
(``results/prompt_v0_2_rc1_development/`` vs ``results/prompt_v0_2_rc2_development/``),
so an rc.2 run can never overwrite the finished rc.1 run.

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
    SUPPORTED_PROMPT_VERSIONS,
    run_development_batch,
)

# Explicit, strictly-fixed experimental condition for --execute. These are NOT
# read from the environment; the client is built with these exact values so the
# real run can never be polluted by ambient HY3_* shell variables.
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_EXECUTE_MODEL = GENERATOR_MODEL  # "tencent/hy3"

# Explicit, unambiguous usage string shown on fail-fast (no flag / both flags).
_USAGE = (
    "usage: run_prompt_v0_2_rc1_development.py {--dry-run | --execute} "
    "[--prompt-version VERSION]\n"
    "  --dry-run   Discover + validate the 30 Pilot inputs and print the plan (no API call).\n"
    "  --execute   REAL generation of the 30 cases with the selected candidate Prompt "
    "(requires OPENROUTER_API_KEY).\n"
    "  --prompt-version {v0.2-rc.1,v0.2-rc.2}\n"
    "              Candidate Prompt to generate with (default: v0.2-rc.1).\n"
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
        description=(
            "Prompt v0.2 development generation runner "
            "(--prompt-version v0.2-rc.1 | v0.2-rc.2; default v0.2-rc.1)."
        ),
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
        help="REAL generation of the 30 cases with the selected candidate Prompt "
        "(requires OPENROUTER_API_KEY).",
    )
    # default=None so we can tell an explicit selection from the rc.1 default.
    parser.add_argument(
        "--prompt-version",
        choices=list(SUPPORTED_PROMPT_VERSIONS),
        default=None,
        help="Candidate Prompt to generate with (default: v0.2-rc.1). "
        "v0.2-rc.2 must be named explicitly.",
    )
    args = parser.parse_args(argv)

    explicit_selection = args.prompt_version is not None
    prompt_version = args.prompt_version or CANDIDATE_PROMPT_VERSION

    # ---- --dry-run: discovery + validation + plan, no API call, no artifacts ----
    if args.dry_run:
        run_development_batch(
            None, dry_run=True, prompt_version=prompt_version
        )
        return 0

    # ---- --execute: real generation ----
    # 0. State the selected prompt version unambiguously before any API contact,
    #    so an rc.2 run can never be confused with the rc.1 default.
    print(
        f"prompt_version = {prompt_version} "
        f"({'explicitly requested' if explicit_selection else 'default'})"
    )
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
    manifest = run_development_batch(
        client, dry_run=False, prompt_version=prompt_version
    )
    _print_delivery_distribution(manifest)
    return 0


def _print_delivery_distribution(manifest: dict) -> None:
    """Print the empty vs. non-empty ``delivery_plan`` diagnostic for a finished run.

    Reporting only — no threshold is evaluated or implied.
    """
    dist = manifest.get("delivery_distribution")
    if not dist:
        return
    print()
    print("delivery_plan distribution")
    print(f"  total cases = {dist['total_cases']}")
    print(f"  empty = {dist['empty_count']}")
    print(f"  non-empty = {dist['non_empty_count']}")
    print(f"  without parsed plan = {dist['without_parsed_plan']}")
    print("  by intent (empty / non-empty):")
    for intent, bucket in dist["by_intent"].items():
        print(
            f"    {intent:<20} {bucket['empty']} / {bucket['non_empty']}"
        )
    ids = dist["non_empty_case_ids"]
    print(f"  non-empty case IDs = {ids if ids else '[]'}")


if __name__ == "__main__":
    raise SystemExit(main())
