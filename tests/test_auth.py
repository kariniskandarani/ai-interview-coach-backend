from types import SimpleNamespace

import pytest

from src.auth import AuthError, get_user_id_from_token


class _FakeAuth:
    def __init__(self, user_id=None, raise_exc=None):
        self._user_id = user_id
        self._raise_exc = raise_exc

    def get_user(self, token):
        if self._raise_exc:
            raise self._raise_exc
        if self._user_id is None:
            return SimpleNamespace(user=None)
        return SimpleNamespace(user=SimpleNamespace(id=self._user_id))


class _FakeClient:
    def __init__(self, user_id=None, raise_exc=None):
        self.auth = _FakeAuth(user_id=user_id, raise_exc=raise_exc)


def test_returns_none_without_authorization_header():
    assert get_user_id_from_token(None) is None


def test_raises_on_malformed_header():
    with pytest.raises(AuthError):
        get_user_id_from_token("not-a-bearer-token")


def test_returns_user_id_for_valid_token(monkeypatch):
    monkeypatch.setattr(
        "src.auth._get_auth_client", lambda: _FakeClient(user_id="user-abc-123")
    )
    assert get_user_id_from_token("Bearer real-token") == "user-abc-123"


def test_raises_when_supabase_rejects_the_token(monkeypatch):
    monkeypatch.setattr(
        "src.auth._get_auth_client",
        lambda: _FakeClient(raise_exc=Exception("token expired")),
    )
    with pytest.raises(AuthError):
        get_user_id_from_token("Bearer expired-token")


def test_raises_when_response_has_no_user(monkeypatch):
    monkeypatch.setattr("src.auth._get_auth_client", lambda: _FakeClient(user_id=None))
    with pytest.raises(AuthError):
        get_user_id_from_token("Bearer weird-token")


def test_get_auth_client_raises_without_credentials(monkeypatch):
    from src.auth import _get_auth_client

    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    with pytest.raises(AuthError):
        _get_auth_client()
