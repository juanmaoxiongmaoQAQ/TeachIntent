# Optional Qwen3-TTS Demonstration Adapter

This adapter is a delivery demonstration layer, not a TeachIntent research
experiment and not part of the frozen Generator, Prompt, Evaluator, Judge, or
schema contracts. TeachIntent remains fully runnable without Qwen3-TTS.

## A/B Contract

Every render compares:

> **Same words. Same voice. Different pedagogical delivery.**

The two conditions use the same exact joined `verbal_plan` text, language,
CustomVoice speaker, Qwen model, seed, and generation method.

| Condition | `instruct` |
|---|---|
| Neutral | empty string |
| Planned | produced only from the supported `delivery_plan` fields below |

`render_manifest.json` records both condition inputs, the source Speech Plan,
supported and unsupported controls, hashes of the text and WAV files, backend
metadata, and all A/B invariants. Existing files are not overwritten unless
`--overwrite` is explicitly supplied.

## Conservative Mapping

Qwen3-TTS CustomVoice accepts a natural-language `instruct` value. The adapter
therefore emits qualitative instructions only; it does not claim exact acoustic
control.

| Speech Plan field | Adapter behavior |
|---|---|
| `global.attitudinal_tone` | Preserve the plan value as an utterance-level attitude instruction. |
| `global.emotion` | Preserve the plan value as an utterance-level emotion instruction. |
| `global.prosody.speaking_rate` | Map the schema category (`x-slow` … `x-fast`) to a qualitative rate instruction. |
| `global.prosody.volume` | Map the schema category (`x-soft` … `x-loud`) to a qualitative volume instruction. |
| `global.prosody.pitch_level`, `pitch_range` | Report unsupported; no F0 mapping is invented. |
| every `segment_overrides[*]` control | Report unsupported; the current adapter makes no segment-local realization claim. |

An empty `delivery_plan` produces an empty planned instruction. This preserves
the Prompt v0.2 rule that explicit delivery control is optional.

## Commands

Install the optional local runtime separately:

```bash
python -m pip install -e ".[tts]"
```

Render one existing release example:

```bash
python scripts/render_tts_demo.py \
  --example corrective-feedback \
  --prompt-version v0.2 \
  --speaker Vivian \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice \
  --device-map cuda:0 \
  --dtype bfloat16
```

The model identifier may be replaced with an already downloaded local path.
If the identifier is not cached, the Qwen loader may download weights. This
repository does not bundle weights and its automated tests never load a model,
use a GPU, or synthesize audio.

The implementation follows the official Qwen3-TTS CustomVoice interface:
[`QwenLM/Qwen3-TTS`](https://github.com/QwenLM/Qwen3-TTS). Runtime support and
speaker availability remain properties of the selected Qwen release/model.

## Boundaries

- Natural-language instruction following is best-effort and may vary by model,
  speaker, language, hardware, and generation implementation.
- A fixed random seed improves comparability but does not establish universal
  bitwise determinism.
- No exact pitch, duration, loudness, prominence, contour, or boundary behavior
  is claimed.
- The pre-audio Evaluator v0.1 score must not be presented as a score of the
  rendered audio.
- Listening impressions from the Task‑1 demo are illustrative, not
  confirmatory evidence.
