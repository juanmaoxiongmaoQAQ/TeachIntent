"""TeachIntent: pedagogical intent driven speech planning.

This package implements the executable contract layer (JSON Schemas + strict
Pydantic models + cross-field semantic validators) plus the Hy3 speech plan
generator v0.1 (versioned prompts, Hy3 client, response parser, generation
service). Renderer adapters, TTS, and the evaluator remain out of scope.
"""

from teachintent.models import SpeechPlan, TeachIntentInput

__version__ = "0.1.0"

__all__ = ["TeachIntentInput", "SpeechPlan", "__version__"]
