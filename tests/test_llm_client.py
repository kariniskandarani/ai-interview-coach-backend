from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from src.llm_client import LLMError, _get_client, generate_structured


class _Greeting(BaseModel):
    message: str


class _FakeCompletions:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)

    def create(self, **kwargs):
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeChat:
    def __init__(self, side_effects):
        self.completions = _FakeCompletions(side_effects)


class _FakeClient:
    def __init__(self, side_effects):
        self.chat = _FakeChat(side_effects)


def _success_response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _rate_limit_error():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(status_code=429, request=request)
    return openai.RateLimitError("Rate limited", response=response, body=None)


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LLMError):
        _get_client()


def test_generate_structured_retries_on_rate_limit_then_succeeds(monkeypatch):
    success = _success_response('{"message": "hi"}')
    fake_client = _FakeClient([_rate_limit_error(), _rate_limit_error(), success])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)
    monkeypatch.setattr("src.llm_client.time.sleep", lambda seconds: None)

    result = generate_structured("prompt", _Greeting)

    assert result == _Greeting(message="hi")


def test_generate_structured_raises_after_max_retries_on_rate_limit(monkeypatch):
    fake_client = _FakeClient([_rate_limit_error() for _ in range(10)])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)
    monkeypatch.setattr("src.llm_client.time.sleep", lambda seconds: None)

    with pytest.raises(LLMError):
        generate_structured("prompt", _Greeting)


def test_generate_structured_does_not_retry_non_rate_limit_errors(monkeypatch):
    other_error = ValueError("something else broke")
    fake_client = _FakeClient([other_error, _success_response('{"message": "hi"}')])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)

    with pytest.raises(LLMError):
        generate_structured("prompt", _Greeting)


def test_generate_structured_raises_on_empty_content(monkeypatch):
    fake_client = _FakeClient([_success_response(None)])
    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)

    with pytest.raises(LLMError, match="empty"):
        generate_structured("prompt", _Greeting)


def test_generate_structured_raises_on_schema_mismatch(monkeypatch):
    fake_client = _FakeClient([_success_response('{"not_a_valid_field": 123}')])
    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)

    with pytest.raises(LLMError, match="schema"):
        generate_structured("prompt", _Greeting)
