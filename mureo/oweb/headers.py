"""Merge platform + per-customer credentials into OWeb MCP headers."""

from __future__ import annotations

from typing import Any

from mureo.auth_oweb import (
    HEADER_GOOGLE_CLIENT_ID,
    HEADER_GOOGLE_CLIENT_SECRET,
    HEADER_GOOGLE_CUSTOMER_ID,
    HEADER_GOOGLE_DEVELOPER_TOKEN,
    HEADER_GOOGLE_LOGIN_CUSTOMER_ID,
    HEADER_GOOGLE_REFRESH_TOKEN,
    HEADER_META_ACCESS_TOKEN,
    HEADER_META_ACCOUNT_ID,
    HEADER_META_APP_ID,
    HEADER_META_APP_SECRET,
)
from mureo.oweb.credential_store import CustomerCredentials

_CUSTOMER_GOOGLE_KEYS = frozenset(
    {"refresh_token", "customer_id", "login_customer_id"}
)
_CUSTOMER_META_KEYS = frozenset({"access_token", "account_id"})


def _pick(section: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    return {key: section[key] for key in allowed if key in section}


def _set(headers: dict[str, str], name: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text:
        headers[name] = text


def merge_credentials_to_headers(
    platform: dict[str, dict[str, Any]],
    customer: CustomerCredentials,
) -> dict[str, str]:
    """Combine shared platform env with per-customer secrets."""
    google = {
        **platform.get("google_ads", {}),
        **_pick(customer.google_ads, _CUSTOMER_GOOGLE_KEYS),
    }
    meta = {
        **platform.get("meta_ads", {}),
        **_pick(customer.meta_ads, _CUSTOMER_META_KEYS),
    }

    headers: dict[str, str] = {}
    _set(headers, HEADER_GOOGLE_DEVELOPER_TOKEN, google.get("developer_token"))
    _set(headers, HEADER_GOOGLE_CLIENT_ID, google.get("client_id"))
    _set(headers, HEADER_GOOGLE_CLIENT_SECRET, google.get("client_secret"))
    _set(headers, HEADER_GOOGLE_REFRESH_TOKEN, google.get("refresh_token"))
    _set(headers, HEADER_GOOGLE_LOGIN_CUSTOMER_ID, google.get("login_customer_id"))
    _set(headers, HEADER_GOOGLE_CUSTOMER_ID, google.get("customer_id"))
    _set(headers, HEADER_META_ACCESS_TOKEN, meta.get("access_token"))
    _set(headers, HEADER_META_APP_ID, meta.get("app_id"))
    _set(headers, HEADER_META_APP_SECRET, meta.get("app_secret"))
    _set(headers, HEADER_META_ACCOUNT_ID, meta.get("account_id"))
    return headers
