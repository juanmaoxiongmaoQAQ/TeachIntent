"""Speech Plan Generator Prompt v0.3.

This opt-in prompt keeps the v0.2 schema and sparse-control policy, while making
local delivery decisions more reliable when a corrective move has distinct
teaching phases. v0.2 remains untouched and remains the application default.
"""

from __future__ import annotations

import json
from typing import NamedTuple

from .speech_plan_v0_2_rc2 import _USER_TEMPLATE
from .speech_plan_v0_2_rc2 import _SYSTEM as _V02_SYSTEM

PROMPT_VERSION = "v0.3"

_V03_GUIDANCE = """
# v0.3 local delivery guidance

When `pedagogical_intent.primary` is `corrective_feedback`, inspect the verbal
segments for distinct teaching phases such as acknowledgement/validation,
correction or explanation, key evidence, and conclusion. If vocal delivery
materially supports the learner-state change, include the smallest justified
segment-level control for at least one relevant phase. This is a conditional
requirement, not a request to control every segment.

Use only the existing finite categorical fields in `segment_overrides[].prosody`:
- acknowledgement/validation MAY use `volume: "soft"`;
- ordinary explanation/transition MAY remain without an override;
- a key correction or conclusion MAY use `pitch_level: "high"`;
- do not add `loud` and `high` together by default; combine dimensions only when
  one named pedagogical need clearly requires both.

Do not invent role, discourse, intensity, numeric acoustic, or renderer-specific
fields. Do not use free-form `attitudinal_tone` or `emotion` as a proxy for a
Baton control. Use `prominence_targets` sparingly and only for a valid exact
substring; never add one merely because a word is important. Other intents may
and should keep `delivery_plan: {}` when wording is sufficient. A segment that
does not need a vocal distinction must have no override.

Before output, verify that every override references an existing segment, that
all enum values match the field contract, and that the verbal text and segment
order are unchanged. Output only the JSON object required by the existing
contract.
"""

_SYSTEM = _V02_SYSTEM + "\n\n" + _V03_GUIDANCE.strip()


class SpeechPlanPrompt(NamedTuple):
    system: str
    user: str


def build_speech_plan_prompt(input_doc: dict) -> SpeechPlanPrompt:
    case_json = json.dumps(input_doc, ensure_ascii=False, indent=2)
    user = _USER_TEMPLATE.format(
        output_language=input_doc["output_language"], case_json=case_json
    )
    return SpeechPlanPrompt(system=_SYSTEM, user=user)


__all__ = ["PROMPT_VERSION", "SpeechPlanPrompt", "build_speech_plan_prompt"]
