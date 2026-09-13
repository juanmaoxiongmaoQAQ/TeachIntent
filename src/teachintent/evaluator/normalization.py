"""Explicit compatibility aliases for Judge output, before strict validation.

The raw response and parser remain unchanged. No score, evidence, or unknown
field repair is performed.
"""

from copy import deepcopy
from typing import Any

from .errors import JudgeOutputSchemaError


SCORE_KEY_ALIASES = {
    "delivery_necessity_and_sparsity": "delivery_necessity_sparsity",
}


def normalize_judge_output(value: Any, *, raw_text: str | None = None) -> Any:
    """Copy and rename only registered score aliases; reject collisions."""
    normalized = deepcopy(value)
    if not isinstance(normalized, dict) or not isinstance(normalized.get("scores"), dict):
        return normalized
    scores = normalized["scores"]
    for alias, canonical in SCORE_KEY_ALIASES.items():
        if alias not in scores:
            continue
        if canonical in scores:
            raise JudgeOutputSchemaError(
                f"scores contains both canonical key {canonical!r} and alias {alias!r}",
                raw_text=raw_text,
            )
        scores[canonical] = scores.pop(alias)
    return normalized
