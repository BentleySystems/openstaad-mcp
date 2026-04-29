# HTTP Auth Redesign — OTS-based Token Delivery

> **Note (2026-04-28):** The `--email` flag and `OPENSTAAD_EMAIL` env var described below were removed in v2.1.0. The server now displays the bearer token via a one-time OTS share URL in the terminal auth banner. No email is sent.

> Status: **Proposed** · April 2026
> Addresses: OMCP-012 (token visible in process args)

## Problem

HTTP mode currently requires `--token <value>` on the command line. The bearer token is visible in `ps aux` / Task Manager / process explorer,
which is unacceptable on multi-user machines. The admin must also invent and securely distribute the token out of band.

## Solution

Replace `--token` with `--email` (also settable via `OPENSTAAD_EMAIL`). At startup the server:

1. Generates a cryptographic random bearer token in memory.
2. Calls the **OneTimeSecret v2 guest** endpoint (no API key required) to
   create a one-time-secret containing the token, emailed to the address.
3. Starts the HTTP listener using the in-memory token for authentication.

The user receives an email with a one-time link, retrieves the token, and provides it to their MCP client (VS Code promptString, Claude env var,
etc). The token **never appears on the CLI or in any file on the server**.

## OTS v2 Guest API

| Property | Value |
|---|---|
| Endpoint | `POST /api/v2/guest/secret/conceal` |
| Auth | None (guest = anonymous) |
| Base URL | `https://uk.onetimesecret.com` (configurable via `--ots-base-url`) |
| Rate limits | Unknown for guest; only 1 call per server startup |

### Request body

```json
{
  "secret": {
    "kind": "conceal",
    "share_domain": "uk.onetimesecret.com",
    "secret": "<generated-bearer-token>",
    "recipient": "user@example.com",
    "ttl": 86400
  }
}
```

### Response (key fields)

```json
{
  "record": {
    "receipt": { "share_url": "https://uk.onetimesecret.com/secret/abc123", ... },
    "secret":  { "identifier": "abc123", "state": "new", ... }
  }
}
```

## CLI Changes

### Removed
- `--token` — no longer accepted

### New flags (HTTP mode only)

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--email` | `OPENSTAAD_EMAIL` | *(required for HTTP)* | Recipient for the one-time token email |
| `--ots-base-url` | — | `https://uk.onetimesecret.com` | OTS regional endpoint |

### Precedence
`--email` CLI flag overrides `OPENSTAAD_EMAIL` env var.

## Startup Sequence (HTTP mode)

```
1. Parse args → require --email or OPENSTAAD_EMAIL
2. token = secrets.token_urlsafe(32)
3. POST {ots-base-url}/api/v2/guest/secret/conceal
     body: { secret: { kind: "conceal", share_domain: <host>, secret: token, recipient: email, ttl: 86400 } }
4. If OTS succeeds:
     Log: "✓ Bearer token emailed to {email} via OneTimeSecret" Log: "  User should check email for the one-time link"
5. If OTS fails:
     Log warning: "OTS delivery failed: {reason}"
     Log: "FALLBACK — bearer token (copy this securely):" Print token to stderr (one time only, user must copy)
6. Configure StaticTokenVerifier with token
7. Start HTTP listener on 127.0.0.1:{port}
```

## Failure Modes

| Scenario | Behaviour |
|---|---|
| OTS API unreachable | Fallback: print token to stderr with warning |
| OTS returns error | Fallback: print token to stderr with warning |
| OTS rate-limited | Fallback: print token to stderr with warning |
| Email never arrives | Admin can re-run server, or use stderr fallback token |
| Invalid email format | Reject at startup (basic validation) |

## Client Configuration Examples

### VS Code (`mcp.json`)

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "openstaad-token",
      "description": "Paste bearer token from OTS email", "password": true } ], "servers": {
    "openstaad": {
      "url": "http://staad-host:18120/mcp/",
      "headers": {
        "Authorization": "Bearer ${input:openstaad-token}" } } } }
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "openstaad": {
      "url": "http://staad-host:18120/mcp/",
      "headers": {
        "Authorization": "Bearer <paste-token-from-ots-email>" } } } }
```

## Security Properties

- **No CLI token exposure**: Token generated in memory, never in argv. - **One-time delivery**: OTS link auto-destructs after first read.
- **No OTS account needed**: Guest endpoint, no API keys to rotate. - **Encrypted in transit**: OTS link is HTTPS; MCP client should use HTTPS too (or SSH tunnel) for production.
- **Short-lived link**: 24h TTL on the OTS secret (configurable).

## Dependencies

- **None added**. Uses Python stdlib `urllib.request` + `json` + `secrets`. - OTS is a runtime call, not a build dependency.

## Backwards Compatibility

- `--token` is **removed**. Any automation using `--token` must switch to `--email` / `OPENSTAAD_EMAIL`.
- stdio mode is unchanged.
