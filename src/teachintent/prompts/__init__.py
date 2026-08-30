"""Versioned generator prompts for TeachIntent.

Exposes:
* the Speech Plan Generator Prompt **v0.1** (``speech_plan.py``) — the original,
  unchanged default;
* the Speech Plan Generator Prompt **v0.2-rc.1** (``speech_plan_v0_2_rc1.py``) —
  a narrow prompt-level behavioral revision;
* an explicit version-selection registry (``registry.py``) that keeps v0.1 as the
  default and lets a run opt into v0.2-rc.1.

``PROMPT_VERSION`` here is still ``"v0.1"`` so the package-level default is
unchanged. Selecting v0.2-rc.1 is explicit.
"""

from .registry import (
    DEFAULT_PROMPT_VERSION,
    PROMPT_VERSION_V0_1,
    PROMPT_VERSION_V0_2_RC1,
    UnknownPromptVersionError,
    build_speech_plan_prompt_for_version,
    get_speech_plan_prompt_version,
    list_speech_plan_prompt_versions,
)
from .speech_plan import PROMPT_VERSION, SpeechPlanPrompt, build_speech_plan_prompt
from .speech_plan_v0_2_rc1 import (
    build_speech_plan_prompt as build_speech_plan_prompt_v0_2_rc1,
)

__all__ = [
    # v0.1 (unchanged default)
    "PROMPT_VERSION",
    "SpeechPlanPrompt",
    "build_speech_plan_prompt",
    # v0.2-rc.1
    "build_speech_plan_prompt_v0_2_rc1",
    "PROMPT_VERSION_V0_2_RC1",
    # registry / selection
    "DEFAULT_PROMPT_VERSION",
    "PROMPT_VERSION_V0_1",
    "UnknownPromptVersionError",
    "build_speech_plan_prompt_for_version",
    "get_speech_plan_prompt_version",
    "list_speech_plan_prompt_versions",
]
