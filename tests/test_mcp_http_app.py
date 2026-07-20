"""Tests for the OWeb Streamable HTTP MCP ASGI app."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from mureo.auth_oweb import (
    HEADER_GOOGLE_CLIENT_ID,
    HEADER_GOOGLE_CLIENT_SECRET,
    HEADER_GOOGLE_DEVELOPER_TOKEN,
    HEADER_GOOGLE_REFRESH_TOKEN,
    HEADER_META_ACCESS_TOKEN,
)
from mureo.mcp.http_app import create_app


def _google_headers() -> dict[str, str]:
    return {
        HEADER_GOOGLE_DEVELOPER_TOKEN: "dev-token",
        HEADER_GOOGLE_CLIENT_ID: "client-id",
        HEADER_GOOGLE_CLIENT_SECRET: "client-secret",
        HEADER_GOOGLE_REFRESH_TOKEN: "refresh-token",
    }


def _meta_headers() -> dict[str, str]:
    return {
        HEADER_META_ACCESS_TOKEN: "meta-access-token",
    }


def _mcp_post(
    client: TestClient,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    merged = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        **(headers or {}),
    }
    response = client.post("/", json=payload, headers=merged)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    return body


@pytest.fixture
def oweb_client() -> TestClient:
    with TestClient(create_app()) as client:
        yield client


@pytest.mark.unit
class TestOWebMCPHttp:
    def test_tools_list_includes_google_and_meta_families(
        self, oweb_client: TestClient
    ) -> None:
        body = _mcp_post(
            oweb_client,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={**_google_headers(), **_meta_headers()},
        )
        names = {tool["name"] for tool in body["result"]["tools"]}
        assert any(name.startswith("google_ads_") for name in names)
        assert any(name.startswith("meta_ads_") for name in names)
        assert "google_ads_accounts_list" in names
        assert "meta_ads_campaigns_list" in names

    def test_google_accounts_list_read_tool(self, oweb_client: TestClient) -> None:
        mock_accounts = AsyncMock(
            return_value=[
                {
                    "id": "1234567890",
                    "descriptive_name": "Test Account",
                    "currency_code": "USD",
                    "time_zone": "America/New_York",
                    "manager": False,
                }
            ]
        )
        with patch(
            "mureo.google_ads.list_accessible_accounts",
            mock_accounts,
        ):
            body = _mcp_post(
                oweb_client,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "google_ads_accounts_list",
                        "arguments": {},
                    },
                },
                headers=_google_headers(),
            )
        text_blocks = body["result"]["content"]
        assert text_blocks[0]["type"] == "text"
        payload = json.loads(text_blocks[0]["text"])
        assert payload[0]["id"] == "1234567890"

    def test_meta_campaigns_list_read_tool(
        self, oweb_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "mureo.mcp._handlers_meta_ads.byod_has",
            lambda _platform: False,
        )
        mock_client = AsyncMock()
        mock_client.list_campaigns.return_value = [
            {"id": "1", "name": "Brand", "status": "ACTIVE"}
        ]
        with (
            patch(
                "mureo.mcp._handlers_meta_ads.create_meta_ads_client",
                return_value=mock_client,
            ),
            patch(
                "mureo.mcp._handlers_meta_ads.refresh_meta_token_if_needed",
                new_callable=AsyncMock,
                side_effect=lambda creds, path=None: creds,
            ),
        ):
            body = _mcp_post(
                oweb_client,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "meta_ads_campaigns_list",
                        "arguments": {"account_id": "act_999"},
                    },
                },
                headers=_meta_headers(),
            )
        text_blocks = body["result"]["content"]
        payload = json.loads(text_blocks[0]["text"])
        assert payload[0]["name"] == "Brand"
