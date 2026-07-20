from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from src.llm_client import LLMError, _get_client, generate_structured


class _Greeting(BaseModel):
    message: str


class _FakeModels:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)

    def generate_content(self, **kwargs):
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeClient:
    def __init__(self, side_effects):
        self.models = _FakeModels(side_effects)


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        _get_client()


def test_generate_structured_retries_on_rate_limit_then_succeeds(monkeypatch):
    rate_limit_error = Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}")
    success = SimpleNamespace(parsed=_Greeting(message="hi"))
    fake_client = _FakeClient([rate_limit_error, rate_limit_error, success])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)
    monkeypatch.setattr("src.llm_client.time.sleep", lambda seconds: None)

    result = generate_structured("prompt", _Greeting)

    assert result == success.parsed


def test_generate_structured_raises_after_max_retries_on_rate_limit(monkeypatch):
    rate_limit_error = Exception("429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}")
    fake_client = _FakeClient([rate_limit_error] * 10)

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)
    monkeypatch.setattr("src.llm_client.time.sleep", lambda seconds: None)

    with pytest.raises(LLMError):
        generate_structured("prompt", _Greeting)


def test_generate_structured_does_not_retry_non_rate_limit_errors(monkeypatch):
    other_error = Exception("404 NOT_FOUND. {'error': {'code': 404}}")
    fake_client = _FakeClient([other_error, SimpleNamespace(parsed=_Greeting(message="hi"))])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)

    with pytest.raises(LLMError):
        generate_structured("prompt", _Greeting)


def test_generate_structured_fails_fast_on_daily_quota_without_retrying(monkeypatch):
    daily_quota_error = Exception(
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
        "\"You exceeded your current quota...\", 'status': 'RESOURCE_EXHAUSTED', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', "
        "'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
        "'quotaValue': '20'}]}]}}"
    )
    fake_client = _FakeClient([daily_quota_error])

    monkeypatch.setattr("src.llm_client._get_client", lambda: fake_client)

    def _fail_if_slept(seconds):
        raise AssertionError("should not retry/sleep on daily quota exhaustion")

    monkeypatch.setattr("src.llm_client.time.sleep", _fail_if_slept)

    with pytest.raises(LLMError, match="daily quota"):
        generate_structured("prompt", _Greeting)
