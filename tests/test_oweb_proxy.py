"""Tests for OWeb MCP proxy credential resolution."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from mureo.mcp.http_app import create_app
from mureo.oweb.credential_store import CustomerCredentials, JsonCredentialStore
from mureo.oweb.headers import merge_credentials_to_headers


def _mcp_post(
    client: TestClient,
    path: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    merged = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **headers,
    }
    response = client.post(path, json=payload, headers=merged)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    return body


@pytest.mark.unit
class TestMergeCredentialsToHeaders:
    def test_merges_platform_and_customer_google_fields(self) -> None:
        platform = {
            "google_ads": {
                "developer_token": "dev",
                "client_id": "cid",
                "client_secret": "secret",
            }
        }
        customer = CustomerCredentials(
            google_ads={"refresh_token": "refresh", "customer_id": "8416959156"},
            meta_ads={},
        )
        headers = merge_credentials_to_headers(platform, customer)
        assert headers["X-Mureo-Google-Ads-Developer-Token"] == "dev"
        assert headers["X-Mureo-Google-Ads-Refresh-Token"] == "refresh"
        assert headers["X-Mureo-Google-Ads-Customer-Id"] == "8416959156"


@pytest.mark.unit
class TestOWebProxyRoute:
    @pytest.fixture
    def proxy_client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        monkeypatch.setenv("OWEB_MCP_PROXY_SECRET", "proxy-secret")
        monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev-token")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "client-id")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "client-secret")
        store = JsonCredentialStore(
            {
                "cust-1": {
                    "google_ads": {
                        "refresh_token": "customer-refresh",
                        "customer_id": "8416959156",
                    }
                }
            }
        )
        with TestClient(create_app(credential_store=store, proxy_only=True)) as client:
            yield client

    def test_proxy_requires_auth(self, proxy_client: TestClient) -> None:
        response = proxy_client.post(
            "/",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-OWeb-Customer-Id": "cust-1",
            },
        )
        assert response.status_code == 401

    def test_proxy_tools_list_uses_customer_credentials(
        self, proxy_client: TestClient
    ) -> None:
        body = _mcp_post(
            proxy_client,
            "/",
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            {
                "Authorization": "Bearer proxy-secret",
                "X-OWeb-Customer-Id": "cust-1",
            },
        )
        names = {tool["name"] for tool in body["result"]["tools"]}
        assert "google_ads_accounts_list" in names

    def test_proxy_google_accounts_list(self, proxy_client: TestClient) -> None:
        mock_accounts = AsyncMock(
            return_value=[
                {
                    "id": "8416959156",
                    "descriptive_name": "Customer",
                    "currency_code": "USD",
                    "time_zone": "America/New_York",
                    "manager": False,
                }
            ]
        )
        with patch("mureo.google_ads.list_accessible_accounts", mock_accounts):
            body = _mcp_post(
                proxy_client,
                "/",
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "google_ads_accounts_list",
                        "arguments": {},
                    },
                },
                {
                    "Authorization": "Bearer proxy-secret",
                    "X-OWeb-Customer-Id": "cust-1",
                },
            )
        payload = json.loads(body["result"]["content"][0]["text"])
        assert payload[0]["id"] == "8416959156"
