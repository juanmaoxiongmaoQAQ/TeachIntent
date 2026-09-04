# TeachIntent

> **Personal / activity project.** TeachIntent is an independent open-practice
> project built with Hy3. It is not an official Tencent product, project, or
> release, and its findings do not represent Tencent.

TeachIntent is a pedagogical speech planning layer for AI Tutors. Given
teaching content, teaching context, learner state, and a teacher-selected
pedagogical intent, Hy3 produces a validated, machine-actionable **Speech
Plan**:

- **WHAT TO SAY**: ordered tutor wording;
- **HOW TO SAY**: optional delivery controls for tone, emotion, and prosody.

TeachIntent addresses a real AI-tutoring problem. A generic answer generator
can produce factually plausible text while performing the wrong teaching move,
over-answering a scaffolding request, ignoring learner frustration, or filling
speech controls mechanically. TeachIntent makes the teaching action and its
delivery choices explicit before any TTS renderer is involved.

## Quick Start

Requirements: Python 3.10 or newer.

```bash
git clone https://github.com/juanmaoxiongmaoQAQ/TeachIntent.git
cd TeachIntent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/run_demo.py
```

The last command is deterministic and offline: it displays an existing,
schema-valid Hy3 artifact from the release sanity run. It does not need an API
key.

To make one live Hy3 call:

```bash
cp .env.example .env
# Edit .env and set HY3_API_KEY.
python scripts/run_demo.py \
  --live \
  --example corrective-feedback \
  --prompt-version v0.2
```

