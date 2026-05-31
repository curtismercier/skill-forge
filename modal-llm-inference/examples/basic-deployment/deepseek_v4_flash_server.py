# ---
# pytest: false
# ---

# # Serve DeepSeek V4 Flash on Modal with SGLang

# DeepSeek V4 Flash (284B total / 13B active) is a near-frontier open-weight model
# with 93.5% LiveCodeBench and 80.6% SWE Verified. It uses FP4+FP8 mixed precision
# and is optimized for SGLang's `flashinfer_mxfp4` backend on Hopper GPUs.

# **GPU Requirement:** 4×H200 ($18.16/hr)
# **Engine:** SGLang (required for MXFP4 support)

# ## Prerequisites

# 1. Modal account (free tier includes $30/mo GPU credit)
# 2. HuggingFace token with DeepSeek V4 license accepted
#    (visit https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash and accept)
# 3. `pip install modal`

# ## Deploy

# ```bash
# modal deploy examples/basic-deployment/deepseek_v4_flash_server.py
# ```

# ## Test

# ```bash
# modal run examples/basic-deployment/deepseek_v4_flash_server.py
# ```

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

import aiohttp
import modal
import modal.experimental

here = Path(__file__).parent

# ## Set up the container image

# We use the `lmsysorg/sglang:latest` image which supports H200 (Hopper) GPUs.
# For Blackwell (B200), use `lmsysorg/sglang:deepseek-v4-blackwell` instead.

image = modal.Image.from_registry("lmsysorg/sglang:latest").entrypoint([])

# ### Load model weights

# We cache weights in a Modal Volume — this makes cold starts ~30-60 seconds
# instead of 20-40 minutes. The download happens once at deploy time.

hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)

image = image.env(
    {
        "HF_XET_HIGH_PERFORMANCE": "1",  # faster transfers
        "CUDA_VISIBLE_DEVICES": "0,1,2,3",
    }
)


def download_model(repo_id, revision=None):
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=repo_id, revision=revision)


REPO_ID = "deepseek-ai/DeepSeek-V4-Flash"

image = image.run_function(
    download_model,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    args=(REPO_ID,),
)

# ### Configure SGLang environment

image = image.env(
    {
        "SGLANG_ENABLE_SPEC_V2": "1",
        "SGLANG_ENABLE_THINKING": "1",
    }
)

# ### Write the SGLang config YAML

# This config is adapted from Modal's `config_deepseek_v4.yaml` for 4×H200.
# For Hopper (H200), we use `flashinfer_mxfp4` MoE runner which supports FP4
# weights on Hopper by decomposing MXFP4 matmuls.

default_config = """\
 # General Config
 host: 0.0.0.0
 log-level: info

 # Model Config
 tool-call-parser: deepseekv4
 reasoning-parser: deepseek-v4
 trust-remote-code: true

 # Memory
 mem-fraction-static: 0.82
 chunked-prefill-size: 4096

 # MoE — flashinfer_mxfp4 on Hopper (H200)
 moe-runner-backend: flashinfer_mxfp4

 # Observability
 enable-metrics: true
 collect-tokens-histogram: true

 # Batching
 max-running-requests: 32
 cuda-graph-max-bs: 32

 # SpecDec (EAGLE)
 speculative-algorithm: EAGLE
 speculative-num-steps: 3
 speculative-eagle-topk: 1
 speculative-num-draft-tokens: 4

 # Tuning
 disable-flashinfer-autotune: true
"""

local_config_path = here / "config_deepseek_v4_flash.yaml"

if modal.is_local():
    if not local_config_path.exists():
        local_config_path.write_text(default_config)
        print(f"Wrote config to {local_config_path}")

    image = image.add_local_file(local_config_path, "/root/config.yaml")

with image.imports():
    import sglang  # noqa — verify import works

# ## Configure infrastructure

app = modal.App("example-deepseek-v4-flash", image=image)

GPU_TYPE = "H200"
GPU_COUNT = 4  # 4×H200 required for V4 Flash

REGION = "us"
PROXY_REGIONS = ["us-east"]

