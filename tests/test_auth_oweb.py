"""Tests for OWeb header-based credential loading."""

from __future__ import annotations

import pytest

from mureo.auth import load_google_ads_credentials, load_meta_ads_credentials
from mureo.auth_oweb import (
    HEADER_GOOGLE_CLIENT_ID,
    HEADER_GOOGLE_CLIENT_SECRET,
    HEADER_GOOGLE_DEVELOPER_TOKEN,
    HEADER_GOOGLE_REFRESH_TOKEN,
    HEADER_META_ACCESS_TOKEN,
    HEADER_META_ACCOUNT_ID,
    activate_request,
    build_secret_store,
    credentials_from_headers,
    is_oweb_request,
)


@pytest.mark.unit
class TestCredentialsFromHeaders:
    def test_parses_google_and_meta_sections(self) -> None:
        headers = {
            HEADER_GOOGLE_DEVELOPER_TOKEN: "dev",
            HEADER_GOOGLE_CLIENT_ID: "cid",
            HEADER_GOOGLE_CLIENT_SECRET: "secret",
            HEADER_GOOGLE_REFRESH_TOKEN: "refresh",
            HEADER_META_ACCESS_TOKEN: "meta-token",
            HEADER_META_ACCOUNT_ID: "act_999",
        }
        data = credentials_from_headers(headers)
        assert data["google_ads"]["developer_token"] == "dev"
        assert data["google_ads"]["client_id"] == "cid"
        assert data["meta_ads"]["access_token"] == "meta-token"
        assert data["meta_ads"]["account_id"] == "act_999"

    def test_case_insensitive_header_names(self) -> None:
        headers = {
            "x-mureo-meta-ads-access-token": "tok",
        }
        data = credentials_from_headers(headers)
        assert data["meta_ads"]["access_token"] == "tok"

    def test_empty_headers_yield_empty_dict(self) -> None:
        assert credentials_from_headers({}) == {}


@pytest.mark.unit
class TestHeaderSecretStore:
    async def test_load_google_via_auth_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
        monkeypatch.delenv("GOOGLE_ADS_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_ADS_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("GOOGLE_ADS_REFRESH_TOKEN", raising=False)

        headers = {
            HEADER_GOOGLE_DEVELOPER_TOKEN: "dev",
            HEADER_GOOGLE_CLIENT_ID: "cid",
            HEADER_GOOGLE_CLIENT_SECRET: "secret",
            HEADER_GOOGLE_REFRESH_TOKEN: "refresh",
        }
        async with activate_request(headers):
            assert is_oweb_request() is True
            creds = load_google_ads_credentials()
            assert creds is not None
            assert creds.developer_token == "dev"
            assert creds.refresh_token == "refresh"

        assert is_oweb_request() is False

    async def test_oweb_scope_skips_env_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "from-env")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "from-env")
        monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "from-env")
        monkeypatch.setenv("GOOGLE_ADS_REFRESH_TOKEN", "from-env")

        async with activate_request({}):
            assert load_google_ads_credentials() is None

    async def test_meta_load_from_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("META_ADS_ACCESS_TOKEN", raising=False)

        headers = {
            HEADER_META_ACCESS_TOKEN: "meta-tok",
            HEADER_META_ACCOUNT_ID: "act_42",
        }
        async with activate_request(headers):
            creds = load_meta_ads_credentials()
            assert creds is not None
            assert creds.access_token == "meta-tok"
            assert creds.account_id == "act_42"

    def test_store_is_read_only(self) -> None:
        store = build_secret_store({HEADER_META_ACCESS_TOKEN: "x"})
        with pytest.raises(Exception, match="read-only"):
            store.save("meta_ads", {"access_token": "y"})