The demo also supports `elicitation`, `scaffolding`, and `supportive-feedback`
examples and explicit `v0.1` / `v0.2` prompt selection. See [Quick Demo](#quick-demo)
for the product-facing web walkthrough.

## Quick Demo

Start the local web app:

```bash
.venv/bin/python scripts/run_web_api.py \
  --host 127.0.0.1 \
  --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

1. **Explore** requires no API credential. It shows recorded Speech Plans,
   evaluator evidence, and curated voice A/B playback from committed public
   artifacts.
2. **Live Studio** requires `HY3_API_KEY` for generation and
   `OPENROUTER_API_KEY` only if the user clicks independent evaluation.
3. **Intent Compare** requires `HY3_API_KEY`. It changes only the selected
   pedagogical intent and runs two user-triggered Hy3 generations; it does not
   call the Judge or TTS.

## Why TeachIntent

Without TeachIntent:

```text
Teaching context -> unconstrained tutor response
```

With TeachIntent:

```text
Teaching context + explicit pedagogical intent
  -> structured Speech Plan
  -> auditable evaluation
  -> optional voice realization
```

Hy3 is the generator, an independent Qwen Judge is the evaluator, and
Qwen3-TTS is an optional downstream renderer for curated examples. TeachIntent
does not claim to be a new foundation model, a new TTS architecture, or proof
of causal pedagogical improvement.

## User Scenario and Problem Definition

Target users are developers and researchers building AI tutors, instructional
agents, or educational speech systems. A tutor policy has already selected a
teaching action; TeachIntent plans the single instructional turn that realizes
it.

The core mapping is:

```text
(C, P, L, G) -> (V, D)
```

| Symbol | Meaning |
|---|---|
| `C` | instructional content and authoritative content anchor |
| `P` | pedagogical context, including the learner's current utterance |
| `L` | explicitly supplied learner knowledge and affective state |
| `G` | the given pedagogical intent |
| `V` | `verbal_plan`: ordered, sayable tutor segments |
| `D` | `delivery_plan`: optional global and segment-level delivery controls |

The LLM is needed because the mapping is conditional and open-ended: the same
content requires different language under different intents, learner states,
and immediate contexts. A fixed template cannot reliably preserve intent
boundaries, adapt the instructional move, resist embedded instructions, and
decide when a delivery control is genuinely useful. Hy3 performs this planning
step while JSON Schema and Pydantic enforce the output contract.

TeachIntent is **not** a TTS architecture. Its research evidence ends at the
validated Speech Plan. An optional Qwen3-TTS adapter can render a small,
explicitly supported subset for demonstration, but does not clone voices,
infer pedagogical intent, or manage multi-turn tutoring policy.

## Six Pedagogical Intents

The v1 control space contains six intents, classified by the intended change in
the learner rather than by surface sentence form:

| Intent | Intended teaching action |
|---|---|
| `elicitation` | reveal the learner's current understanding or reasoning |
| `scaffolding` | provide a bounded hint or intermediate step while preserving learner work |
| `explanation` | supply knowledge, clarification, reasoning, or procedure |
| `corrective_feedback` | identify and repair an existing error or misconception |
| `supportive_feedback` | reinforce valid progress, strategy, confidence, or engagement |
| `extension` | deepen or transfer established understanding |

The intent is supplied by the calling tutor system; Hy3 does not choose it.
Full definitions and boundaries are in
[docs/pedagogical_intents.md](docs/pedagogical_intents.md).

## Speech Plan

Every successful generation returns Speech Plan Schema `1.0.0-rc.3`:

```json
{
  "schema_version": "1.0.0-rc.3",
  "verbal_plan": {
    "segments": [
      {"segment_id": "seg_01", "text": "..."}
    ]
  },
  "delivery_plan": {
    "global": {"attitudinal_tone": "firm but supportive"}
  }
}
```

`verbal_plan` is the actual ordered tutor wording. `delivery_plan` contains
only pedagogically justified tone, emotion, relative prosody, prominence,
contour, or boundary controls. It may legally be `{}`: renderer defaults are
preferable to unnecessary control. See
[docs/speech_plan_schema.md](docs/speech_plan_schema.md).

## Architecture

```text
TeachIntent Input (C, P, L, G)
        |
        v
JSON Schema + Pydantic input validation
        |
        v
Versioned prompt registry (v0.1 or frozen v0.2)
        |
        v
Hy3 planner, temperature 0, single pass
        |
        v
JSON parse + JSON Schema + Pydantic Speech Plan validation
        |
        +------> verbal_plan ----> tutor / TTS adapter
        |        delivery_plan --> renderer controls
        |
        v
Evaluator v0.1
  Layer 0: deterministic contract gate
  Layer 1: six-dimension LLM judge + grounded evidence + critical flags
        |
        v
Machine-readable diagnostic artifact

Optional demonstration path (outside the frozen research evaluation):
Speech Plan --> conservative Qwen3-TTS CustomVoice adapter --> A/B WAV pair
```

The generator deliberately performs no retry or self-repair: a first-call
failure remains observable. Evaluation acquisition retries are separate and
are allowed only when no legal evaluator artifact was produced, never because
of a low score.

## Evaluation Method

Evaluator v0.1 is a diagnostic instrument, not a scalar reward. It assigns an
integer score from 0 (severe failure) to 4 (strong) on six independent
dimensions:

| ID | Dimension | Operational question |
|---|---|---|
| D1 | Pedagogical Intent Fidelity | Is this the intended kind of teaching move? |
| D2 | Content Faithfulness / Boundary | Is it grounded in the supplied content without contradiction or material expansion? |
| D3 | Learner-State Compatibility | Does it fit the supplied cognitive and affective state? |
| D4 | Intent-Specific Instructional Adequacy | How well is the requested teaching move executed? |
| D5 | Delivery Necessity / Sparsity | Are specified controls necessary and minimal? |
| D6 | Delivery–Pedagogy Alignment | Do chosen controls—or their omission—support the pedagogy? |

Every dimension requires grounded evidence and a justification. Seven explicit
critical flags cover injection compliance, false affirmation, content
contradiction, off-anchor content, learner humiliation, harmful self-label
reinforcement, and hostile delivery. The deterministic service computes an
unweighted overall percentage only as a secondary summary; no universal
semantic pass threshold exists.

The complete method, difficult-case design, and evaluator validation are in
[docs/EVALUATION_METHOD.md](docs/EVALUATION_METHOD.md).

## Evaluator Validation

Evaluator v0.1 was tested independently of prompt development on 24 frozen
holdout reference/degraded pairs across eight controlled perturbation families,
with three repeats per plan (144 planned Judge calls). Confirmatory diagnostic
run `20260829T154127Z` produced 138 valid artifacts and passed its frozen
Protocol v0.2 criteria:

| Measure | Result | Frozen criterion |
|---|---:|---:|
| Primary directional accuracy | 23/24 = 95.83% | >=85% |
| Mean primary targeted drop | 2.6528 | >=1.0 |
| Protected-dimension MAE | 0.2552 | <=0.5 |
| Within-one repeatability | 99.62% | >=95% |
| Semantic pair coverage | 24/24 | >=90% |
| Critical flags | TP 10, FN 0, FP 1 | reported diagnostically |

This validates discrimination and score consistency under the frozen
conditions; it does not make the LLM judge infallible.

## Main Experimental Findings

All findings below reuse recorded artifacts; no experiment is run by the demo.

| Stage | Evidence and finding |
|---|---|
| Canonical Pilot | 30/30 Hy3 v0.1 generations succeeded across controlled, cross-domain, and hard/adversarial cases. |
| Generator v0.1 baseline | 26/30 cases were evaluation-eligible. D1–D6 means were 3.974, 4.000, 3.974, 3.763, **3.487**, 3.949. D5 exposed unnecessary delivery control as the clearest weakness. |
| Prompt v0.2-rc.1 | D5 improved, but all 30 plans had empty `delivery_plan`; this was rejected as delivery mode collapse. |
| Prompt v0.2-rc.2 | 30/30 generated; delivery was 27 empty / 3 non-empty. On 26 paired development cases, D5 delta was +0.5128 and D4 delta +0.1346, with no systematic protected-dimension regression. |
| Formal Prompt v0.2 | Frozen as a model-facing byte-identical alias of rc.2. Selection is supported by development evidence, not a formal held-out confirmation. |
| Release sanity | 12 new cases. Generation was 12/12 for v0.1 and 11/12 for v0.2. Five Judge-available pairs had no worsened dimension; v0.2 delivery was 9 empty / 2 non-empty among 11 valid plans. Upstream rate limits constrained evaluation coverage. |

The v0.1 -> rc.1 -> rc.2 story matters: sparsity cannot be judged from D5
alone. rc.1 showed that an always-empty plan can look sparse, so D5, D6, and
the measured empty/non-empty distribution must be interpreted together. rc.2
introduced the frozen **minimum justified control** behavior.

Detailed tables and representative case analysis are in
[docs/RESULTS.md](docs/RESULTS.md); observed failure modes and capability
boundaries are in [docs/FAILURE_ANALYSIS.md](docs/FAILURE_ANALYSIS.md).

## Demo

### Web App (React + FastAPI)

The product-facing Task 1 web app uses React, TypeScript, Vite, Tailwind CSS,
and FastAPI. The Explore page is public-first: recorded Speech Plans and
recorded Evaluator v0.1 evidence are served from committed demo artifacts, not
from git-ignored `results/`.

- `Explore` shows recorded examples, recorded Speech Plans, recorded Evaluator
  v0.1 results, synchronized evidence focus, and curated public Qwen3-TTS A/B
  audio when committed voice artifacts are present. Ordinary playback does not
  require a local TTS model.
- `Live Studio` lets a user submit a teaching scenario, call Hy3 once, then
  explicitly run the independent frozen Evaluator v0.1 Judge. Live generation
  requires `HY3_API_KEY`; live evaluation requires `OPENROUTER_API_KEY` in
  local `.env`. Live Studio does not generate TTS.
- `Intent Compare` holds the same teaching context constant, changes only two
  selected pedagogical intents, runs two user-triggered Hy3 generations, and
  shows a deterministic structural comparison of the resulting Speech Plans.
  It does not call the Judge or generate TTS. This is an application-level
  controlled input comparison, not a statistical experiment or causal claim.

Terminal 1:

```bash
.venv/bin/python scripts/run_web_api.py \
  --host 127.0.0.1 \
  --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The Gradio demo remains available as a legacy research/demo interface.

### Recommended 2-minute walkthrough

1. Open `Explore` on `corrective-feedback`: show **WHAT TO SAY** /
   **HOW TO SAY**, click D6 or D2 to show synchronized evidence, then play
   Neutral and TeachIntent voice realization.
2. Open `Intent Compare`: load the showcase scenario, keep
   `corrective_feedback` vs `scaffolding`, and show how the same context leads
   to different Speech Plans.
3. Open `Live Studio`: show that custom generation and optional independent
   evaluation exist, but avoid waiting on live APIs during a two-minute
   recording.

### Legacy Gradio visual demo

The single-page app has two modes:

- `Explore` uses existing recorded artifacts and makes no API call. It shows
  the recorded Speech Plan, recorded Evaluator v0.1 result, evidence trace,
  and optional curated Qwen3-TTS A/B audio.
- `Live Studio` builds a validated TeachIntent input and calls Hy3 once through
  the existing live generation pipeline. After generation, the user may
  explicitly run the independent Evaluator v0.1 Judge and inspect the same
  evidence trace workbench.
  Live generation requires `HY3_API_KEY`; live evaluation requires
  `OPENROUTER_API_KEY` in local `.env`.

```bash
python -m pip install -e ".[demo]"
python scripts/run_visual_demo.py
```

Open `http://127.0.0.1:7860`. The app never runs a live Judge for recorded
examples. For custom scenarios, the live Judge runs only when the user clicks
`Evaluate this plan`. Audio rendering is shown for curated recorded examples
only unless an existing WAV pair is found.

### Terminal demo

Recorded mode is safe for a screen recording and makes no network request:

```bash
python scripts/run_demo.py
python scripts/run_demo.py --example elicitation --prompt-version v0.2
python scripts/run_demo.py --example scaffolding --prompt-version v0.1
python scripts/run_demo.py --json
```

Live mode makes exactly one Hy3 generation call through the normal validation
pipeline:

```bash
python scripts/run_demo.py \
  --live \
  --example scaffolding \
  --prompt-version v0.2
```

The public examples are existing valid artifacts, not newly generated results:

- [elicitation](examples/elicitation.json)
- [corrective feedback with selective delivery control](examples/corrective_feedback.json)
- [scaffolding with selective delivery control](examples/scaffolding.json)
- [supportive feedback with intentionally empty delivery control](examples/supportive_feedback.json)

### Optional local Qwen3-TTS A/B

The renderer compares the same exact words, voice, model, language, seed, and
generation path. Only the CustomVoice `instruct` value changes: neutral uses an
empty instruction and planned uses the conservative `delivery_plan` mapping.

> **Same words. Same voice. Different pedagogical delivery.**

Qwen3-TTS is deliberately a separate, heavy optional install. The command may
download model weights if the selected model is not already cached; do not run
it unless that is intended and a compatible GPU environment is available.

```bash
python -m pip install -e ".[tts]"
python scripts/render_tts_demo.py \
  --example corrective-feedback \
  --prompt-version v0.2 \
  --speaker Vivian \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
  --device-map cuda:0 \
  --dtype bfloat16
```

This creates `neutral.wav`, `planned.wav`, and an auditable
`render_manifest.json` under the ignored `results/tts_demo/` tree. Unsupported
pitch and segment-local controls are listed, not approximated. See
[docs/TTS_RENDERER.md](docs/TTS_RENDERER.md).

To publish already-rendered curated audio for the React Explore page:

```bash
python scripts/export_public_voice_artifacts.py \
  --source-root results/tts_demo \
  --output-root public_demo/voice
```

This command copies and verifies existing WAV artifacts. It does not invoke
Qwen3-TTS, Hy3, or the Judge. The web app reads only `public_demo/voice/` for
recorded playback and does not fallback to git-ignored `results/`. The current
Qwen3-TTS adapter supports only a conservative utterance-level subset
(`attitudinal_tone`, `emotion`, `speaking_rate`, `volume`); unsupported
Speech Plan controls remain visible as preserved but not realized.

The <=2 minute recording plan is in
[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Installation, Configuration, and Testing

Copy the environment template and place only local credentials in `.env`:

```bash
cp .env.example .env
```

The established Hy3 condition is:

```text
HY3_BASE_URL=https://openrouter.ai/api/v1
HY3_MODEL=tencent/hy3
```

Run the test suite and offline dataset checks:

```bash
python -m pip install -e ".[dev]"
pytest -q
python scripts/validate_pilot_cases.py cases/pilot/blocks/block_c_hard_adversarial.jsonl
python scripts/validate_release_sanity.py
```

Research runners under `scripts/` may make many paid API calls; read their
frozen protocol before running them. `scripts/run_demo.py` and
`scripts/run_visual_demo.py` call no API unless live mode is explicitly
selected. `scripts/render_tts_demo.py` runs a local model but may fetch weights
through the model loader when they are not already cached.

## Repository Map

```text
cases/                    self-constructed Pilot, diagnostic, and sanity sets
docs/                     contracts, protocols, public results, and analysis
examples/                 recorded valid Hy3 input/output examples
schemas/                  JSON Schema contracts
scripts/                  demo, validators, and experiment entry points
src/teachintent/          generator, evaluator, renderers, models, runners
tests/                    automated regression suite
results/                  local immutable experiment evidence (git-ignored)
```

Task‑1 coverage is tracked in
[docs/TASK1_COMPLIANCE.md](docs/TASK1_COMPLIANCE.md).

## Limitations

- The system plans one instructional turn; it does not select intent or manage a dialogue.
- Pilot and sanity outputs are zh-CN; multilingual generalization is untested.
- The research evaluator assesses the pre-audio Speech Plan. The optional TTS
  adapter is a best-effort demonstration; no audio quality, acoustic-control
  accuracy, or listener outcome has been evaluated.
- The evaluator is LLM-assisted and can suffer API, parsing, grounding, and judgment errors.
- Generator experiments use small, self-authored datasets rather than classroom outcomes or educator ratings.
- Prompt v0.2 has development and release-sanity support, but no paper-grade held-out confirmatory comparison.
- Provider availability affected some evaluator artifacts, especially in release sanity.

## Security and Provenance

No credential is hard-coded or tracked. `.env`, local experiment artifacts,
and common private-key formats are ignored. Do not commit API keys,
Authorization headers, or local result directories. Recorded runs preserve
model, prompt, dataset, protocol, and hash provenance; unfavorable and
operational failures are not silently removed.

## License and Disclaimer

Source code and documentation are available under the [MIT License](LICENSE).

TeachIntent is a personal research/activity project and an independent Hy3
application. It is not an official Tencent release. Hy3 and other named models
remain the property of their respective owners.
