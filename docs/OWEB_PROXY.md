# OWeb MCP proxy — multi-tenant customer access

OWeb customers connect their own Google Ads / Meta Ads accounts via OAuth in the OWeb app. The **MCP proxy** lets your backend call mureo tools **without** exposing per-customer refresh tokens to browsers or AI clients.

## Architecture

```text
Customer browser
    → OWeb app ("Connect Google Ads" OAuth)
    → OWeb DB stores refresh_token per customer_id

OWeb backend (Next.js API route / worker)
    → POST https://<mcp-host>/api/oweb/mcp
        Authorization: Bearer <OWEB_MCP_PROXY_SECRET>
        X-OWeb-Customer-Id: <customer_uuid>
    → Proxy loads platform creds from env + customer creds from API
    → Injects X-Mureo-* headers in-process
    → mureo MCP tools run against that customer's account
```

Two public MCP surfaces:

| Endpoint | Who calls it | Credentials |
|----------|--------------|-------------|
| `/api/mcp` | Power users / debugging | Caller sends all `X-Mureo-*` headers |
| `/api/oweb/mcp` | OWeb backend only | Proxy injects creds from store + platform env |

## Platform env (shared, Vercel)

Set once on the MCP deployment — **not** per customer:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Your Google Ads API developer token |
| `GOOGLE_ADS_CLIENT_ID` | OWeb OAuth app client id |
| `GOOGLE_ADS_CLIENT_SECRET` | OWeb OAuth app client secret |
| `META_ADS_APP_ID` | Optional — Meta token refresh |
| `META_ADS_APP_SECRET` | Optional — Meta token refresh |
| `OWEB_MCP_PROXY_SECRET` | Shared secret between OWeb backend and MCP proxy |

Do **not** set `GOOGLE_ADS_REFRESH_TOKEN` globally when using multi-tenant proxy mode.

## Per-customer credentials

### Production: HTTP credentials API

Configure the proxy to call your OWeb internal API:

| Variable | Example |
|----------|---------|
| `OWEB_CREDENTIALS_API_URL` | `https://app.oweb.com/api/internal/mcp-credentials` |
| `OWEB_MCP_PROXY_SECRET` | Same value on MCP + OWeb backend |

The proxy performs:

```http
GET {OWEB_CREDENTIALS_API_URL}/{customer_id}
Authorization: Bearer {OWEB_MCP_PROXY_SECRET}
Accept: application/json
```

**Response body** (JSON):

```json
{
  "google_ads": {
    "refresh_token": "1//...",
    "customer_id": "8416959156",
    "login_customer_id": "1234567890"
  },
  "meta_ads": {
    "access_token": "EAA...",
    "account_id": "act_1234567890"
  }
}
```

Only include platforms the customer has connected. Omit keys they have not linked.

### Local / smoke test: JSON env

```bash
export OWEB_CUSTOMER_CREDENTIALS_JSON='{
  "cust-1": {
    "google_ads": {
      "refresh_token": "1//...",
      "customer_id": "8416959156"
    }
  }
}'
```

## OWeb app: Google Ads Connect (your side)

Implement in the OWeb app (not this repo):

1. **OAuth start** — redirect to Google with your `GOOGLE_ADS_CLIENT_ID`, scope `https://www.googleapis.com/auth/adwords`, `access_type=offline`, `prompt=consent`.
2. **OAuth callback** — exchange code for tokens; persist `refresh_token` keyed by `customer_id`.
3. **Credentials API** — `GET /api/internal/mcp-credentials/:customerId` returns the JSON shape above (service-auth only).
4. **MCP proxy client** — OWeb backend forwards MCP JSON-RPC to `/api/oweb/mcp` with `Authorization` + `X-OWeb-Customer-Id`.

Customers never see refresh tokens or developer tokens.

## Proxy request example

```bash
export MCP_PROXY_URL="https://<project>.vercel.app/api/oweb/mcp"
export OWEB_MCP_PROXY_SECRET="your-shared-secret"
export CUSTOMER_ID="cust-uuid-from-your-db"

curl -sS "$MCP_PROXY_URL" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $OWEB_MCP_PROXY_SECRET" \
  -H "X-OWeb-Customer-Id: $CUSTOMER_ID" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"google_ads_accounts_list","arguments":{}}}'
```

Parse SSE: lines starting with `data: ` contain JSON (see `docs/OWEB.md`).

## Security

- `OWEB_MCP_PROXY_SECRET` must only live on OWeb server + MCP deployment.
- Never expose the credentials API to browsers; service-to-service only.
- Rotate customer refresh tokens when they disconnect/reconnect Google Ads.
- Prefer encrypting `refresh_token` at rest in your DB.

## Implementation files

| Module | Role |
|--------|------|
| `mureo/oweb/proxy.py` | Proxy auth + credential injection middleware |
| `mureo/oweb/credential_store.py` | HTTP + JSON credential stores |
| `mureo/oweb/platform_env.py` | Shared platform env loader |
| `mureo/oweb/headers.py` | Merge platform + customer → `X-Mureo-*` |
| `api/oweb/mcp/index.py` | Vercel entry for `/api/oweb/mcp` |

See also: `docs/OWEB.md` (direct header MCP).
