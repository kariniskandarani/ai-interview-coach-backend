import pytest

from src.llm_client import LLMError, _get_client


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        _get_client()
