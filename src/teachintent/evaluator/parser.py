"""Judge response parser (separate from the Generator response parser).

The judge parser handles the LLM judge's output, which is structurally
different from the Generator's speech-plan output. It is deliberately a
separate module from ``teachintent.generator.parser`` -- the two parsers
follow the same tolerance principle (pure JSON preferred; single Markdown
fence tolerated) but serve different contracts and must not share state.

Parsing is strict: no field repair, enum repair, score repair, evidence
repair, or self-repair is performed (Section 22). A successfully parsed
non-dict JSON value is a parse failure.
"""

from __future__ import annotations

import json
import re

from .errors import JudgeResponseParseError

__all__ = ["parse_judge_response"]

# A single Markdown fence wrapping the entire (trimmed) response:
#   ```json\n{...}\n```   /   ```\n{...}\n```   /   ```JSON\n{...}\n```
_FENCE_RE = re.compile(
    r"^```[A-Za-z0-9_-]*[ \t]*\n(?P<body>.*?)\n?```[ \t]*$",
    re.DOTALL,
)

_HEAD_SNIPPET_LEN = 200

_NOT_PARSED = object()


def parse_judge_response(raw: str) -> dict:
    """Parse *raw* judge response text into a dict.

    Algorithm (Section 22.2, text-output mode):
    1. trim surrounding whitespace;
    2. reject empty output;
    3. attempt ``json.loads`` directly;
    4. if direct parsing fails, accept exactly one Markdown code fence wrapping
       the entire response, strip that fence, and retry;
    5. reject all other formats;
    6. require the parsed result to be a JSON object;
    7. perform no field repair, enum repair, score repair, evidence repair, or
       self-repair.

    Raises:
        JudgeResponseParseError: always carrying ``raw_text``.
    """
    text = raw.strip()
    if not text:
        raise JudgeResponseParseError(
            "judge response is empty", raw_text=raw
        )

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
    raise JudgeResponseParseError(
        f"judge response is not valid JSON{detail}; head: {snippet}",
        raw_text=raw,
    )


def _try_loads(text: str) -> tuple[object, str | None]:
    """Return (parsed_value, None) on success or (_NOT_PARSED, error_msg)."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return _NOT_PARSED, exc.msg


def _coerce_to_dict(value: object, raw: str, error: str | None) -> dict:
    if isinstance(value, dict):
        return value
    raise JudgeResponseParseError(
        "judge response parsed as JSON but is not an object",
        raw_text=raw,
    )
