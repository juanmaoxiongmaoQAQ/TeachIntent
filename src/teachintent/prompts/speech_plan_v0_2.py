"""Formal Speech Plan Generator Prompt v0.2.

Formal v0.2 is the release identity for the exact model-facing treatment selected
as v0.2-rc.2.  This module deliberately delegates to the rc.2 builder instead of
copying or rewriting prompt text, so every generated system and user message is
byte-for-byte identical for every input document.

``PROMPT_VERSION`` is provenance metadata resolved by the prompt registry; it is
not injected into the model-facing messages.  ``PARENT_PROMPT_VERSION`` records
the development candidate from which formal v0.2 was frozen.
"""

from __future__ import annotations

from .speech_plan_v0_2_rc2 import (
    PROMPT_VERSION as PARENT_PROMPT_VERSION,
)
from .speech_plan_v0_2_rc2 import (
    SpeechPlanPrompt,
    build_speech_plan_prompt,
)

__all__ = [
    "PROMPT_VERSION",
    "PARENT_PROMPT_VERSION",
    "SpeechPlanPrompt",
    "build_speech_plan_prompt",
]

PROMPT_VERSION = "v0.2"