MIN_CONTAINERS = 0  # Set to 1 for production
TARGET_INPUTS = 10

SGLANG_PORT = 8000
MINUTES = 60


@app.cls(
    image=image,
    gpu=f"{GPU_TYPE}:{GPU_COUNT}",
    scaledown_window=20 * MINUTES,
    timeout=3 * 60 * MINUTES,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    region=REGION,
    min_containers=MIN_CONTAINERS,
)
@modal.experimental.http_server(
    port=SGLANG_PORT,
    proxy_regions=PROXY_REGIONS,
    exit_grace_period=25,
)
@modal.concurrent(target_inputs=TARGET_INPUTS)
class Server:
    @modal.enter()
    def start(self):
        """Start SGLang server and wait for readiness."""
        self.proc = _start_server()
        wait_for_server_ready()

    @modal.exit()
    def stop(self):
        """Terminate SGLang server on container shutdown."""
        self.proc.terminate()
        self.proc.wait()


def _start_server() -> subprocess.Popen:
    """Launch SGLang server with DeepSeek V4 Flash config."""
    cmd = [
        "python",
        "-m",
        "sglang.launch_server",
        "--host",
        "0.0.0.0",
        "--port",
        str(SGLANG_PORT),
        "--model-path",
        REPO_ID,
        "--tp-size",
        str(GPU_COUNT),
        "--config",
        "/root/config.yaml",
    ]

    print("Starting SGLang server with:")
    print(" ".join(cmd))

    return subprocess.Popen(" ".join(cmd), shell=True, start_new_session=True)


def wait_for_server_ready():
    """Poll the health endpoint until the server responds."""
    import requests

    url = f"http://localhost:{SGLANG_PORT}/health"
    print(f"Waiting for server at {url}...")

    while True:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print("Server is ready!")
                return
        except requests.exceptions.RequestException:
            pass
        print(".", end="", flush=True)
        time.sleep(5)


# ## Test the server

# ```bash
# modal run examples/basic-deployment/deepseek_v4_flash_server.py
# ```


@app.local_entrypoint()
async def test(test_timeout=60 * MINUTES, content=None, twice=True):
    """Smoke test the deployed endpoint."""
    url = (await Server._experimental_get_flash_urls.aio())[0]
    print(f"Server URL: {url}")

    system_prompt = {
        "role": "system",
        "content": "You are a helpful AI assistant with expertise in coding and reasoning.",
    }
    if content is None:
        content = "Write a Python function that implements binary search."

    messages = [system_prompt, {"role": "user", "content": content}]

    print(f"Sending: {content}")
    await probe(url, messages, timeout=test_timeout)

    if twice:
        messages[1]["content"] = "Explain the difference between REST and GraphQL."
        print(f"Sending: {messages[1]['content']}")
        await probe(url, messages, timeout=10 * MINUTES)


async def probe(url, messages, timeout=20 * MINUTES):
    """Send a request with retry logic for startup delays."""
    deadline = time.time() + timeout
    async with aiohttp.ClientSession(base_url=url) as session:
        while time.time() < deadline:
            try:
                await _send_request_streaming(session, messages)
                return
            except asyncio.TimeoutError:
                await asyncio.sleep(1)
            except aiohttp.client_exceptions.ClientResponseError as e:
                if e.status == 503:
                    await asyncio.sleep(1)
                    continue
                raise e
    raise TimeoutError(f"No response within {timeout} seconds")


async def _send_request_streaming(
    session: aiohttp.ClientSession, messages: list, timeout: int | None = None
):
    """Stream response from the chat completions endpoint."""
    payload = {
        "messages": messages,
        "stream": True,
        "model": "deepseek-ai/DeepSeek-V4-Flash",
    }
    headers = {"Accept": "text/event-stream"}

    async with session.post(
        "/v1/chat/completions", json=payload, headers=headers, timeout=timeout
    ) as resp:
        resp.raise_for_status()
        async for raw in resp.content:
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (evt.get("choices") or [{}])[0].get("delta") or {}
            chunk = delta.get("content") or delta.get("reasoning_content")
            if chunk:
                print(chunk, end="", flush=True)
        print()
