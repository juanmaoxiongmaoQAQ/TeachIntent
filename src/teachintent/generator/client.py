"""Hy3 API client (OpenAI-compatible Chat Completions over OpenRouter).

Everything provider-specific lives here so it can be swapped without touching the
service layer. The confirmed v0.1 baseline is OpenRouter
(``HY3_BASE_URL=https://openrouter.ai/api/v1``) with Bearer-token auth; the client
joins ``{base_url.rstrip('/')}/chat/completions``.

Model metadata is split for reproducibility:
* :attr:`Hy3Client.model` / :attr:`Hy3Completer.model` is the REQUESTED model
  (``HY3_MODEL`` - what we asked for);
* :attr:`Hy3Completion.reported_model` is the model the API returned (may be
  ``None`` if the gateway does not echo it).

The API key is NEVER logged, never stored on exceptions, and never interpolated
into any message. ``response_format`` is accepted as an opt-in constructor param
but is NOT sent by default - v0.1 deliberately observes Hy3's raw
instruction-following without schema-constrained generation, even when OpenRouter
supports structured outputs for the chosen model.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

from .errors import Hy3APIError, Hy3ConfigError

__all__ = ["Hy3Completion", "Hy3Completer", "Hy3Client"]


@dataclass(frozen=True)
class Hy3Completion:
    """A single Hy3 chat completion result."""

    content: str
    finish_reason: str | None
    reported_model: str | None  # model name AS RETURNED BY THE API (may be None)


@runtime_checkable
class Hy3Completer(Protocol):
    """Structural typing seam for tests and future providers.

    ``model`` is the REQUESTED model (read-only); the REPORTED model is carried
    per-completion on :class:`Hy3Completion`.
    """

    @property
    def model(self) -> str: ...

    def complete(
        self, system: str, user: str, *, temperature: float = ...
    ) -> Hy3Completion: ...


class Hy3Client:
    """OpenAI-compatible Chat Completions client for Hy3 (OpenRouter baseline)."""

    DEFAULT_TIMEOUT_SECONDS: float = 120.0
    _REQUIRED_ENV = ("HY3_API_KEY", "HY3_BASE_URL", "HY3_MODEL")

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        response_format: dict[str, Any] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._response_format = response_format
        self._transport = transport

    @property
    def model(self) -> str:
        """The REQUESTED model (``HY3_MODEL``). Read-only; for reproducibility metadata."""
        return self._model

    @property
    def endpoint(self) -> str:
        """The full chat-completions endpoint URL (for logging; never includes the key)."""
        return f"{self._base_url}/chat/completions"

    @classmethod
    def from_env(cls, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> "Hy3Client":
        """Build a client from ``HY3_API_KEY`` / ``HY3_BASE_URL`` / ``HY3_MODEL``.

        Reads ``os.environ`` only (no .env loading here - the entry point owns
        that). Raises :class:`Hy3ConfigError` naming the missing variable(s);
        NEVER echoes any value.
        """
        missing = [
            name
            for name in cls._REQUIRED_ENV
            if not os.environ.get(name, "").strip()
        ]
        if missing:
            joined = ", ".join(missing)
            raise Hy3ConfigError(
                f"Required Hy3 environment variable(s) not set or empty: {joined}. "
                "Copy .env.example to .env and fill in the values."
            )
        return cls(
            api_key=os.environ["HY3_API_KEY"],
            base_url=os.environ["HY3_BASE_URL"],
            model=os.environ["HY3_MODEL"],
            timeout=timeout,
        )

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0
    ) -> Hy3Completion:
        """Call Hy3 and return the completion. Always sends ``temperature`` explicitly."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if self._response_format is not None:
            payload["response_format"] = self._response_format

        headers = {
            "Authorization": f"Bearer {self._api_key}",
        }

        try:
            with httpx.Client(
                timeout=self._timeout, transport=self._transport
            ) as http:
                response = http.post(self.endpoint, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise Hy3APIError(
                f"Hy3 API request failed: {type(exc).__name__}: {exc}"
            ) from exc

        response_text = response.text
        if response.status_code >= 400:
            snippet = response_text[:500]
            raise Hy3APIError(
                f"Hy3 API returned HTTP {response.status_code}; body snippet: {snippet}",
                status_code=response.status_code,
                response_text=response_text,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise Hy3APIError(
                f"Hy3 API returned a non-JSON response body: {exc}",
                status_code=response.status_code,
                response_text=response_text,
            ) from exc

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise Hy3APIError(
                "Hy3 API response has no non-empty 'choices' array",
                status_code=response.status_code,
                response_text=response_text,
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise Hy3APIError(
                "Hy3 API response choices[0] is not an object",
                status_code=response.status_code,
                response_text=response_text,
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise Hy3APIError(
                "Hy3 API response choices[0].message is not an object",
                status_code=response.status_code,
                response_text=response_text,
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            finish_reason = first.get("finish_reason")
            hint = (
                f" (finish_reason={finish_reason!r})"
                if finish_reason is not None
                else ""
            )
            raise Hy3APIError(
                f"Hy3 API response choices[0].message.content is missing or empty{hint}",
                status_code=response.status_code,
                response_text=response_text,
            )

        return Hy3Completion(
            content=content,
            finish_reason=first.get("finish_reason"),
            reported_model=data.get("model"),
        )
