"""Opt-in v0.4: natural verbal units and expressive, sparse local delivery.

Reuses the v0.2 contract and user message without changing v0.2 or v0.3.
This is prompt guidance, not a renderer rule or validated acoustic outcome.
"""

from __future__ import annotations

from .speech_plan_v0_2 import SpeechPlanPrompt
from .speech_plan_v0_2 import build_speech_plan_prompt as _build_v02

PROMPT_VERSION = "v0.4"

_V04_GUIDANCE = """
# v0.4 natural verbal segmentation

Plan the wording and natural verbal segmentation BEFORE choosing delivery
controls. Prefer short but complete segments, each expressing one natural
teaching meaning unit that can be read aloud on its own in context. Avoid packing
multiple independent propositions that need separate spoken boundaries into one
segment. Explanation and evidence may span several natural short sentences;
keep their logical connections and the original content boundary intact.
Do not fragment speech into individual words or very short, incomplete phrases.
Do not add SSML, pause tokens, or renderer-specific markup. Segment text must
remain natural, directly speakable text. Segmentation expresses meaning units;
it does not prescribe timed pauses or guarantee acoustic timing.

# v0.4 expressive sparse local delivery

For `corrective_feedback`, inspect the actual verbal plan for teaching phases:
acknowledgement/validation, correction/explanation, key evidence, and conclusion.
Choose sparse but meaningful local control by pedagogical function and learner
need, never by segment index or specific keywords. Do not invent teaching phases
or split text merely to create more control slots.

When acknowledgement/validation and a distinct key correction/conclusion are
present AND both need a vocal distinction to support the learner-state change,
include at least two meaningful local controls on the relevant distinct segments:
one to support acknowledgement and one to make the key repair clear. In this
case, softening acknowledgement alone is insufficient. This is conditional on
two justified pedagogical needs, not an unconditional numeric quota. If only
one phase needs control, use one; if wording alone suffices, `delivery_plan: {}`
remains valid. Do not mechanically fill the delivery plan to reach a count.

Use the existing finite enums in `segment_overrides[].prosody` for these signals:
- acknowledgement/validation MAY use `volume: "soft"`, without also changing pitch;
- ordinary explanation/transition normally stays neutral, with no override;
- select one key correction, decisive evidence, or conclusion for mild emphasis
  using `pitch_level: "high"` when pedagogically justified;
- do not combine `pitch_level: "high"` with `volume: "loud"` by default; prefer
  one control dimension per selected segment, not stacked emphasis.

Do not require an override for every segment. Leave segments without a justified
vocal distinction uncontrolled; do not add explicit neutral overrides or a global
control merely to establish a trajectory. Do not amplify the same correction at
every evidence and conclusion segment. Other intents retain minimum justified
control and may keep an empty delivery plan.

Do not use free-form `attitudinal_tone` or `emotion` as acoustic control signals.
Do not add numeric acoustics, renderer-specific fields, or word-level prominence
to implement this policy. Use the finite segment-level prosody choices above;
do not substitute `prominence_targets` for them.

Before output, check whether both justified teaching functions received their
minimal local control, and remove controls without a separate pedagogical need.
Verify references against the finalized verbal segments and the existing enum
contract. Delivery planning must not rewrite the finalized text or its order.
Output only the JSON object required by the existing contract.
"""


def build_speech_plan_prompt(input_doc: dict) -> SpeechPlanPrompt:
    base = _build_v02(input_doc)
    return SpeechPlanPrompt(
        system=base.system + "\n\n" + _V04_GUIDANCE.strip(), user=base.user
    )


__all__ = ["PROMPT_VERSION", "SpeechPlanPrompt", "build_speech_plan_prompt"]
