"""Shared platform credentials for OWeb (not per-customer)."""

from __future__ import annotations

import os
from typing import Any


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_platform_credentials() -> dict[str, dict[str, Any]]:
    """Load OWeb-wide Google/Meta credentials from environment variables."""
    google: dict[str, Any] = {}
    meta: dict[str, Any] = {}

    if token := _env("GOOGLE_ADS_DEVELOPER_TOKEN"):
        google["developer_token"] = token
    if client_id := _env("GOOGLE_ADS_CLIENT_ID"):
        google["client_id"] = client_id
    if client_secret := _env("GOOGLE_ADS_CLIENT_SECRET"):
        google["client_secret"] = client_secret
    if app_id := _env("META_ADS_APP_ID"):
        meta["app_id"] = app_id
    if app_secret := _env("META_ADS_APP_SECRET"):
        meta["app_secret"] = app_secret

    result: dict[str, dict[str, Any]] = {}
    if google:
        result["google_ads"] = google
    if meta:
        result["meta_ads"] = meta
    return result
