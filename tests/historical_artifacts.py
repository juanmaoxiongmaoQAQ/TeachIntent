"""Explicit prerequisites for optional, immutable experiment evidence.

Only absent run roots permit a skip. An existing but incomplete/corrupt run,
including a dangling symlink, must reach the original assertions and fail.
No application exception is caught and no evidence is downloaded or generated.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_RUNS = {
    "pilot_a": "results/pilot/block_a/20260827-002543",
    "pilot_b": "results/pilot/block_b/20260827-051547",
    "pilot_c": "results/pilot/block_c/20260827-074602",
    "baseline_v2": "results/generator_v0_1_baseline_evaluation_v0_2/20260830T095934Z",
    "rc1_generation": "results/prompt_v0_2_rc1_development/20260831-052126",
    "rc2_generation": "results/prompt_v0_2_rc2_development/20260831-153546",
}


def missing_runs(names: tuple[str, ...], root: Path = REPO_ROOT) -> list[str]:
    if not names or any(name not in HISTORICAL_RUNS for name in names):
        raise pytest.UsageError("historical_artifacts requires known run names")
    return [
        HISTORICAL_RUNS[name]
        for name in names
        if not (root / HISTORICAL_RUNS[name]).exists()
        and not (root / HISTORICAL_RUNS[name]).is_symlink()
    ]


def pytest_addoption(parser):
    parser.addoption(
        "--require-historical-artifacts", action="store_true",
        help="Fail instead of skipping selected tests whose historical run roots are absent.",
    )


def pytest_runtest_setup(item):
    for marker in item.iter_markers("historical_artifacts"):
        if marker.kwargs:
            raise pytest.UsageError("historical_artifacts takes only positional run names")
        missing = missing_runs(marker.args)
        if missing:
            reason = "Missing optional frozen run(s): " + ", ".join(missing)
            reason += "; restore original evidence only; see docs/TESTING.md"
            if item.config.getoption("--require-historical-artifacts"):
                pytest.fail(reason, pytrace=False)
            pytest.skip(reason)
