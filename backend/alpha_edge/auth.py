from __future__ import annotations

from fastapi import Header, HTTPException, status

from alpha_edge.config import get_settings


def require_admin_api_key(x_admin_token: str | None = Header(default=None)) -> None:
    """Guard admin endpoints when an admin API key is configured.

    If `ADMIN_API_KEY` is unset, local/dev environments remain open so the app
    keeps working without extra configuration.
    """
    expected = get_settings().admin_api_key
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
        )
