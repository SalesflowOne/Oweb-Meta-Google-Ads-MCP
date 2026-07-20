"""Vercel serverless entrypoint — OWeb customer MCP proxy."""

from __future__ import annotations

from mureo.mcp.http_app import create_app

app = create_app(proxy_only=True)
