"""Per-customer credential stores for the OWeb MCP proxy."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

_CUSTOMER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def validate_customer_id(customer_id: str) -> str:
    """Reject path metacharacters and other unsafe customer id values."""
    if not _CUSTOMER_ID_PATTERN.fullmatch(customer_id):
        raise ValueError("invalid customer_id")
    return customer_id


@dataclass(frozen=True)
class CustomerCredentials:
    """Per-tenant secrets returned by the OWeb credentials API."""

    google_ads: dict[str, Any]
    meta_ads: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> CustomerCredentials:
        google = payload.get("google_ads")
        meta = payload.get("meta_ads")
        return cls(
            google_ads=dict(google) if isinstance(google, dict) else {},
            meta_ads=dict(meta) if isinstance(meta, dict) else {},
        )


class CredentialStore(Protocol):
    """Resolve per-customer platform credentials for MCP proxy requests."""

    async def get(self, customer_id: str) -> CustomerCredentials:
        """Return credentials for ``customer_id``."""
        ...


class JsonCredentialStore:
    """Static JSON map for local smoke tests (``OWEB_CUSTOMER_CREDENTIALS_JSON``)."""

    def __init__(self, mapping: dict[str, dict[str, Any]]) -> None:
        self._mapping = mapping

    async def get(self, customer_id: str) -> CustomerCredentials:
        safe_id = validate_customer_id(customer_id)
        payload = self._mapping.get(safe_id)
        if not isinstance(payload, dict):
            raise KeyError(f"unknown OWeb customer_id: {customer_id}")
        return CustomerCredentials.from_payload(payload)


class HttpCredentialStore:
    """Fetch credentials from the OWeb app internal API."""

    def __init__(self, base_url: str, service_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token

    async def get(self, customer_id: str) -> CustomerCredentials:
        safe_id = validate_customer_id(customer_id)
        url = f"{self._base_url}/{safe_id}"
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._service_token}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise KeyError(f"unknown OWeb customer_id: {customer_id}") from exc
            raise
        if not isinstance(payload, dict):
            raise ValueError("credentials API must return a JSON object")
        return CustomerCredentials.from_payload(payload)


def build_credential_store() -> CredentialStore | None:
    """Build a store from env, or ``None`` when proxy mode is not configured."""
    api_url = os.environ.get("OWEB_CREDENTIALS_API_URL", "").strip()
    service_token = os.environ.get("OWEB_MCP_PROXY_SECRET", "").strip()
    if api_url and service_token:
        return HttpCredentialStore(api_url, service_token)

    raw_json = os.environ.get("OWEB_CUSTOMER_CREDENTIALS_JSON", "").strip()
    if raw_json:
        mapping = json.loads(raw_json)
        if not isinstance(mapping, dict):
            raise ValueError("OWEB_CUSTOMER_CREDENTIALS_JSON must be a JSON object")
        return JsonCredentialStore(mapping)

    return None
