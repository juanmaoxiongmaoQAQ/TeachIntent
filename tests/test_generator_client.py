"""Tests for the Hy3 client (network-free via httpx.MockTransport).

Covers env loading, request construction (temperature always sent, no
response_format by default, Bearer auth, endpoint joining), error mapping, and
the requested-vs-reported model distinction. The API key is asserted absent
from all error messages.
"""

from __future__ import annotations

import json

import httpx
import pytest

from teachintent.generator.client import Hy3Client, Hy3Completion
from teachintent.generator.errors import Hy3APIError, Hy3ConfigError

API_KEY = "test-api-key"
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "hy3-test-model"


def _ok_response(
    *, content: str = '{"schema_version": "1.0.0-rc.3"}',
    finish_reason: str = "stop",
    reported_model: str | None = "hy3-test-model-reported",
) -> bytes:
    body = {
        "id": "resp_1",
        "model": reported_model,
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    return json.dumps(body).encode("utf-8")


def make_client(handler, **kwargs) -> Hy3Client:
    transport = httpx.MockTransport(handler)
    return Hy3Client(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        transport=transport,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["HY3_API_KEY", "HY3_BASE_URL", "HY3_MODEL"])
def test_from_env_missing_var_raises_config_error(monkeypatch, missing) -> None:
    for name in ("HY3_API_KEY", "HY3_BASE_URL", "HY3_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HY3_API_KEY", API_KEY)
    monkeypatch.setenv("HY3_BASE_URL", BASE_URL)
    monkeypatch.setenv("HY3_MODEL", MODEL)
    monkeypatch.delenv(missing, raising=False)
    with pytest.raises(Hy3ConfigError) as exc:
        Hy3Client.from_env()
    assert missing in str(exc.value)
    # The message must never echo any value.
    assert API_KEY not in str(exc.value)
    assert BASE_URL not in str(exc.value)


def test_from_env_empty_var_raises_config_error(monkeypatch) -> None:
    monkeypatch.setenv("HY3_API_KEY", "   ")
    monkeypatch.setenv("HY3_BASE_URL", BASE_URL)
    monkeypatch.setenv("HY3_MODEL", MODEL)
    with pytest.raises(Hy3ConfigError) as exc:
        Hy3Client.from_env()
    assert "HY3_API_KEY" in str(exc.value)


def test_from_env_happy_path(monkeypatch) -> None:
    monkeypatch.setenv("HY3_API_KEY", API_KEY)
    monkeypatch.setenv("HY3_BASE_URL", "https://openrouter.ai/api/v1/")
    monkeypatch.setenv("HY3_MODEL", MODEL)
    client = Hy3Client.from_env()
    assert client.model == MODEL  # requested model
    assert client.endpoint == "https://openrouter.ai/api/v1/chat/completions"


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------


def test_request_construction_default_no_response_format() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_ok_response())

    client = make_client(handler)
    completion = client.complete("sys", "usr")

    request = captured[0]
    assert request.url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.read())
    assert body["model"] == MODEL
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert body["temperature"] == 0.0
    assert "response_format" not in body  # v0.1: not sent by default
    assert isinstance(completion, Hy3Completion)
    assert completion.content == '{"schema_version": "1.0.0-rc.3"}'
    assert completion.finish_reason == "stop"
    assert completion.reported_model == "hy3-test-model-reported"


def test_request_construction_response_format_opt_in() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_ok_response())

    client = make_client(
        handler, response_format={"type": "json_object"}
    )
    client.complete("sys", "usr")
    body = json.loads(captured[0].read())
    assert body["response_format"] == {"type": "json_object"}


def test_temperature_is_sent_explicitly() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=_ok_response())

    client = make_client(handler)
    client.complete("sys", "usr", temperature=0.0)
    assert json.loads(captured[0].read())["temperature"] == 0.0


def test_trailing_slash_base_url_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://host.example/v1/chat/completions"
        return httpx.Response(200, content=_ok_response())

    client = Hy3Client(
        api_key=API_KEY,
        base_url="https://host.example/v1/",
        model=MODEL,
        transport=httpx.MockTransport(handler),
    )
    client.complete("sys", "usr")


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 500, 503])
def test_non_2xx_raises_hy3_api_error(status) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=b'{"error":"nope"}')

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert exc.value.status_code == status
    assert exc.value.response_text == '{"error":"nope"}'
    assert str(status) in str(exc.value)
    assert API_KEY not in str(exc.value)


def test_network_error_raises_hy3_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert exc.value.status_code is None
    assert "ConnectError" in str(exc.value)
    assert API_KEY not in str(exc.value)


def test_timeout_raises_hy3_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out")

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert "ReadTimeout" in str(exc.value)


def test_non_json_body_raises_hy3_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert "non-JSON" in str(exc.value)


def test_empty_choices_raises_hy3_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"choices": []}')

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert "choices" in str(exc.value)


def test_missing_content_raises_hy3_api_error_with_finish_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {"finish_reason": "length", "message": {"role": "assistant"}}
            ]
        }
        return httpx.Response(200, content=json.dumps(body).encode())

    client = make_client(handler)
    with pytest.raises(Hy3APIError) as exc:
        client.complete("sys", "usr")
    assert "content" in str(exc.value)
    assert "length" in str(exc.value)  # truncation diagnosis surfaced


def test_reported_model_can_be_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_ok_response(reported_model=None))

    client = make_client(handler)
    completion = client.complete("sys", "usr")
    assert completion.reported_model is None
    assert client.model == MODEL  # requested model is still known
