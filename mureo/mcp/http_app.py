"""Streamable HTTP MCP ASGI application for OWeb (Vercel).

Exposes the same tool surface as :mod:`mureo.mcp.server` over MCP Streamable
HTTP in **stateless** mode (one transport per request — suitable for serverless).
Credentials are read from ``X-Mureo-*`` request headers via
:mod:`mureo.auth_oweb`; ``~/.mureo/credentials.json`` is never consulted.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import (  # noqa: TC002
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request  # noqa: TC002
from starlette.responses import Response  # noqa: TC002
from starlette.routing import Route
from starlette.types import Receive, Scope, Send  # noqa: TC002

from mureo.auth_oweb import activate_request
from mureo.mcp.server import _create_server
from mureo.oweb.credential_store import CredentialStore
from mureo.oweb.proxy import OWebProxyMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_MCP_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]


class OWebCredentialsMiddleware(BaseHTTPMiddleware):
    """Bind ``X-Mureo-*`` headers to the current request's credential scope."""

    def __init__(
        self,
        app: object,
        proxy_only: bool = False,
    ) -> None:
        super().__init__(app)
        self._proxy_only = proxy_only

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if self._proxy_only or request.url.path.startswith("/api/oweb/mcp"):
            return await call_next(request)
        async with activate_request(request.headers):
            return await call_next(request)


class StreamableMCPASGI:
    """ASGI callable that forwards to the Streamable HTTP session manager."""

    def __init__(self) -> None:
        self._session_manager: StreamableHTTPSessionManager | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._session_manager is None:
            raise RuntimeError(
                "OWeb MCP session manager is not running; Starlette lifespan "
                "has not started."
            )
        await self._session_manager.handle_request(scope, receive, send)


def create_app(
    credential_store: CredentialStore | None = None,
    *,
    proxy_only: bool = False,
) -> Starlette:
    """Build the Starlette ASGI app exported by ``api/mcp/index.py``."""
    mcp_server = _create_server()
    mcp_asgi = StreamableMCPASGI()

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        mcp_asgi._session_manager = StreamableHTTPSessionManager(
            app=mcp_server,
            json_response=True,
            stateless=True,
        )
        async with mcp_asgi._session_manager.run():
            yield
        mcp_asgi._session_manager = None

    routes = (
        [Route("/", endpoint=mcp_asgi, methods=_MCP_METHODS)]
        if proxy_only
        else [
            Route("/", endpoint=mcp_asgi, methods=_MCP_METHODS),
            Route("/api/mcp", endpoint=mcp_asgi, methods=_MCP_METHODS),
            Route("/api/mcp/", endpoint=mcp_asgi, methods=_MCP_METHODS),
            Route("/api/oweb/mcp", endpoint=mcp_asgi, methods=_MCP_METHODS),
            Route("/api/oweb/mcp/", endpoint=mcp_asgi, methods=_MCP_METHODS),
        ]
    )

    return Starlette(
        routes=routes,
        middleware=[
            Middleware(
                OWebProxyMiddleware,
                store=credential_store,
                always_proxy=proxy_only,
            ),
            Middleware(OWebCredentialsMiddleware, proxy_only=proxy_only),
        ],
        lifespan=lifespan,
    )
