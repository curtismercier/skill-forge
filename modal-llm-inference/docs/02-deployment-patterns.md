<!--
CANONICAL SOURCES — when in doubt, prefer these over the snippets below:
  • Runnable servers:  examples/basic-deployment/*.py       (tested, current APIs)
  • API gotchas:       references/modal-api-notes.md        (URL retrieval, auth, snapshots)
  • Verification:      docs/00-verification-playbook.md     (how to check if anything here is stale)
  • ERRATA:            ERRATA.md                            (known discrepancies awaiting fix)

Snippets here illustrate patterns. Real deployable code lives in examples/.
-->

# Deployment Patterns

## Purpose

Advanced deployment configurations including multi-replica setups, auto-scaling policies, container optimization, and production-ready patterns.

## Table of Contents

1. [Multi-Replica Deployment](#multi-replica-deployment)
2. [Auto-Scaling Configuration](#auto-scaling-configuration)
3. [Queue-Based Processing](#queue-based-processing)
4. [Container Optimization](#container-optimization)
5. [Network Configuration](#network-configuration)
6. [Production Checklist](#production-checklist)

## Multi-Replica Deployment

### Concurrent Function Calls

Modal automatically scales inference across multiple GPU replicas based on concurrent requests.

```python
import modal

app = modal.App("scaled-vllm")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.19.0", "openai")
)

@app.function(
    image=image,
    gpu="H200",
    max_concurrent_calls=10,      # Max concurrent requests per replica
    allow_concurrent_inputs=True,  # Allow parallel execution
    timeout=300,
)
def scaled_inference(prompt: str, model: str = "google/gemma-4-26B-A4B-it"):
    """Auto-scaled inference function."""

    from openai import OpenAI
    import os

    client = OpenAI(
        api_key=os.environ.get("HF_TOKEN", "dummy"),
        base_url="http://localhost:8000/v1"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    return {
        "response": response.choices[0].message.content,
        "usage": response.usage.to_dict(),
    }

@app.local_entrypoint()
def main():
    # Batch processing with auto-scaling
    prompts = [
        "What is machine learning?",
        "Explain neural networks",
        "Describe gradient descent",
        "What is backpropagation?",
        "Define deep learning",
    ]

    results = scaled_inference.map(prompts)

    for i, result in enumerate(results):
        print(f"Prompt {i+1}: {result}")
```

### Parallel Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor

@app.function(
    gpu="H200",
    max_concurrent_calls=10,
)
def parallel_inference(prompts: list[str]):
    """Process multiple prompts in parallel."""

    import subprocess
    import json

    # vLLM handles batching internally
    # This function receives a batch and returns results

    return [{"prompt": p, "processed": True} for p in prompts]

@app.local_entrypoint()
def main():
    # Generate large batch
    all_prompts = [f"Task {i}: Explain topic {i}" for i in range(100)]

    # Process with parallelism
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [parallel_inference.spawn(batch) for batch in chunks(all_prompts, 10)]
        results = [f.get() for f in futures]
```

## Auto-Scaling Configuration

### Manual Scaling with Cron

```python
import modal
from modal import Cron

app = modal.App("auto-scaled-vllm")

# Define scale configuration
SCALE_CONFIG = {
    "min_replicas": 0,
    "max_replicas": 4,
    "target_qps": 10,
}

@app.function(
    gpu="H200",
    allow_concurrent_inputs=True,
)
def inference_function(prompt: str):
    """Inference function with auto-scaling."""
    pass

@app.function(
    schedule=Cron("*/5 * * * *"),  # Every 5 minutes
)
def scale_monitor():
    """Monitor queue depth and adjust scaling."""

    import modal

    # Get current metrics
    # Adjust replica count based on queue depth
    # This is a simplified example

    print("Auto-scaling check completed")
```

### Web Server with Scaling

```python
import modal

app = modal.App("web-scaled-vllm")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("vllm==0.19.0", "fastapi", "uvicorn")
)

@app.function(
    image=image,
    gpu="H200",
    allow_concurrent_inputs=True,
    timeout=300,
)
@modal.web_server(port=8000, startup_timeout=600)
def web_server():
    """Web server with auto-scaling."""

    import subprocess
    import os

    subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--port", "8000",
        "--host", "0.0.0.0",
    ], env=os.environ)
```

## Queue-Based Processing

### Modal Queue Implementation

```python
import modal
import asyncio

app = modal.App("queued-vllm")

# Create persistent queue
queue = modal.Queue.from_name("vllm-inference-queue", create_if_missing=True)

RESULTS_QUEUE = modal.Queue.from_name("vllm-results-queue", create_if_missing=True)

@app.function(
    gpu="H200",
    timeout=600,
)
async def queue_processor():
    """Process inference requests from queue."""

    from openai import OpenAI
    import os
    import asyncio

    client = OpenAI(
        api_key=os.environ.get("HF_TOKEN", "dummy"),
        base_url="http://localhost:8000/v1"
    )

    while True:
        # Get request from queue
        request = queue.get(timeout=30)

        if request is None:
            await asyncio.sleep(1)
            continue

        prompt = request["prompt"]
        request_id = request["id"]

        try:
            # Process inference
            response = client.chat.completions.create(
                model="google/gemma-4-26B-A4B-it",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )

            # Store result
            RESULTS_QUEUE.put({
                "id": request_id,
                "result": response.choices[0].message.content,
                "status": "completed",
            })

        except Exception as e:
            RESULTS_QUEUE.put({
                "id": request_id,
                "error": str(e),
                "status": "failed",
            })

