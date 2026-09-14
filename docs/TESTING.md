# Offline release and historical tests

Run from a repository checkout using Python 3.10+ with `pip install -e '.[dev]'`.
Core tests use fake clients/backends and committed examples. They do not require
Hy3/OpenRouter keys, model weights, a GPU or private historical results.

## Core release gate

```bash
mkdir -p outputs/tmp
export TMPDIR="$PWD/outputs/tmp"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m 'not historical_artifacts'
git diff --check
git status --short
```

Use `.venv/bin/python` when the virtual environment is not activated. Disabling
third-party pytest plugin autoload keeps unrelated locally installed plugins out
of the gate. The repository's explicitly registered prerequisite plugin still
loads. Pytest creates a unique `outputs/pytest/run-<uuid>/` base when none is
supplied; an explicit `--basetemp` should also name a **fresh** project-local
path. Never reuse a historical artifact directory as pytest's base: pytest owns
and may clear that base. `project_tmp_path` diagnostic fixtures separately use
unique directories under `outputs/offline-tests/`.

Core includes contract, parsing, prompt compatibility, evidence grounding,
reducer, failure taxonomy, Web API, recorded-showcase and mock renderer tests.
Offline experimental regression tests remain in this gate. A file's historical
name does not remove its pure unit tests from core.

Frontend, after `npm ci` in `frontend/`:

```bash
npm test
npm run build
```

Set `TMPDIR` and `npm_config_cache` to project-local directories as in the README.
Vitest uses mocked fetch/media; it does not establish real browser timing or
human audio quality. The build includes TypeScript checking.

## Historical artifact-dependent tests

Individual tests in seven Pilot/baseline/rc-development modules carry
`@pytest.mark.historical_artifacts("run_name", ...)`. The names resolve to these
exact immutable run roots in `tests/historical_artifacts.py`:

| Name | Original run root relative to TeachIntent |
|---|---|
| `pilot_a` | `results/pilot/block_a/20260827-002543/` |
| `pilot_b` | `results/pilot/block_b/20260827-051547/` |
| `pilot_c` | `results/pilot/block_c/20260827-074602/` |
| `baseline_v2` | `results/generator_v0_1_baseline_evaluation_v0_2/20260830T095934Z/` |
| `rc1_generation` | `results/prompt_v0_2_rc1_development/20260831-052126/` |
| `rc2_generation` | `results/prompt_v0_2_rc2_development/20260831-153546/` |

The registry was audited against source calls and fixtures, not generated from
failed-test names. It includes CLI credential checks whose historical CLI
performs frozen-population preflight **before** checking credentials. Pure
validation/aggregation tests remain unmarked. The rc.2 wrong-prompt test also
requires the rc.1 run it deliberately passes to the rc.2 loader.

```bash
# Read-only tests with visible missing-prerequisite reasons:
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m historical_artifacts -rs

# Strict evidence verification after restoring the original runs:
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -m historical_artifacts --require-historical-artifacts

# Everything available in this checkout:
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -rs
```

Only a **missing named run root** permits an automatic skip. An existing empty
run, missing file within a restored run, invalid JSON, wrong run identity,
fingerprint mismatch or dangling symlink still reaches the original tests and
can fail. A typo or empty prerequisite marker is a configuration error.
Strict mode turns missing prerequisites into errors instead of skips.

If one of several required roots is absent, the dependent test cannot run; a
skip is not a validation of the other roots. Use strict mode after restoring the
complete required evidence set. No catch-all `FileNotFoundError`, `xfail`, score
change, replacement fixture, download or regeneration is used. Assertions and
experiment implementations remain unchanged.

These runs are intentionally not required for a public clone's core gate.
Restore original evidence from an authorized archive only if historical
verification is needed. Do not recreate unfavorable runs, fabricate manifests,
change frozen contracts or commit `results/` to turn the suite green. Portable
Explore artifacts under `examples/` and `public_demo/` are separate, committed
release dependencies and are **not** covered by missing-history skips.

## Product UI regression boundary

Frontend tests cover Chinese navigation, forms, example-only filling, explicit
generation/evaluation/rendering, attached delivery labels, folded raw evidence,
optional audio failure, and sequential playback. Browser review uses real local
servers with frozen examples and intercepted POST responses; it never calls a
model provider. Review captures stay in ignored `outputs/ui-review/`; selected
actual product screenshots are committed under `docs/assets/`.

Privacy tests intentionally contain synthetic absolute paths such as
`/Users/example/private` and `/opt/example-models/` to verify redaction. These
are test inputs, not deployment paths or personal machine information.
