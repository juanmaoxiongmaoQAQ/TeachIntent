"""Missing optional evidence is distinct from a broken restored run."""

from types import SimpleNamespace

import pytest

import historical_artifacts as boundary


def test_only_absent_run_roots_are_optional(tmp_path):
    assert boundary.missing_runs(("baseline_v2",), tmp_path)
    run = tmp_path / boundary.HISTORICAL_RUNS["baseline_v2"]
    run.mkdir(parents=True)
    # Missing manifest, invalid JSON and wrong run identity must reach real tests.
    assert boundary.missing_runs(("baseline_v2",), tmp_path) == []
    (run / "run_manifest.json").write_text("not JSON")
    assert boundary.missing_runs(("baseline_v2",), tmp_path) == []


def test_dangling_symlink_is_not_treated_as_optional(tmp_path):
    run = tmp_path / boundary.HISTORICAL_RUNS["rc1_generation"]
    run.parent.mkdir(parents=True)
    run.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    assert boundary.missing_runs(("rc1_generation",), tmp_path) == []


@pytest.mark.parametrize("names", [(), ("typo",)])
def test_unknown_or_empty_prerequisites_fail(names, tmp_path):
    with pytest.raises(pytest.UsageError):
        boundary.missing_runs(names, tmp_path)


@pytest.mark.parametrize("strict", [False, True])
def test_missing_evidence_skip_or_strict_failure(tmp_path, monkeypatch, strict):
    monkeypatch.setitem(boundary.HISTORICAL_RUNS, "unit_run", str(tmp_path / "absent"))
    marker = pytest.mark.historical_artifacts("unit_run").mark
    item = SimpleNamespace(
        iter_markers=lambda name: [marker],
        config=SimpleNamespace(getoption=lambda name: strict),
    )
    outcome = pytest.fail.Exception if strict else pytest.skip.Exception
    with pytest.raises(outcome, match="Missing optional frozen run.*restore original evidence"):
        boundary.pytest_runtest_setup(item)


def test_present_incomplete_evidence_and_unmarked_tests_are_not_skipped(tmp_path, monkeypatch):
    monkeypatch.setitem(boundary.HISTORICAL_RUNS, "unit_run", str(tmp_path))
    marker = pytest.mark.historical_artifacts("unit_run").mark
    for markers in ([], [marker]):
        boundary.pytest_runtest_setup(SimpleNamespace(iter_markers=lambda name: markers))
