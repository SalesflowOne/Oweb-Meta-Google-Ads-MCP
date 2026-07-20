"""OWeb MCP proxy authentication and credential injection."""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mureo.auth_oweb import activate_request
from mureo.oweb.credential_store import CredentialStore, build_credential_store
from mureo.oweb.headers import merge_credentials_to_headers
from mureo.oweb.platform_env import load_platform_credentials

if TYPE_CHECKING:
    from collections.abc import Callable

HEADER_CUSTOMER_ID = "X-OWeb-Customer-Id"
_PROXY_PREFIX = "/api/oweb/mcp"


def _proxy_secret() -> str | None:
    value = os.environ.get("OWEB_MCP_PROXY_SECRET", "").strip()
    return value or None


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    token = auth[7:].strip()
    return token or None


def _authorize_proxy(request: Request) -> bool:
    expected = _proxy_secret()
    if not expected:
        return False
    token = _bearer_token(request)
    if not token:
        return False
    return secrets.compare_digest(token, expected)


class OWebProxyMiddleware(BaseHTTPMiddleware):
    """Inject per-customer credentials on ``/api/oweb/mcp`` requests."""

    def __init__(
        self,
        app: Callable[..., object],
        store: CredentialStore | None = None,
        *,
        always_proxy: bool = False,
    ) -> None:
        super().__init__(app)
        self._store = store if store is not None else build_credential_store()
        self._platform = load_platform_credentials()
        self._always_proxy = always_proxy

    def _is_proxy_path(self, request: Request) -> bool:
        if self._always_proxy:
            return True
        path = request.url.path.rstrip("/") or "/"
        return path.startswith(_PROXY_PREFIX.rstrip("/"))

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._is_proxy_path(request):
            return await call_next(request)

        if not _authorize_proxy(request):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        if self._store is None:
            return JSONResponse(
                {"error": "OWeb proxy credentials store is not configured"},
                status_code=503,
            )

        customer_id = request.headers.get(HEADER_CUSTOMER_ID, "").strip()
        if not customer_id:
            return JSONResponse(
                {"error": f"Missing {HEADER_CUSTOMER_ID} header"},
                status_code=400,
            )

        try:
            customer = await self._store.get(customer_id)
        except KeyError:
            return JSONResponse({"error": "Unknown customer"}, status_code=404)
        except (OSError, ValueError) as exc:
            return JSONResponse(
                {"error": f"Credentials lookup failed: {exc}"},
                status_code=502,
            )

        headers = merge_credentials_to_headers(self._platform, customer)
        async with activate_request(headers):
            return await call_next(request)
