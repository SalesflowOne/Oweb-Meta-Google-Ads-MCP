"""OWeb request-scoped credential loading from HTTP headers.

Hosted Streamable HTTP MCP (Vercel) must not read ``~/.mureo/credentials.json``.
Callers pass Google Ads and Meta Ads credentials on each request via
``X-Mureo-*`` headers; :func:`activate_request` installs a read-only
in-memory :class:`SecretStore` for the lifetime of the request.

See :doc:`OWEB` for the header contract and curl examples.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Any

from mureo.core.secret_store import SecretStore, SecretStoreError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

# ---------------------------------------------------------------------------
# Request scope — when active, mureo.auth loaders use headers only (no file/env)
# ---------------------------------------------------------------------------

_oweb_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "oweb_active",
    default=False,
)
_oweb_secret_store: contextvars.ContextVar[SecretStore | None] = contextvars.ContextVar(
    "oweb_secret_store",
    default=None,
)

# Header names (HTTP field names; clients may send any casing).
HEADER_GOOGLE_DEVELOPER_TOKEN = "X-Mureo-Google-Ads-Developer-Token"
HEADER_GOOGLE_CLIENT_ID = "X-Mureo-Google-Ads-Client-Id"
HEADER_GOOGLE_CLIENT_SECRET = "X-Mureo-Google-Ads-Client-Secret"
HEADER_GOOGLE_REFRESH_TOKEN = "X-Mureo-Google-Ads-Refresh-Token"
HEADER_GOOGLE_LOGIN_CUSTOMER_ID = "X-Mureo-Google-Ads-Login-Customer-Id"
HEADER_GOOGLE_CUSTOMER_ID = "X-Mureo-Google-Ads-Customer-Id"

HEADER_META_ACCESS_TOKEN = "X-Mureo-Meta-Ads-Access-Token"
HEADER_META_APP_ID = "X-Mureo-Meta-Ads-App-Id"
HEADER_META_APP_SECRET = "X-Mureo-Meta-Ads-App-Secret"
HEADER_META_ACCOUNT_ID = "X-Mureo-Meta-Ads-Account-Id"


def is_oweb_request() -> bool:
    """Return True while an OWeb per-request credential scope is active."""
    return _oweb_active.get()


def get_oweb_secret_store() -> SecretStore | None:
    """Return the active OWeb header store, or ``None`` outside OWeb scope."""
    return _oweb_secret_store.get()


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    """Return a stripped header value, matching ``name`` case-insensitively."""
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            stripped = value.strip()
            if not stripped:
                return None
            if any(char in stripped for char in "\r\n\x00"):
                return None
            return stripped
    return None


def credentials_from_headers(headers: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """Parse OWeb credential headers into a credentials.json-shaped dict."""
    google: dict[str, Any] = {}
    meta: dict[str, Any] = {}

    if token := _header_value(headers, HEADER_GOOGLE_DEVELOPER_TOKEN):
        google["developer_token"] = token
    if client_id := _header_value(headers, HEADER_GOOGLE_CLIENT_ID):
        google["client_id"] = client_id
    if client_secret := _header_value(headers, HEADER_GOOGLE_CLIENT_SECRET):
        google["client_secret"] = client_secret
    if refresh_token := _header_value(headers, HEADER_GOOGLE_REFRESH_TOKEN):
        google["refresh_token"] = refresh_token
    if login_customer_id := _header_value(headers, HEADER_GOOGLE_LOGIN_CUSTOMER_ID):
        google["login_customer_id"] = login_customer_id
    if customer_id := _header_value(headers, HEADER_GOOGLE_CUSTOMER_ID):
        google["customer_id"] = customer_id

    if access_token := _header_value(headers, HEADER_META_ACCESS_TOKEN):
        meta["access_token"] = access_token
    if app_id := _header_value(headers, HEADER_META_APP_ID):
        meta["app_id"] = app_id
    if app_secret := _header_value(headers, HEADER_META_APP_SECRET):
        meta["app_secret"] = app_secret
    if account_id := _header_value(headers, HEADER_META_ACCOUNT_ID):
        meta["account_id"] = account_id

    result: dict[str, dict[str, Any]] = {}
    if google:
        result["google_ads"] = google
    if meta:
        result["meta_ads"] = meta
    return result


class HeaderSecretStore:
    """Read-only :class:`SecretStore` backed by parsed request headers."""

    def __init__(self, sections: dict[str, dict[str, Any]]) -> None:
        self._sections = sections

    def load(self, key: str) -> dict[str, Any]:
        section = self._sections.get(key)
        return dict(section) if isinstance(section, dict) else {}

    def save(self, key: str, value: dict[str, Any]) -> None:
        raise SecretStoreError("OWeb header credentials are read-only")

    def delete(self, key: str) -> None:
        raise SecretStoreError("OWeb header credentials are read-only")


def build_secret_store(headers: Mapping[str, str]) -> HeaderSecretStore:
    """Build a :class:`HeaderSecretStore` from request headers."""
    return HeaderSecretStore(credentials_from_headers(headers))


@contextlib.asynccontextmanager
async def activate_request(headers: Mapping[str, str]) -> AsyncIterator[None]:
    """Install per-request OWeb credentials for the current async context."""
    store = build_secret_store(headers)
    active_token = _oweb_active.set(True)
    store_token = _oweb_secret_store.set(store)
    try:
        yield
    finally:
        _oweb_secret_store.reset(store_token)
        _oweb_active.reset(active_token)
