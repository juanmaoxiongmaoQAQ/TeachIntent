"""Explicit version selection for the Speech Plan Generator Prompt.

v0.1 is preserved untouched in :mod:`teachintent.prompts.speech_plan`. v0.2-rc.1
lives in :mod:`teachintent.prompts.speech_plan_v0_2_rc1`, and v0.2-rc.2 (a minimal
correction of rc.1) lives in :mod:`teachintent.prompts.speech_plan_v0_2_rc2`. This
registry adds a minimal, explicit selection API on top of the existing prompts
package so that a generation run can request a specific prompt version without the
generator implementation needing to hard-code which one it imports.

The DEFAULT version is ``v0.1`` — call sites that do not opt into selection get
byte-identical behavior to the original ``build_speech_plan_prompt``. The generator
service (``teachintent.generator.service``) already selects through this registry
via ``generate_speech_plan(..., prompt_version=...)``; the v0.2-rc.1 development
runner opts into ``v0.2-rc.1`` explicitly. No prompt text lives here — this module
only routes to the existing prompt builders.
"""

from __future__ import annotations

from typing import Callable

from .speech_plan import PROMPT_VERSION as PROMPT_VERSION_V0_1
from .speech_plan import SpeechPlanPrompt, build_speech_plan_prompt as _build_v0_1
from .speech_plan_v0_2_rc1 import (
    PROMPT_VERSION as PROMPT_VERSION_V0_2_RC1,
)
from .speech_plan_v0_2_rc1 import (
    build_speech_plan_prompt as _build_v0_2_rc1,
)
from .speech_plan_v0_2_rc2 import (
    PROMPT_VERSION as PROMPT_VERSION_V0_2_RC2,
)
from .speech_plan_v0_2_rc2 import (
    build_speech_plan_prompt as _build_v0_2_rc2,
)

__all__ = [
    "PROMPT_VERSION_V0_1",
    "PROMPT_VERSION_V0_2_RC1",
    "PROMPT_VERSION_V0_2_RC2",
    "SpeechPlanPrompt",
    "UnknownPromptVersionError",
    "SPEECH_PLAN_PROMPTS",
    "DEFAULT_PROMPT_VERSION",
    "build_speech_plan_prompt_for_version",
    "get_speech_plan_prompt_version",
    "list_speech_plan_prompt_versions",
]

DEFAULT_PROMPT_VERSION = PROMPT_VERSION_V0_1  # "v0.1" — preserves original behavior


class UnknownPromptVersionError(ValueError):
    """Raised when a requested prompt version is not registered."""


# version string -> (PROMPT_VERSION constant, builder)
SPEECH_PLAN_PROMPTS: dict[str, tuple[str, Callable[[dict], SpeechPlanPrompt]]] = {
    PROMPT_VERSION_V0_1: (PROMPT_VERSION_V0_1, _build_v0_1),
    PROMPT_VERSION_V0_2_RC1: (PROMPT_VERSION_V0_2_RC1, _build_v0_2_rc1),
    PROMPT_VERSION_V0_2_RC2: (PROMPT_VERSION_V0_2_RC2, _build_v0_2_rc2),
}


def list_speech_plan_prompt_versions() -> list[str]:
    """Return the registered prompt version strings, sorted for stable output."""
    return sorted(SPEECH_PLAN_PROMPTS)


def get_speech_plan_prompt_version(version: str) -> str:
    """Return the canonical version string for *version* (validates existence)."""
    if version not in SPEECH_PLAN_PROMPTS:
        raise UnknownPromptVersionError(
            f"Unknown speech-plan prompt version {version!r}; "
            f"available: {list_speech_plan_prompt_versions()}"
        )
    return SPEECH_PLAN_PROMPTS[version][0]


def build_speech_plan_prompt_for_version(
    input_doc: dict, version: str = DEFAULT_PROMPT_VERSION
) -> SpeechPlanPrompt:
    """Build the Speech Plan Generator prompt for an explicit *version*.

    Defaults to ``v0.1`` so existing call sites that do not opt into selection get
    byte-identical behavior to the original ``build_speech_plan_prompt``.
    """
    if version not in SPEECH_PLAN_PROMPTS:
        raise UnknownPromptVersionError(
            f"Unknown speech-plan prompt version {version!r}; "
            f"available: {list_speech_plan_prompt_versions()}"
        )
    return SPEECH_PLAN_PROMPTS[version][1](input_doc)
