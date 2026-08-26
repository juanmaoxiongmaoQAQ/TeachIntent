"""Versioned generator prompts for TeachIntent.

Currently exposes the Speech Plan Generator Prompt (``speech_plan.py``, v0.1).
"""

from .speech_plan import PROMPT_VERSION, SpeechPlanPrompt, build_speech_plan_prompt

__all__ = ["PROMPT_VERSION", "SpeechPlanPrompt", "build_speech_plan_prompt"]
