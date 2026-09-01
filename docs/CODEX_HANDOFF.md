# Codex Handoff — TeachIntent

Precise snapshot of the repository at the moment of handoff from WorkBuddy.
Generated 2026-09-01. Re-verify before acting; the repo is the source of truth.

---

## Current branch

- Branch: `feat/prompt-v0.2-rc1`
- HEAD commit: `2252fde1c26049e514532ccf495d910a2090d6c0`
  - subject: `feat: add prompt v0.2 rc2`
  - committed: 2026-08-31 20:58:13 -0700
- Remote: `origin  git@github.com:juanmaoxiongmaoQAQ/TeachIntent.git`
- Remote status: local branch is in sync with `origin/feat/prompt-v0.2-rc1`
  (no ahead/behind divergence at handoff time).

## Current working tree

Tracked modifications (not yet committed):

```
 M scripts/run_prompt_v0_2_rc1_development_evaluation.py
 M src/teachintent/prompt_development/__init__.py
 M src/teachintent/prompt_development/development_evaluation.py
```

Untracked:

```
?? .pytest-basetemp/                                        (local temp — do NOT commit)
?? tests/test_prompt_v0_2_rc2_development_evaluation.py     (new test module — should be committed with the above)
```

`.pytest-basetemp/` is a local pytest temp directory and must not be committed.
`results/` is git-ignored, so all experiment artifacts below live outside git.

The three modified files are the parameterization of the paired development
evaluation to support `--prompt-version v0.2-rc.2` alongside the existing
`v0.2-rc.1` path (one shared framework, no duplicated logic). Frozen prompt
text (v0.1 / v0.2-rc.1 / v0.2-rc.2) is unchanged by these edits.

---

## Current research state

Only currently-valid facts, in chronological order.

### 1. Generator v0.1 canonical Pilot (frozen)

Block A (`controlled_contrast`)   — run `20260827-002543`, 12/12 success
Block B (`cross_domain_generalization`) — run `20260827-051547`, 12/12 success
Block C (`hard_adversarial`)      — run `20260827-074602`, 6/6 success

Total 30 cases. Model `tencent/hy3`, temperature 0, no retry/self-repair.
Paths under `results/pilot/block_{a,b,c}/`.

### 2. Evaluator v0.1 confirmatory validation

Run `20260829T154127Z` → **semantic validation PASS**.
Path: `results/evaluator_diagnostic_confirmatory/20260829T154127Z/`.
Protocol v0.2; holdout dataset 24 pairs / 48 plans; 138/144 evaluations
successful. This confirms Evaluator v0.1 against the frozen diagnostic protocol.

### 3. Generator v0.1 baseline evaluation (frozen protocol v0.2)

Run `20260830T095934Z`.
Path: `results/generator_v0_1_baseline_evaluation_v0_2/20260830T095934Z/`.
- eligible cases: 26/30
- successful semantic repeats: 73/90; total physical attempts: 136
- `source_population_sha256` = `a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b`

This is the frozen v0.1 baseline reused by all paired development evaluations.
It is never re-generated or re-Judged.

### 4. Prompt v0.2 development

**rc.1**
- generation run: `results/prompt_v0_2_rc1_development/20260831-052126`
  (30/30 generation success)
- development evaluation run: `results/prompt_v0_2_rc1_development_evaluation/20260831T103707Z`

Key finding: D5 improved, but `delivery_plan` was `{}` for **30/30** cases →
judged **delivery mode collapse**. rc.1 was **not frozen**.

**rc.2**
- generation run: `results/prompt_v0_2_rc2_development/20260831-153546`
  (30/30 generation success)
- delivery distribution: **27 empty / 3 non-empty**
- non-empty case IDs: `PILOT-A-COR-01`, `PILOT-C-COR-01`, `PILOT-C-SCA-01`

rc.2 uses "minimum justified control" — sparsity without zero control, unlike
rc.1's collapse.

### 5. rc.2 paired development evaluation

Run `results/prompt_v0_2_rc2_development_evaluation/20260901T043729Z`.

- 87/90 semantic repeats successful; 112 physical attempts (max 270)
- rc.2 eligible: 29/30; pair-eligible: 26/30 (v0.1 eligible 26)
- Evaluator v0.1 / Judge Prompt v0.1 / openrouter / `qwen/qwen3.5-plus-20260420`
  / temperature 0 / no structured output / no self-repair

Paired results (v0.1 → rc.2), n=26:

