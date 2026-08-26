"""Parse the Hy3 raw response text into a Python dict.

Parsing is strictly separated from validation: this module does NOT check the
speech plan against any schema or semantic rule - it only turns text into a dict.
It also never silently fixes field names, enum values, text content, or prosody
controls. The only tolerated deviation from strict JSON is stripping a single
Markdown code fence that wraps the whole response (a common, benign model habit);
anything beyond that is a hard parse failure so Hy3's true instruction-following
signal is preserved, not masked.
"""

from __future__ import annotations

import json
import re

from .errors import ResponseParsingError

__all__ = ["parse_speech_plan_json"]

# A single Markdown fence wrapping the entire (trimmed) response:
#   ```json\n{...}\n```   /   ```\n{...}\n```   /   ```JSON\n{...}\n```
_FENCE_RE = re.compile(
    r"^```[A-Za-z0-9_-]*[ \t]*\n(?P<body>.*?)\n?```[ \t]*$",
    re.DOTALL,
)

_HEAD_SNIPPET_LEN = 200


def parse_speech_plan_json(raw: str) -> dict:
    """Parse *raw* Hy3 response text into a dict.

    Algorithm:
    1. Strip; empty -> :class:`ResponseParsingError`.
    2. Try ``json.loads`` directly (pure JSON preferred, unmutated).
    3. Documented tolerance: if the whole trimmed text is a single Markdown fence,
       strip the fence and retry ``json.loads`` on the body.
    4. Otherwise -> :class:`ResponseParsingError`.

    A successfully parsed non-dict JSON value (list/string/number/bool/null) is a
    parse failure ("parsed JSON is not an object"), not returned.

    Raises:
        ResponseParsingError: always carrying ``raw_text``.
    """
    text = raw.strip()
    if not text:
        raise ResponseParsingError("Hy3 response is empty", raw_text=raw)

    result, error = _try_loads(text)
    if result is not _NOT_PARSED:
        return _coerce_to_dict(result, raw, error)

    fence_match = _FENCE_RE.match(text)
    if fence_match is not None:
        body = fence_match.group("body")
        result, error = _try_loads(body)
        if result is not _NOT_PARSED:
            return _coerce_to_dict(result, raw, error)

    snippet = repr(raw[:_HEAD_SNIPPET_LEN])
    detail = f" ({error})" if error else ""
    raise ResponseParsingError(
        f"Hy3 response is not valid JSON{detail}; head: {snippet}",
        raw_text=raw,
    )


# Sentinel meaning "json.loads failed to produce any value".
_NOT_PARSED = object()


def _try_loads(text: str) -> tuple[object, str | None]:
    """Return (parsed_value, None) on success or (_NOT_PARSED, error_msg) on failure."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return _NOT_PARSED, exc.msg


def _coerce_to_dict(value: object, raw: str, error: str | None) -> dict:
    if isinstance(value, dict):
        return value
    raise ResponseParsingError(
        "Hy3 response parsed as JSON but is not an object",
        raw_text=raw,
    )
