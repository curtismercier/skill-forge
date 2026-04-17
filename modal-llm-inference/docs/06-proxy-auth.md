# Modal Proxy Auth — the one auth pattern this skill recommends

**Source of truth:** https://modal.com/docs/guide/webhook-proxy-auth
**Runnable example:** `examples/basic-deployment/gemma_secured_server.py`

## TL;DR

Modal has first-class endpoint auth built into its proxy layer. Unauthorized requests are rejected by Modal's infrastructure **before any container spins up**, so they cost you zero. Add one flag to your decorator, and your endpoint is protected.

This is the right pattern for almost every inference endpoint you'll deploy from this skill. Don't roll your own bearer-token FastAPI middleware unless you have a specific reason.

## The one-line change

```python
@modal.web_server(port=VLLM_PORT, startup_timeout=10*MINUTES, requires_proxy_auth=True)
def serve():
    subprocess.Popen(["vllm", "serve", MODEL_NAME, ...])
```

That's it. The decorator accepts `requires_proxy_auth=True` on all four web decorators: `web_server`, `fastapi_endpoint`, `asgi_app`, `wsgi_app`.

When you deploy, Modal prints the endpoint URL with a 🔑 emoji next to it, signaling it's secured.

## Client flow

### 1. Create a token pair

Visit https://modal.com/settings/proxy-auth-tokens and create a token. You'll get:

- **Token ID** — starts with `wk-` (this is public-ish, like an API key ID)
- **Token Secret** — starts with `ws-` (this is the actual secret, shown **once**, save it now)

Tokens belong to your Modal workspace. Anyone in the workspace can manage them. On RBAC workspaces you can scope tokens to specific environments.

### 2. Include two headers on every request

```
Modal-Key: wk-your-token-id
Modal-Secret: ws-your-token-secret
```

### 3. Use it

**curl:**
```bash
curl -X POST https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1/chat/completions \
  -H "Modal-Key: $MODAL_TOKEN_ID" \
  -H "Modal-Secret: $MODAL_TOKEN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"model":"llm","messages":[{"role":"user","content":"hi"}]}'
```

**OpenAI Python SDK:** pass the headers via `default_headers` — they're added to every request:
```python
from openai import OpenAI
import os

client = OpenAI(
    api_key="dummy",  # vLLM doesn't care, Modal handles real auth
    base_url="https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1",
    default_headers={
        "Modal-Key":    os.environ["MODAL_TOKEN_ID"],
        "Modal-Secret": os.environ["MODAL_TOKEN_SECRET"],
    },
)

response = client.chat.completions.create(
    model="llm",
    messages=[{"role": "user", "content": "hello"}],
)
```

**Node / OpenAI JS SDK:** same pattern via `defaultHeaders`:
```javascript
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: "dummy",
  baseURL: "https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1",
  defaultHeaders: {
    "Modal-Key":    process.env.MODAL_TOKEN_ID,
    "Modal-Secret": process.env.MODAL_TOKEN_SECRET,
  },
});
```

## Why proxy auth beats DIY bearer-token middleware

| Concern | Proxy auth | DIY middleware (FastAPI/Unkey/etc.) |
|---|---|---|
| Cost of unauthorized requests | $0 — rejected before container wake | Full cold-start + container seconds billed |
| Code complexity | One decorator flag | Imports, dependencies, request validation code |
| Token rotation | Dashboard UI, immediate | Redeploy + secret rotation |
| Token scope | Workspace, optionally per-env via RBAC | Whatever you build |
| Dashboard visibility | 🔑 emoji on endpoint URL | You track it yourself |
| Auth bypass risk | Enforced by Modal infra (outside your code) | Any middleware bug is an exposure |

The one case where DIY makes sense: if you need **per-user** auth (not per-workspace), e.g. a public SaaS where each paying customer gets their own key and you want to revoke/throttle individually. That's an Unkey-style use case. For internal deployments, team tools, agent orchestration — Modal proxy auth is strictly better.

## Rotating a token

1. Create a new token pair at https://modal.com/settings/proxy-auth-tokens
2. Update the clients using it
3. Delete the old pair

No redeploy required. Modal validates each token independently.

## Troubleshooting

**`401 Unauthorized` with a token that seems correct:**
- Check both headers are present. Missing either one → 401.
- Token values are case-sensitive. Don't trim whitespace manually; env vars can pick up trailing newlines.
- If you rotated tokens recently, make sure you're using the new pair.

**Local `modal serve` development with auth:**
- `modal serve` endpoints get the same 🔑 protection if `requires_proxy_auth=True` is set. Your local test client still needs the headers.
- For dev speed, deploy one unsecured version (different App name) alongside the secured one.

**Load testing a secured endpoint:**
- The load-test skeleton in `scripts/load_test/locustfile.py` reads `LOADTEST_AUTH` env var. For proxy auth, Locust needs both headers separately; edit the `headers` dict in the locustfile:

```python
headers = {
    "Modal-Key":    os.environ["MODAL_TOKEN_ID"],
    "Modal-Secret": os.environ["MODAL_TOKEN_SECRET"],
    "Accept":       "application/json",
}
```

## What this skill doesn't cover

**OIDC integration** — Modal can issue short-lived JWTs that AWS/GCP/Vault accept directly. Useful for function-to-external-service auth (e.g. your vLLM server calling S3). Separate concern from endpoint protection. See https://modal.com/docs/guide/oidc-integration.

**Per-user billing and quotas** — if you need Unkey/Clerk-style per-user keys with usage tracking, that's a layer on top of Modal proxy auth, not instead of it. Put your per-user middleware inside the vLLM container (or in a small FastAPI wrapper in front), and use Modal proxy auth as the outer perimeter.
