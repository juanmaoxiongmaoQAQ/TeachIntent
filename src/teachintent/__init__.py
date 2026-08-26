"""TeachIntent: pedagogical intent driven speech planning — contract layer.

This package currently implements the executable contract layer only
(JSON Schemas + strict Pydantic models + cross-field semantic validators).
Generator prompts, Hy3 API integration, renderer adapters, TTS and the
evaluator are deliberately out of scope for this phase.
"""

from teachintent.models import SpeechPlan, TeachIntentInput

__version__ = "0.1.0"

__all__ = ["TeachIntentInput", "SpeechPlan", "__version__"]
