"""
Gemma 4 vLLM Server on Modal — WITH MODAL PROXY AUTHENTICATION.
File: examples/basic-deployment/gemma_secured_server.py

Same model and server as gemma_server.py, but the endpoint is gated by
Modal's proxy authentication — requests without valid Modal-Key/Modal-Secret
headers are rejected by Modal's infrastructure BEFORE any container spins up.

Why this matters:
  * Unauthorized requests cost you zero (no container wake-up)
  * No third-party auth service, no Unkey/FastAPI-Users/etc. plumbing
  * Built-in at the decorator level — add one flag, the endpoint is protected
  * Supported on web_server, fastapi_endpoint, asgi_app, wsgi_app

How to use it:
  1. Deploy this file:   modal deploy gemma_secured_server.py
  2. Create a Proxy Auth Token: https://modal.com/settings/proxy-auth-tokens
     You'll get a Token ID (looks like "wk-abc123") and a Secret ("ws-xyz789").
     SAVE THE SECRET NOW — it's shown only once.
  3. Call the endpoint with both headers:

     curl -X POST https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1/chat/completions \\
       -H "Modal-Key: $MODAL_TOKEN_ID" \\
       -H "Modal-Secret: $MODAL_TOKEN_SECRET" \\
       -H "Content-Type: application/json" \\
       -d '{"model":"llm","messages":[{"role":"user","content":"hi"}]}'

  Modal's dashboard will show the endpoint URL decorated with a 🔑 emoji.
  Hitting it without auth headers returns 401 Unauthorized (no container spin-up).

Reference:
  https://modal.com/docs/guide/webhook-proxy-auth
  modal-examples/07_web_endpoints/basic_web.py (fastapi_endpoint version)
"""

import subprocess

import aiohttp
import modal

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("gemma-4-secured-vllm")

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.19.0")
    .uv_pip_install("transformers==5.5.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

MODEL_NAME = "google/gemma-4-26B-A4B-it"
MODEL_REVISION = "47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301"
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)


@app.function(
    image=vllm_image,
    gpu="H200:1",
    scaledown_window=5 * MINUTES,
    timeout=10 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
@modal.concurrent(max_inputs=64)
@modal.web_server(
    port=VLLM_PORT,
    startup_timeout=10 * MINUTES,
    requires_proxy_auth=True,  # <-- THE ONE FLAG THAT MATTERS
)
def serve():
    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--served-model-name", MODEL_NAME, "llm",
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--uvicorn-log-level=info",
        "--tensor-parallel-size", "1",
        "--gpu-memory-utilization", "0.90",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "gemma4",
        "--tool-call-parser", "gemma4",
    ]
    subprocess.Popen(cmd)


@app.local_entrypoint()
async def test(content: str | None = None):
    """Healthcheck + completion, using proxy auth headers.

    Reads MODAL_TOKEN_ID and MODAL_TOKEN_SECRET from the local environment.
    Create them at https://modal.com/settings/proxy-auth-tokens, then:

        export MODAL_TOKEN_ID=wk-...
        export MODAL_TOKEN_SECRET=ws-...
        modal run examples/basic-deployment/gemma_secured_server.py
    """
    import os

    token_id = os.environ.get("MODAL_TOKEN_ID")
    token_secret = os.environ.get("MODAL_TOKEN_SECRET")
    if not token_id or not token_secret:
        raise SystemExit(
            "Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET environment variables.\n"
            "Create them at https://modal.com/settings/proxy-auth-tokens."
        )

    url = await serve.get_web_url.aio()
    print(f"Endpoint: {url} 🔑")

    auth_headers = {
        "Modal-Key": token_id,
        "Modal-Secret": token_secret,
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": "You are a terse, precise assistant."},
        {"role": "user",   "content": content or "What's the capital of France?"},
    ]
    payload = {"model": "llm", "messages": messages, "max_tokens": 64}

    async with aiohttp.ClientSession(base_url=url) as session:
        # Health check first — proves auth works
        async with session.get("/health", headers=auth_headers, timeout=2 * MINUTES) as r:
            assert r.status == 200, f"healthcheck failed: {r.status} — auth token rejected?"
            print("  /health OK (auth accepted)")

        async with session.post("/v1/chat/completions", json=payload, headers=auth_headers) as r:
            r.raise_for_status()
            data = await r.json()
            print(data["choices"][0]["message"]["content"])
