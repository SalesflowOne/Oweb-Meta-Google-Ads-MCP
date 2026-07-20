"""Vercel serverless entrypoint — Streamable HTTP MCP for OWeb.

Vercel detects the top-level ``app`` ASGI object and serves it at ``/api/mcp``.
"""

from __future__ import annotations

from mureo.mcp.http_app import create_app

app = create_app()
