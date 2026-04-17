"""
MiniMax-M2.7 vLLM Server on Modal.
File: examples/basic-deployment/minimax_server.py

MiniMax-M2.7 is a 229B-param MoE model (10B active), FP8 native.
At ~230GB of weights, this is a "very large model" by Modal's classification
and follows the Cls lifecycle pattern from:
https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/very_large_models.py

Key differences from the simple gemma_server.py pattern:
  * Weights pre-downloaded at Image build time (avoids 10+ minute cold-start
    download on first run)
  * modal.Cls with @modal.enter/@modal.exit for explicit server lifecycle
  * Multi-GPU via --tensor-parallel-size; 4xH200 is the working floor
  * Uses modal.experimental.http_server for lower-latency routing

Prerequisites:
    modal setup
    modal secret create huggingface-secret HF_TOKEN=hf_xxx    # if needed

Deploy:
    modal deploy examples/basic-deployment/minimax_server.py

Model card (sampling defaults, parsers, reasoning format):
    https://huggingface.co/MiniMaxAI/MiniMax-M2.7

Important: MiniMax-M2.7 is an interleaved-thinking model. Preserve
<think>...</think> blocks in conversation history when making multi-turn calls.
"""

import json
import os
import subprocess
import time

import aiohttp
import modal
import modal.experimental

# ----- Config -----
MODEL_NAME = "MiniMaxAI/MiniMax-M2.7"
MODEL_REVISION = None  # pin a specific commit hash in production

GPU_TYPE = "H200"
GPU_COUNT = 4  # floor for M2.7 FP8; 2xH200 may work for small KV cache budgets

REGION = "us"
PROXY_REGION = "us-east"

VLLM_PORT = 8000
MINUTES = 60

MIN_CONTAINERS = 0   # set to 1 for production to keep a warm replica
TARGET_INPUTS = 10   # concurrent requests per replica before scaling up

# Dummy-weights mode for iterating on server config without downloading 230GB.
USE_DUMMY_WEIGHTS = os.environ.get("APP_USE_DUMMY_WEIGHTS", "0").lower() in ("1", "true")

# ----- Volumes -----
HF_CACHE_VOL = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
HF_CACHE_PATH = "/root/.cache/huggingface"
VLLM_CACHE_VOL = modal.Volume.from_name("vllm-cache", create_if_missing=True)
VLLM_CACHE_PATH = "/root/.cache/vllm"


# ----- Image -----
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.19.0")
    .uv_pip_install("transformers==5.5.0")
    .uv_pip_install("huggingface-hub[hf_xet]==0.36.0")
    .env({
        "HF_HUB_CACHE": HF_CACHE_PATH,
        "HF_XET_HIGH_PERFORMANCE": "1",
        "APP_USE_DUMMY_WEIGHTS": str(int(USE_DUMMY_WEIGHTS)),
    })
)


def _download_weights(repo_id: str, revision: str | None = None) -> None:
    """Runs during image build to pre-populate the HF cache Volume."""
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo_id, revision=revision)


# Pre-download weights into the Volume at Image build time. This moves the
# ~230GB one-time download out of the cold-start path. Skipped when iterating
# on config with USE_DUMMY_WEIGHTS=1.
if not USE_DUMMY_WEIGHTS:
    vllm_image = vllm_image.run_function(
        _download_weights,
        volumes={HF_CACHE_PATH: HF_CACHE_VOL},
        secrets=[modal.Secret.from_name("huggingface-secret", create_if_missing=True)],
        kwargs={"repo_id": MODEL_NAME, "revision": MODEL_REVISION},
        timeout=60 * MINUTES,
    )


with vllm_image.imports():
    import requests


# ----- App -----
app = modal.App("minimax-m27-vllm-server", image=vllm_image)


def _start_server() -> subprocess.Popen:
    """Launch vLLM in a subprocess with tensor parallelism across GPU_COUNT GPUs."""
    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--served-model-name", MODEL_NAME, "llm",
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--tensor-parallel-size", str(GPU_COUNT),
        "--trust-remote-code",             # MiniMax ships custom modeling code
        "--max-model-len", "65536",        # M2.7 supports up to ~200k; dial to workload
        "--gpu-memory-utilization", "0.90",
        "--async-scheduling",
        "--no-enforce-eager",
        # MiniMax-specific parsers, per the M2.7 model card.
        "--enable-auto-tool-choice",
        "--reasoning-parser", "minimax",
        "--tool-call-parser", "minimax-m2",
    ]

    if MODEL_REVISION:
        cmd += ["--revision", MODEL_REVISION]

    if USE_DUMMY_WEIGHTS:
        cmd += ["--load-format", "dummy"]

    print("Starting vLLM server:")
    print(*cmd)
    return subprocess.Popen(" ".join(cmd), shell=True, start_new_session=True)


def _wait_ready(proc: subprocess.Popen, timeout: int = 25 * MINUTES) -> None:
    """Block until the server answers /health, or die if the subprocess exits."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rc = proc.poll()
        if rc is not None:
            raise subprocess.CalledProcessError(rc, cmd=proc.args)
        try:
            requests.get(f"http://127.0.0.1:{VLLM_PORT}/health", timeout=5).raise_for_status()
            return
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            time.sleep(5)
    raise TimeoutError(f"vLLM server not ready within {timeout}s")


@app.cls(
    gpu=f"{GPU_TYPE}:{GPU_COUNT}",
    scaledown_window=20 * MINUTES,
    timeout=30 * MINUTES,               # big boot budget for a 229B model
    volumes={HF_CACHE_PATH: HF_CACHE_VOL, VLLM_CACHE_PATH: VLLM_CACHE_VOL},
    region=REGION,
    min_containers=MIN_CONTAINERS,
    secrets=[modal.Secret.from_name("huggingface-secret", create_if_missing=True)],
    startup_timeout=30 * MINUTES,
)
@modal.experimental.http_server(
    port=VLLM_PORT,
    proxy_regions=[PROXY_REGION],
    exit_grace_period=25,
)
@modal.concurrent(target_inputs=TARGET_INPUTS)
class Server:
    @modal.enter()
    def start(self):
        self.proc = _start_server()
        _wait_ready(self.proc)

    @modal.exit()
    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()


@app.local_entrypoint()
async def test(content: str | None = None):
    """Healthcheck + single streamed completion against the deployed server.
    For modal.experimental.http_server, the URL comes from _experimental_get_flash_urls
    (see Modal's nemotron_inference.py for the canonical pattern)."""
    urls = await Server._experimental_get_flash_urls.aio()
    assert urls, "No flash URLs returned — is the server deployed?"
    url = urls[0]

    messages = [{"role": "user", "content": content or "Write a terse haiku about sawdust."}]
    payload = {
        "model": "llm",
        "messages": messages,
        "stream": True,
        "temperature": 1.0,   # recommended defaults from the M2.7 model card
        "top_p": 0.95,
    }
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

    async with aiohttp.ClientSession(base_url=url) as session:
        print(f"Healthcheck at {url}/health")
        async with session.get("/health", timeout=5 * MINUTES) as r:
            assert r.status == 200, f"Health check failed: {r.status}"
        print("Healthy.")

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
