# OWeb — Streamable HTTP MCP on Vercel

OWeb Phase 0 exposes mureo's Google Ads and Meta Ads MCP tools over **Streamable HTTP** on Vercel. Credentials travel in **request headers** — the server never reads `~/.mureo/credentials.json`.

Both platform families are enabled (`google_ads_*` and `meta_ads_*`). Do **not** set `MUREO_DISABLE_GOOGLE_ADS` or `MUREO_DISABLE_META_ADS` on the deployment.

## Endpoint

After deploy:

```text
https://<your-project>.vercel.app/api/mcp
```

The handler is `api/mcp/index.py` (ASGI `app`). Routing is configured in `vercel.json`.

## Credential headers

Pass only the platforms you need. Header names are case-insensitive.

### Google Ads

| Header | Required | Maps to |
|--------|----------|---------|
| `X-Mureo-Google-Ads-Developer-Token` | Yes | `developer_token` |
| `X-Mureo-Google-Ads-Client-Id` | Yes | `client_id` |
| `X-Mureo-Google-Ads-Client-Secret` | Yes | `client_secret` |
| `X-Mureo-Google-Ads-Refresh-Token` | Yes | `refresh_token` |
| `X-Mureo-Google-Ads-Login-Customer-Id` | No | `login_customer_id` (MCC) |
| `X-Mureo-Google-Ads-Customer-Id` | No | default `customer_id` |

### Meta Ads

| Header | Required | Maps to |
|--------|----------|---------|
| `X-Mureo-Meta-Ads-Access-Token` | Yes | `access_token` |
| `X-Mureo-Meta-Ads-App-Id` | No | `app_id` (long-lived token refresh) |
| `X-Mureo-Meta-Ads-App-Secret` | No | `app_secret` |
| `X-Mureo-Meta-Ads-Account-Id` | No | default `account_id` (`act_…`) |

Implementation: `mureo/auth_oweb.py`.

## MCP over Streamable HTTP (stateless)

The deployment uses **stateless** Streamable HTTP (`json_response=true`): each `POST` is handled independently (no session id required). Send `Accept: application/json` and `Content-Type: application/json`.

Replace placeholders in the examples below.

```bash
export MCP_URL="https://<your-project>.vercel.app/api/mcp"

# --- Google Ads headers (all four required for Google tools) ---
export H_GOOGLE_DEV="your-developer-token"
export H_GOOGLE_CID="your-oauth-client-id"
export H_GOOGLE_SECRET="your-oauth-client-secret"
export H_GOOGLE_REFRESH="your-oauth-refresh-token"
# optional:
# export H_GOOGLE_CUSTOMER="1234567890"

# --- Meta Ads headers ---
export H_META_TOKEN="your-meta-access-token"
export H_META_ACCOUNT="act_1234567890"
```

### `tools/list` (both `google_ads_*` and `meta_ads_*`)

```bash
curl -sS "$MCP_URL" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "X-Mureo-Google-Ads-Developer-Token: $H_GOOGLE_DEV" \
  -H "X-Mureo-Google-Ads-Client-Id: $H_GOOGLE_CID" \
  -H "X-Mureo-Google-Ads-Client-Secret: $H_GOOGLE_SECRET" \
  -H "X-Mureo-Google-Ads-Refresh-Token: $H_GOOGLE_REFRESH" \
  -H "X-Mureo-Meta-Ads-Access-Token: $H_META_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '.result.tools[].name' | grep -E '^(google_ads_|meta_ads_)' | head
```

You should see names such as `google_ads_accounts_list` and `meta_ads_campaigns_list`.

### Google read tool — `google_ads_accounts_list`

Lists accessible Google Ads accounts (read-only; no `customer_id` argument required when using an MCC).

```bash
curl -sS "$MCP_URL" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "X-Mureo-Google-Ads-Developer-Token: $H_GOOGLE_DEV" \
  -H "X-Mureo-Google-Ads-Client-Id: $H_GOOGLE_CID" \
  -H "X-Mureo-Google-Ads-Client-Secret: $H_GOOGLE_SECRET" \
  -H "X-Mureo-Google-Ads-Refresh-Token: $H_GOOGLE_REFRESH" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"google_ads_accounts_list","arguments":{}}}' \
  | jq .
```

### Meta read tool — `meta_ads_campaigns_list`

Pass `account_id` in the tool arguments or set `X-Mureo-Meta-Ads-Account-Id`.

```bash
curl -sS "$MCP_URL" \
  -H 'Accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "X-Mureo-Meta-Ads-Access-Token: $H_META_TOKEN" \
  -H "X-Mureo-Meta-Ads-Account-Id: $H_META_ACCOUNT" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"meta_ads_campaigns_list","arguments":{}}}' \
  | jq .
```

## Local smoke test

With the dev server (Starlette / uvicorn) pointed at the same `app`:

```bash
pip install -e ".[dev]"
uvicorn api.mcp.index:app --host 127.0.0.1 --port 8787
```

Then use `MCP_URL=http://127.0.0.1:8787/` in the curl examples above.

## Security notes

- Treat credential headers like secrets: use HTTPS only, avoid logging them, and prefer short-lived tokens where the platform allows.
- OWeb does not persist refreshed Meta tokens to disk; token refresh still works in-process when `app_id` / `app_secret` headers are supplied.
- BYOD (`~/.mureo/byod/`) is not used on Vercel — only live API credentials from headers apply.