| dim | v0.1 mean | rc.2 mean | paired Δ mean | 95% CI | improved/tied/worsened |
|-----|-----------|-----------|---------------|--------|------------------------|
| D5 (primary) | 3.49 | 4.00 | +0.513 | [0.326, 0.699] | 16 / 10 / 0 |
| D4 (secondary) | 3.76 | 3.90 | +0.135 | [0.017, 0.252] | 10 / 15 / 1 |
| D1 (protected) | 3.97 | 3.95 | −0.026 | (CI incl. 0) | 0 / 24 / 2 |
| D2 (protected) | 4.00 | 4.00 | 0.0 | — | 0 / 26 / 0 |
| D3 (protected) | 3.97 | 3.99 | +0.013 | (CI incl. 0) | 2 / 23 / 1 |
| D6 (protected) | 3.95 | 3.97 | +0.026 | (CI incl. 0) | 4 / 20 / 2 |

Conclusion: **development evidence supports rc.2** (D5 strongly positive, D4
stable-positive, no systematic protected-dimension regression, delivery 27/3
not 30/0). This is **development evidence, not held-out confirmatory evidence**.
`verdict = None` — no mechanical PASS/FAIL threshold is defined.

---

## Current decision

- Prompt **v0.2-rc.2 is the candidate for the formal v0.2**.
- Next step is **NOT** further tuning on these 30 development cases.
- Next step is planning / executing a **held-out evaluation** and then a
  **final freeze**.
- Do **not** create an rc.3 unless new evidence reveals a clear, systematic
  problem.

## Pending repository action

The `development_evaluation` parameterization (3 modified files + the new
`tests/test_prompt_v0_2_rc2_development_evaluation.py`) is **not yet
committed or pushed**. It must be committed before any new work builds on it.

---

## Important paths (absolute)

Repository root: `<repository-root>`

Canonical Pilot runs:
- `results/pilot/block_a/20260827-002543/`
- `results/pilot/block_b/20260827-051547/`
- `results/pilot/block_c/20260827-074602/`

Evaluator confirmatory:
- `results/evaluator_diagnostic_confirmatory/20260829T154127Z/`

Generator baseline (frozen v0.2):
- `results/generator_v0_1_baseline_evaluation_v0_2/20260830T095934Z/`

rc.1 generation / evaluation:
- `results/prompt_v0_2_rc1_development/20260831-052126/`
- `results/prompt_v0_2_rc1_development_evaluation/20260831T103707Z/`

rc.2 generation / evaluation:
- `results/prompt_v0_2_rc2_development/20260831-153546/`
- `results/prompt_v0_2_rc2_development_evaluation/20260901T043729Z/`

Design / protocol documents:
- `docs/generator_prompt_v0.2_design_spec.md`
- `docs/generator_prompt_v0.2_experiment_protocol.md`
- `docs/generator_v0.1_evaluation_protocol_v0.2.md` (frozen baseline protocol)
- `docs/evaluator_spec_v0.1.md` (frozen)
- `docs/evaluator_diagnostic_protocol_v0.2.md` (frozen)
- `docs/problem_definition.md`, `docs/pedagogical_intents.md`,
  `docs/speech_plan_schema.md`, `docs/pilot_dataset_spec.md`

---

## Important hashes (verified from artifacts)

| hash | value |
|------|-------|
| source_population_sha256 (baseline v0.2) | `a880833add59293a6de13b046c75af6527483eba5bfb3e1a35aebbf2f129706b` |
| Evaluator diagnostic holdout dataset SHA | `f14e2a87c7a62345963d389441388c4f74a91b9b5bb00457ed580da285420569` |
| Evaluator diagnostic development dataset SHA | `a004715338c97d9e85b92fe0221a18631aa2884f6bb8b1d78a66066ccdd12664` |
| Judge Prompt v0.1 SHA | `b2eac7b0750ab1221ec8c6a554d82b5edc313e637435ec93015cf18cb9ef9f28` |
| Generator eval protocol v0.2 document SHA | `c30cb89096fa945111e4e93b59777ce91c29951b797c1a970848ab41b050caab` |
| Evaluator diagnostic protocol v0.2 document SHA | `c8b5a25669dfb80e11d0653e2dd57cea23e94f87e2369eed8f364b9895e5a925` |

All hashes were read from `run_manifest.json` files in the corresponding run
directories. Verify against the live manifests before relying on them.

Schema versions: Input `1.0.0-rc.2`; Speech Plan `1.0.0-rc.3`.
