<!--
NOTE: This document covers concepts, architecture, and tradeoffs. For current
API specifics — vLLM version pinning, Modal decorator signatures, GPU pricing,
proxy auth, memory snapshots — see `references/modal-api-notes.md`. The code
snippets in this file illustrate patterns; copy-paste-ready runnable examples
live in `examples/basic-deployment/`.
-->

# Modal vLLM Inference Foundation

## Purpose

This document covers core concepts, architecture patterns, and essential configuration for deploying vLLM inference on Modal.com. It serves as the foundational layer for all subsequent skill levels.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Modal SDK Basics](#modal-sdk-basics)
3. [vLLM Configuration](#vllm-configuration)
4. [GPU Requirements](#gpu-requirements)
5. [Volume Caching](#volume-caching)
6. [Quick Start Example](#quick-start-example)
7. [Health Checks](#health-checks)
8. [Next Steps](#next-steps)

## Architecture Overview

Modal provides serverless GPU infrastructure for running vLLM inference. The deployment pattern uses a containerized approach where vLLM runs as an OpenAI-compatible API server accessible via HTTP.

### Key Components

| Component | Purpose | Configuration |
|-----------|---------|---------------|
| Modal App | Container orchestration | `modal.App()` |
| Container Image | Dependencies and runtime | `modal.Image` |
| GPU Allocation | Compute resources | `gpu="H200"` |
| Volume | Persistent model cache | `modal.Volume` |
| Secrets | Credential management | `modal.Secret` |

### Request Flow

```
Client Request
    ↓
Modal Web Server (port 8000)
    ↓
vLLM API Server (subprocess)
    ↓
GPU (H200/A100)
    ↓
Model Weights (cached on Volume)
```

## Modal SDK Basics

### Application Definition

```python
import modal

# Initialize application
app = modal.App("vllm-inference")

# Define container image
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.19.0", "openai")
)
```

### Function Decorators

| Decorator | Purpose | Key Parameters |
|-----------|---------|----------------|
| `@app.function()` | Base function | `gpu`, `timeout`, `memory` |
| `@app.local_entrypoint()` | CLI entry point | N/A |
| `@modal.web_server()` | HTTP server | `port`, `startup_timeout` |

### GPU Configuration

```python
@app.function(
    gpu="H200",           # GPU type
    memory=512 * 1024,     # 512 GB RAM
    timeout=3600,          # 1 hour max
    scaledown_window=300,  # Keep warm for 5 min
)
def inference_function():
    pass
```

**Available GPU Types:**

| GPU | VRAM | Best For | Cost Factor |
|-----|------|----------|-------------|
| H200 | 141 GB | Large models (Gemma 4) | 1.0x |
| A100-80GB | 80 GB | Medium-large models | 0.65x |
| A100-40GB | 40 GB | Smaller models | 0.40x |
| L40S | 48 GB | Testing/development | 0.30x |

## vLLM Configuration

### Basic Server Startup

```python
import subprocess
import os

def start_vllm_server():
    """Start vLLM as OpenAI-compatible API server."""

    model_id = "google/gemma-4-26B-A4B-it"
    hf_token = os.environ.get("HF_TOKEN", "")

    vllm_args = [
        "vllm", "serve", model_id,
        "--tokenizer", model_id,
        "--dtype", "half",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.95",
        "--port", "8000",
    ]

    env = {**os.environ, "HF_TOKEN": hf_token}
    process = subprocess.Popen(vllm_args, env=env)

    return process.pid
```

### Key vLLM Parameters

| Parameter | Default | Recommended | Purpose |
|-----------|---------|-------------|---------|
| `--dtype` | float16 | half | Model precision |
| `--max-model-len` | 4096 | 8192-16384 | Context window |
| `--gpu-memory-utilization` | 0.9 | 0.95 | KV cache size |
| `--tensor-parallel-size` | 1 | 1-8 | Multi-GPU scaling |
| `--enforce-eager` | False | False | Enable CUDA graphs |

### Advanced Configuration

```python
ADVANCED_VLLM_ARGS = [
    "--enable-chunked-prefill",      # Better throughput
    "--max-num-batched-tokens", "32768",  # Batch size
    "--prefill-chunk-size", "4096",  # Prefill chunking
    "--max-num-seqs", "256",         # Max concurrent sequences
    "--block-size", "16",             # KV cache block size
]
```

## GPU Requirements

### Gemma 4 Specifications

| Specification | Value | Notes |
|--------------|-------|-------|
| Total Parameters | 26B | Full model size |
| Active Parameters | 4B | Per-token processing |
| Model Type | Dense, Decoder-only | |
| Context Length | 32K | Maximum sequence |
| Multimodal | Yes | Images, video, audio |

### Memory Calculation

```
Required VRAM = (Model Parameters × Bytes per Parameter) + KV Cache

Example for Gemma 4:
- Model: 26B × 2 bytes (half precision) = 52 GB
- KV Cache: ~40 GB (for 8K context)
- Safety Margin: 5 GB
- Total: ~97 GB (requires H200 or multi-A100)
```

### Minimum Requirements

| Configuration | GPU | VRAM | Notes |
|--------------|-----|------|-------|
| Production | H200 | 141 GB | Optimal performance |
| Recommended | A100-80GB | 80 GB | May require reduced batch |
| Minimum | A100-40GB | 40 GB | Reduced context, batch |

## Volume Caching

Volume caching is critical for reducing cold start times from 5-10 minutes to approximately 10-15 seconds.

### How Caching Works

1. First run: Download model weights from HuggingFace (~5-30 min)
2. Cache weights to Modal Volume
3. Subsequent runs: Load weights from Volume cache
4. JIT compilation artifacts also cached for faster startup

### Cache Configuration

```python
import modal

# Create or access volume
volume = modal.Volume.from_name(
    "vllm-model-cache",
    create_if_missing=True
)

CACHE_DIR = "/volumed_cache"

@app.function(
    volumes={CACHE_DIR: volume},
    gpu="H200",
)
def cached_vllm_startup():
    """Start vLLM with cached model weights."""

    import os
    cache_path = f"{CACHE_DIR}/models/google-gemma-4-26B"

    # Check if model already cached
    if not os.path.exists(cache_path):
        os.makedirs(cache_path, exist_ok=True)
        # Download weights (one-time)
        subprocess.run([
            "python", "-m", "huggingface_hub.commands.huggingface_hub_download",
            "--repo_id", "google/gemma-4-26B-A4B-it",
            "--local-dir", cache_path,
        ])

    # vLLM will find cached weights
    # Cold start: ~10-15 seconds (cached)
    # Cold start: ~5-10 minutes (uncached)
```

### Cache Management

```bash
# View volume contents
modal volume ls vllm-model-cache

# Clear specific cache
modal volume rm vllm-model-cache/models/google-gemma-4-26B

# Clear entire cache
modal volume rm vllm-model-cache
```

## Quick Start Example

### Complete Basic Server

```python
"""
Basic Gemma 4 vLLM Server on Modal
File: examples/basic-deployment/gemma_server.py
"""

import modal
import subprocess
import os
import time

app = modal.App("gemma-4-vllm-server")

# Container image with vLLM
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.19.0", "openai", "huggingface_hub")
)

@app.function(
    image=image,
    gpu="H200",
    memory=512 * 1024,
    timeout=3600,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def vllm_server():
    """Start vLLM server as background process."""

    process = subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--dtype", "half",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.95",
        "--port", "8000",
    ], env={**os.environ})

    # Wait for initialization
    time.sleep(60)

    return {
        "status": "running",
        "pid": process.pid,
        "endpoint": "http://localhost:8000/v1"
    }

@app.local_entrypoint()
def main():
    result = vllm_server.remote()
    print(f"vLLM Server: {result}")
    print("API Documentation: http://localhost:8000/docs")
```

### Test Client

```python
"""
Test client for vLLM server
File: examples/basic-deployment/test_client.py
"""

from openai import OpenAI

client = OpenAI(
    api_key="dummy",  # Not used with vLLM
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="google/gemma-4-26B-A4B-it",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing in simple terms."}
    ],
    max_tokens=512,
    temperature=0.7,
)

print(response.choices[0].message.content)
```

### Deployment Commands

```bash
# Run locally for testing
modal run examples/basic-deployment/gemma_server.py

# Deploy to production
modal deploy examples/basic-deployment/gemma_server.py

# View logs
modal logs gemma-4-vllm-server

# Check status
modal app status gemma-4-vllm-server
```

## Health Checks

### Health Endpoint

vLLM provides a built-in health check at `/health`:

```python
import requests

def check_health(endpoint: str) -> bool:
    """Check if vLLM server is healthy."""
    try:
        response = requests.get(f"{endpoint}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False
```

### Startup Verification

```python
@app.function(...)
def verify_startup():
    """Verify vLLM server is fully initialized."""

    import requests
    import time

    max_retries = 30
    retry_delay = 5

    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("vLLM server is healthy!")
                return True
        except requests.RequestException:
            pass

        print(f"Waiting for startup... ({i+1}/{max_retries})")
        time.sleep(retry_delay)

    raise RuntimeError("vLLM server failed to start")
```

### Readiness Check Pattern

```python
@app.function(
    timeout=3600,
    scaledown_window=300,
)
def ready_server():
    """Start server and verify readiness."""

    import subprocess
    import requests
    import time

    # Start vLLM
    process = subprocess.Popen([...])

    # Wait and verify
    time.sleep(30)  # Allow initialization

    # Try health check
    for _ in range(10):
        try:
            r = requests.get("http://localhost:8000/health", timeout=2)
            if r.status_code == 200:
                return {"status": "ready"}
        except:
            time.sleep(5)

    return {"status": "starting", "pid": process.pid}
```

## Next Steps

After completing this foundation document:

1. Review [Deployment Patterns](02-deployment-patterns.md) for advanced configurations
2. Explore [Client Integration](03-client-integration.md) for SDK usage
3. Study [Cost Management](04-cost-management.md) for optimization
4. Implement [TUI/Agent Patterns](05-tui-agent-patterns.md) for terminal agents

## Key Takeaways

- Modal provides serverless GPU infrastructure with per-second billing
- vLLM runs as OpenAI-compatible API server (port 8000)
- Volume caching reduces cold starts from minutes to ~15 seconds
- H200 is optimal for Gemma 4; A100-80GB is cost-effective alternative
- Health checks ensure reliable server initialization
- Secrets provide secure credential management

## Reference Commands

```bash
# Volume management
modal volume create vllm-model-cache
modal volume ls
modal volume inspect vllm-model-cache

# Secret management
modal secret create huggingface-secret HF_TOKEN=your_token
modal secret ls

# Application management
modal app list
modal app status <app-name>
modal logs <app-name>

# Function invocation
modal run <file.py>::<app>.<function>
modal deploy <file.py>
```
