"""
Gemma 4 (26B-A4B-it) vLLM Server on Modal.
File: examples/basic-deployment/gemma_server.py

Closely mirrors Modal's canonical vllm_inference.py example, verified against
https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/vllm_inference.py

Usage:
    modal setup                                                    # first-time auth
    modal secret create huggingface-secret HF_TOKEN=hf_xxx         # if model is gated
    modal deploy examples/basic-deployment/gemma_server.py         # persistent deploy
    modal serve  examples/basic-deployment/gemma_server.py         # ephemeral, auto-reload
    modal run    examples/basic-deployment/gemma_server.py         # deploy + run test()

After `modal deploy`, Modal prints a URL like:
    https://<workspace>--gemma-4-vllm-server-serve.modal.run
OpenAI-compatible routes at {URL}/v1/*. Swagger at {URL}/docs.

Note: Gemma 4 is a gated model. Accept its license at
    https://huggingface.co/google/gemma-4-26B-A4B-it
before first run, and create a HuggingFace secret named "huggingface-secret"
with an HF_TOKEN env var.
"""

import json
from typing import Any

import aiohttp
import modal

# ----- Container image -----
# Pattern from Modal's canonical example. vLLM 0.19 + transformers 5.5 is the
# currently working combination for Gemma 4 on Modal. Don't downgrade vllm.
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.19.0")
    .uv_pip_install("transformers==5.5.0")  # Gemma 4 needs this specific transformers version
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})   # Xet backend — fastest HF downloads
)

# ----- Model config -----
MODEL_NAME = "google/gemma-4-26B-A4B-it"
# Pinning a revision avoids surprises when HF repos update. Commit from Modal's
# canonical example — bump this after validating against newer revisions.
MODEL_REVISION = "47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301"

# ----- Volumes (persistent caches) -----
# Without these, every cold start re-downloads weights (minutes) and re-compiles
# CUDA graphs (tens of seconds to minutes).
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

# ----- App -----
app = modal.App("gemma-4-vllm-server")

N_GPU = 1
MINUTES = 60
VLLM_PORT = 8000

# FAST_BOOT=False = best steady-state throughput (CUDA graphs + torch.compile).
# Set True if you scale from zero frequently — trades throughput for ~30-60s less boot.
FAST_BOOT = False


@app.function(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=15 * MINUTES,   # how long to stay up after last request
    timeout=10 * MINUTES,            # container startup budget
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=100)    # requests one replica can handle concurrently
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * MINUTES)
def serve():
    """Spawn `vllm serve` as a subprocess. The @modal.web_server decorator
    exposes port 8000 publicly once the subprocess is accepting connections."""
    import subprocess

    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--served-model-name", MODEL_NAME, "llm",   # alias "llm" for client convenience
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--uvicorn-log-level=info",
        "--async-scheduling",
    ]

    # Explicit enforce-eager toggle — either disable compilation+graphs, or force them on.
    cmd += ["--enforce-eager" if FAST_BOOT else "--no-enforce-eager"]

    # Tensor parallelism: splits large matmuls across GPUs. Passed even for N=1.
    cmd += ["--tensor-parallel-size", str(N_GPU)]

    # Gemma 4 specifics: text-only, with reasoning + tool calling.
    cmd += [
        "--limit-mm-per-prompt",
        f"'{json.dumps({'image': 0, 'video': 0, 'audio': 0})}'",
        "--enable-auto-tool-choice",
        "--reasoning-parser", "gemma4",
        "--tool-call-parser", "gemma4",
    ]

    print("Launching:", *cmd)
    subprocess.Popen(" ".join(cmd), shell=True)


@app.local_entrypoint()
async def test(test_timeout: int = 10 * MINUTES, content: str | None = None):
    """Healthcheck + a single streamed completion to validate the deployment."""
    url = await serve.get_web_url.aio()

    messages = [
        {"role": "system", "content": "You are a terse, precise assistant."},
        {"role": "user",   "content": content or "Explain the singular value decomposition in two sentences."},
    ]

    async with aiohttp.ClientSession(base_url=url) as session:
        print(f"Healthcheck at {url}/health")
        async with session.get("/health", timeout=test_timeout - MINUTES) as r:
            assert r.status == 200, f"Health check failed: {r.status}"
        print("Healthy.")

        payload: dict[str, Any] = {
            "model": "llm",
            "messages": messages,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": True},
        }
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

        print(f"POST {url}/v1/chat/completions")
        async with session.post("/v1/chat/completions", json=payload, headers=headers) as r:
            async for raw in r.content:
                r.raise_for_status()
                line = raw.decode().strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    line = line[len("data: "):]
                chunk = json.loads(line)
                delta = chunk["choices"][0]["delta"]
                out = delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning")
                if out:
                    print(out, end="", flush=True)
        print()
