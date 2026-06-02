import pytest
from fastapi import HTTPException

from alpha_edge.auth import require_admin_api_key
from alpha_edge.config import get_settings


def test_admin_auth_allows_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "")
    get_settings.cache_clear()

    assert require_admin_api_key() is None


def test_admin_auth_rejects_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "expected")
    get_settings.cache_clear()

    with pytest.raises(HTTPException):
        require_admin_api_key(x_admin_token="wrong")


def test_admin_auth_accepts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_API_KEY", "expected")
    get_settings.cache_clear()

    assert require_admin_api_key(x_admin_token="expected") is None
