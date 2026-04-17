"""
Test client for a Modal vLLM inference server.
File: examples/basic-deployment/test_client.py

Hits the deployed OpenAI-compatible endpoint with a few smoke tests.
Runs locally — no Modal decorators, no Modal runtime required.

Usage:
    # Against a public (unsecured) endpoint:
    BASE_URL=https://<workspace>--gemma-4-vllm-server-serve.modal.run/v1 \\
        python examples/basic-deployment/test_client.py

    # Against a Modal-proxy-auth-protected endpoint (gemma_secured_server.py):
    BASE_URL=https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1 \\
    MODAL_TOKEN_ID=wk-... \\
    MODAL_TOKEN_SECRET=ws-... \\
        python examples/basic-deployment/test_client.py

    # Or against a local vLLM server:
    BASE_URL=http://localhost:8000/v1 python examples/basic-deployment/test_client.py

Env vars:
    BASE_URL            (required) OpenAI-compatible /v1 endpoint
    MODEL_NAME          (optional) served-model-name used at deploy time.
                        Defaults to "llm" — match what you passed to --served-model-name.
    API_KEY             (optional) if you set VLLM_API_KEY on the server, set it here too.
    MODAL_TOKEN_ID      (optional) Modal proxy auth Token ID.  If set, sent as Modal-Key header.
    MODAL_TOKEN_SECRET  (optional) Modal proxy auth Token Secret.  If set, sent as Modal-Secret header.
                        Create a token pair at https://modal.com/settings/proxy-auth-tokens.
"""

import os
import sys

from openai import OpenAI


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llm")
API_KEY = os.environ.get("API_KEY", "dummy")  # vLLM accepts any non-empty value by default

# If Modal proxy auth env vars are set, pass them as extra headers on every request.
MODAL_TOKEN_ID = os.environ.get("MODAL_TOKEN_ID")
MODAL_TOKEN_SECRET = os.environ.get("MODAL_TOKEN_SECRET")
_modal_auth_headers = {}
if MODAL_TOKEN_ID and MODAL_TOKEN_SECRET:
    _modal_auth_headers = {
        "Modal-Key": MODAL_TOKEN_ID,
        "Modal-Secret": MODAL_TOKEN_SECRET,
    }
elif MODAL_TOKEN_ID or MODAL_TOKEN_SECRET:
    print(
        "WARNING: Only one of MODAL_TOKEN_ID / MODAL_TOKEN_SECRET is set. "
        "Need BOTH for proxy auth to work. Proceeding without auth headers.",
        file=sys.stderr,
    )


def test_completions(client: OpenAI) -> list[dict]:
    """Smoke-test the chat completions endpoint with a few prompts."""
    cases = [
        ("Simple Q&A",    "What is the capital of France?",                                  100),
        ("Code gen",      "Write a Python function that returns the nth Fibonacci number.",  256),
        ("Explanation",   "Explain machine learning in two sentences.",                      256),
        ("Reasoning",     "If all roses are flowers and some flowers fade quickly, "
                          "what can we conclude?",                                           256),
    ]

    print(f"Endpoint: {BASE_URL}")
    print(f"Model:    {MODEL_NAME}\n")

    results = []
    for i, (name, prompt, max_tokens) in enumerate(cases, 1):
        print(f"Test {i}: {name}")
        print(f"  Prompt: {prompt}")
        try:
            r = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            text = r.choices[0].message.content
            usage = r.usage.model_dump() if hasattr(r.usage, "model_dump") else dict(r.usage)
            print(f"  Response: {text[:200]}{'...' if len(text) > 200 else ''}")
            print(f"  Tokens:   {usage}\n")
            results.append({"name": name, "ok": True, "tokens": usage.get("total_tokens", 0)})
        except Exception as e:
            print(f"  ERROR: {e}\n")
            results.append({"name": name, "ok": False, "error": str(e)})

    passed = sum(1 for r in results if r["ok"])
    total_tokens = sum(r.get("tokens", 0) for r in results if r["ok"])
    print(f"Summary: {passed}/{len(results)} passed, {total_tokens} total tokens")
    return results


def test_streaming(client: OpenAI) -> None:
    """Smoke-test streaming. Prints tokens to stdout as they arrive."""
    print("\n--- Streaming test ---")
    prompt = "Write two sentences about a robot learning carpentry."
    print(f"Prompt: {prompt}\nResponse: ", end="", flush=True)

    stream = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        stream=True,
    )
    chunks = 0
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            chunks += 1
    print(f"\n({chunks} chunks received)")


def main() -> int:
    if BASE_URL == "http://localhost:8000/v1":
        print("Warning: BASE_URL not set, defaulting to localhost.", file=sys.stderr)
        print("For a Modal deploy, set BASE_URL to the URL modal printed.\n", file=sys.stderr)

    if _modal_auth_headers:
        print("Modal proxy auth: enabled (sending Modal-Key + Modal-Secret headers)\n")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        default_headers=_modal_auth_headers or None,
    )
    results = test_completions(client)
    if all(r["ok"] for r in results):
        test_streaming(client)
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