@app.local_entrypoint()
def main():
    """Submit requests to queue."""

    # Submit batch of requests
    for i in range(100):
        queue.put({
            "id": f"req-{i}",
            "prompt": f"Task {i}: Explain this concept",
        })

    print("Submitted 100 requests to queue")
```

### Request Batching

```python
@app.function(
    gpu="H200",
    max_batch_size=32,
    batch_timeout=1.0,
)
def batched_inference(prompts: list[str]):
    """Process batched requests for efficiency."""

    from openai import OpenAI
    import os

    client = OpenAI(
        api_key=os.environ.get("HF_TOKEN", "dummy"),
        base_url="http://localhost:8000/v1"
    )

    # vLLM handles batching internally
    # Process as streaming completion
    responses = []

    for prompt in prompts:
        response = client.chat.completions.create(
            model="google/gemma-4-26B-A4B-it",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        responses.append(response.choices[0].message.content)

    return responses
```

## Container Optimization

### Pre-Installed Dependencies

```python
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.19.0",
        "openai>=1.0.0",
        "huggingface_hub>=0.20.0",
        "torch>=2.1.0",
        "transformers>=4.36.0",
        "accelerate>=0.25.0",
    )
    .pip_install(
        "--index-url", "https://download.pytorch.org/whl/cu124",
        "torch",
    )
)
```

### Lazy Loading Pattern

```python
@app.function(
    image=image,
    gpu="H200",
    timeout=3600,
)
def lazy_loaded_inference():
    """Load dependencies only when needed."""

    # vLLM is heavy, load only when function is called
    # This keeps container image small

    import subprocess
    import os

    # Start server on first invocation
    process = subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--port", "8000",
    ])

    return {"status": "server_started", "pid": process.pid}
```

### Multi-Stage Build

```python
# Build optimized image in stages
FROM python:3.11-slim as builder

RUN pip install --user vllm==0.19.0

FROM python:3.11-slim

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

RUN pip install openai huggingface_hub
```

## Network Configuration

### Tailscale Integration

```python
app = modal.App("tailscale-vllm")

# Custom Tailscale setup
TAILSCALE_SCRIPT = """
#!/bin/bash
echo "Setting up Tailscale..."

# Authenticate with Tailscale
tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=modal-vllm-$MODAL_TASK_ID

echo "Tailscale connected"
echo "IP: $(tailscale ip -4)"
"""

@app.function(
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("tailscale-auth"),
    ],
)
def tailscale_server():
    """vLLM server with Tailscale networking."""

    import subprocess

    # Setup Tailscale
    subprocess.run(["bash", "-c", TAILSCALE_SCRIPT], check=True)

    # Start vLLM
    subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--port", "8000",
    ])
```

### Custom Domain with Tunnels

```python
@app.function(
    allow_concurrent_inputs=True,
)
@modal.web_server(port=8000)
def public_server():
    """Public-facing vLLM server via Modal Tunnels."""

    import subprocess
    import os

    subprocess.Popen([
        "vllm", "serve", "google/gemma-4-26B-A4B-it",
        "--port", "8000",
        "--host", "0.0.0.0",
    ], env=os.environ)
```

## Production Checklist

### Security

- [ ] API key authentication implemented
- [ ] Rate limiting configured
- [ ] Secrets stored in Modal dashboard
- [ ] TLS/SSL for public endpoints
- [ ] Input validation and sanitization
- [ ] Output filtering for sensitive data

### Reliability

- [ ] Health check endpoints configured
- [ ] Retry logic with exponential backoff
- [ ] Circuit breaker for downstream failures
- [ ] Graceful shutdown handling
- [ ] Dead letter queue for failed requests
- [ ] Alerting for error rates

### Performance

- [ ] Volume caching enabled for model weights
- [ ] GPU memory utilization optimized (>0.90)
- [ ] Batch processing for throughput
- [ ] Chunked prefill enabled
- [ ] Connection pooling configured
- [ ] Response streaming implemented

### Monitoring

- [ ] Request latency tracking
- [ ] Token throughput metrics
- [ ] GPU utilization monitoring
- [ ] Cost per request calculation
- [ ] Error rate dashboards
- [ ] Log aggregation configured

### Deployment

- [ ] CI/CD pipeline configured
- [ ] Blue-green or canary deployment
- [ ] Rollback procedure documented
- [ ] Configuration as code
- [ ] Infrastructure versioning
- [ ] Documentation updated

## Scaling Patterns Summary

| Pattern | Use Case | Complexity |
|---------|----------|------------|
| Concurrent Calls | Burst traffic | Low |
| Queue Processing | Backpressure | Medium |
| Web Server | HTTP API | Low |
| Tailscale | Private networking | Medium |
| Multi-Replica | High throughput | Medium |

## Next Steps

- Review [Client Integration](03-client-integration.md) for SDK usage
- Study [Cost Management](04-cost-management.md) for optimization
- Implement [TUI/Agent Patterns](05-tui-agent-patterns.md) for terminal agents
