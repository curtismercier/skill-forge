"""
Gemma 4 (26B-A4B-it) vLLM Server on Modal — WITH MEMORY SNAPSHOTS.
File: examples/basic-deployment/gemma_snapshot_server.py

Same model as gemma_server.py, but with Modal's memory-snapshot lifecycle
for ~10x faster cold starts. Adapted from:
https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/ministral3_inference.py

When to use THIS vs gemma_server.py:
  * Snapshot version: production traffic that frequently scales from zero,
    need cold starts measured in seconds (not tens of seconds).
    Cost: more complex lifecycle, requires vLLM Sleep Mode support,
    larger state artifacts stored on Modal's side.
  * Simple version: development, iterating on config, low traffic where
    cold-start latency isn't on the critical path.

Key additions vs gemma_server.py:
  1. `@app.cls` (not `@app.function`) with `enable_memory_snapshot=True`
     and `experimental_options={"enable_gpu_snapshot": True}`
  2. `@modal.enter(snap=True)` method that starts vLLM, warms it up,
     then puts it to sleep — all before the snapshot is taken.
  3. `@modal.enter(snap=False)` method that wakes vLLM after snapshot
     restore on each new container.
  4. `--enable-sleep-mode` flag on vLLM + `VLLM_SERVER_DEV_MODE=1` env
  5. Explicit `--max-num-seqs` and `--max-num-batched-tokens` to keep
     KV cache size predictable (snapshots don't love surprises).

Usage:
    modal setup
    modal secret create huggingface-secret HF_TOKEN=hf_xxx
    modal deploy examples/basic-deployment/gemma_snapshot_server.py

After deploy, first-ever boot still does the full build + warm-up (slow).
Subsequent cold starts restore from snapshot — measured in seconds.
"""

import socket
import subprocess

import aiohttp
import modal

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("gemma-4-vllm-snapshot")

# ----- Image -----
# Key addition: VLLM_SERVER_DEV_MODE lets us use vLLM's /sleep + /wake_up endpoints,
# and TORCHINDUCTOR_COMPILE_THREADS=1 improves compatibility with GPU snapshots.
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.19.0")
    .uv_pip_install("transformers==5.5.0")
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VLLM_SERVER_DEV_MODE": "1",           # unlocks /sleep and /wake_up
            "TORCHINDUCTOR_COMPILE_THREADS": "1",  # better snapshot reproducibility
        }
    )
)

MODEL_NAME = "google/gemma-4-26B-A4B-it"
MODEL_REVISION = "47b6801b24d15ff9bcd8c96dfaea0be9ed3a0301"

hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

N_GPU = 1


with vllm_image.imports():
    import requests


def _wait_ready(proc: subprocess.Popen) -> None:
    """Busy-poll the server until it accepts TCP connections. Dies if the subprocess exits."""
    while True:
        try:
            socket.create_connection(("localhost", VLLM_PORT), timeout=1).close()
            return
        except OSError:
            if proc.poll() is not None:
                raise RuntimeError(f"vLLM exited with {proc.returncode}")


def _warmup() -> None:
    """Fire a few real requests to capture JIT artifacts (CUDA graphs, torch.compile) in the snapshot."""
    payload = {
        "model": "llm",
        "messages": [{"role": "user", "content": "Who are you?"}],
        "max_tokens": 16,
    }
    for _ in range(3):
        requests.post(
            f"http://localhost:{VLLM_PORT}/v1/chat/completions",
            json=payload,
            timeout=300,
        ).raise_for_status()


def _sleep() -> None:
    """Put vLLM to sleep: weights offloaded to CPU, KV cache cleared. Ready for snapshot."""
    requests.post(f"http://localhost:{VLLM_PORT}/sleep?level=1").raise_for_status()


def _wake() -> None:
    """Wake vLLM back up after snapshot restore."""
    requests.post(f"http://localhost:{VLLM_PORT}/wake_up").raise_for_status()


@app.cls(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=15 * MINUTES,              # first build takes longer
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    enable_memory_snapshot=True,        # THE key flag
    experimental_options={"enable_gpu_snapshot": True},
)
@modal.concurrent(max_inputs=32)        # smaller than gemma_server.py — see --max-num-seqs below
class VllmServer:
    @modal.enter(snap=True)
    def start(self):
        """Runs ONCE per image build, BEFORE the snapshot is taken.
        Starts vLLM, warms it up, puts it to sleep — all that state gets frozen."""
        cmd = [
            "vllm", "serve", MODEL_NAME,
            "--revision", MODEL_REVISION,
            "--served-model-name", MODEL_NAME, "llm",
            "--host", "0.0.0.0",
            "--port", str(VLLM_PORT),
            "--uvicorn-log-level=info",
            "--tensor-parallel-size", str(N_GPU),
            "--gpu-memory-utilization", "0.90",
            # Gemma 4 parsers
            "--enable-auto-tool-choice",
            "--reasoning-parser", "gemma4",
            "--tool-call-parser", "gemma4",
            # Snapshot-specific: enable sleep mode + predictable KV footprint
            "--enable-sleep-mode",
            "--max-num-seqs", "2",
            "--max-model-len", "12288",
            "--max-num-batched-tokens", "12288",
        ]

        print("Launching vLLM for snapshot:", *cmd)
        self.vllm_proc = subprocess.Popen(cmd)

        _wait_ready(self.vllm_proc)
        _warmup()
        _sleep()

    @modal.enter(snap=False)
    def wake(self):
        """Runs on EVERY container start AFTER snapshot restore. Just wakes vLLM."""
        _wake()
        _wait_ready(self.vllm_proc)

    @modal.web_server(port=VLLM_PORT, startup_timeout=10 * MINUTES)
    def serve(self):
        """The @modal.web_server decorator handles the HTTP exposure.
        The actual server is already running from start() / wake()."""
        pass

    @modal.exit()
    def stop(self):
        self.vllm_proc.terminate()


@app.local_entrypoint()
async def test(content: str | None = None):
    """Healthcheck + streamed completion. Note the URL retrieval pattern —
    `VllmServer().serve.get_web_url()` is sync because @modal.web_server
    on a Cls method exposes it as a regular (non-experimental) web URL."""
    url = VllmServer().serve.get_web_url()
    print(f"Endpoint: {url}")

    messages = [
        {"role": "system", "content": "You are a terse, precise assistant."},
        {"role": "user",   "content": content or "What's the capital of France?"},
    ]
    payload = {"model": "llm", "messages": messages, "max_tokens": 64}
    headers = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession(base_url=url) as session:
        async with session.get("/health", timeout=2 * MINUTES) as r:
            assert r.status == 200
        async with session.post("/v1/chat/completions", json=payload, headers=headers) as r:
            data = await r.json()
            print(data["choices"][0]["message"]["content"])
