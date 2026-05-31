<!--
NOTE: This document covers cost concepts, monitoring patterns, and optimization
strategies. For current GPU pricing and the cost estimator, see
`scripts/estimate_cost.py` and `references/modal-api-notes.md`. For post-hoc
tracking APIs (modal.billing, modal billing CLI, App tags, workspace budget cap),
run `python scripts/estimate_cost.py --tracking`.
-->

# Cost Management

## Purpose

Detailed cost analysis, monitoring, and optimization strategies for production Modal vLLM deployments with aggressive cost mitigation requirements.

## Table of Contents

1. [Cost Structure](#cost-structure)
2. [GPU Pricing](#gpu-pricing)
3. [Cost Calculation](#cost-calculation)
4. [Optimization Strategies](#optimization-strategies)
5. [Monitoring Setup](#monitoring-setup)
6. [Cost Mitigation Patterns](#cost-mitigation-patterns)

## Cost Structure

Modal pricing is based on GPU compute time with per-second billing granularity. Understanding the cost structure enables informed decisions about instance selection and optimization.

### Cost Components

| Component | Description | Billing |
|-----------|-------------|---------|
| GPU Compute | GPU usage time | Per second |
| CPU Compute | Container CPU time | Included |
| Memory | RAM allocation | Included |
| Storage | Volume storage | Per GB-hour |
| Network | Data transfer | Per GB |
| Cold Starts | Server initialization | Per second |

### Free Tier Limitations

| Resource | Free Tier | Paid Tier |
|----------|-----------|-----------|
| GPU Hours | Limited | Unlimited |
| Volume Storage | 500 MB | Unlimited |
| Secrets | 10 | Unlimited |
| Concurrent Functions | 1 | Multiple |

## GPU Pricing

### Current Pricing (verified April 2026)

Modal bills per-second, so the per-hour is derived. Source: `references/modal-api-notes.md` and https://modal.com/pricing. When in doubt re-verify.

| GPU Type     | VRAM   | $/sec     | $/hr   | Use Case |
|--------------|--------|-----------|--------|----------|
| B200         | 192 GB | 0.001736  | $6.25  | Frontier-scale inference |
| H200         | 141 GB | 0.001261  | $4.54  | Production Gemma 4 / MiniMax tensor-parallel |
| H100         | 80 GB  | 0.001097  | $3.95  | Medium-large LLMs |
| RTX_PRO_6000 | 48 GB  | 0.000842  | $3.03  | Cost-optimized prod |
| A100-80GB    | 80 GB  | 0.000694  | $2.50  | Medium models |
| A100-40GB    | 40 GB  | 0.000583  | $2.10  | Smaller models |
| L40S         | 48 GB  | 0.000542  | $1.95  | Development / small prod |
| A10          | 24 GB  | 0.000306  | $1.10  | Dev only |
| L4           | 24 GB  | 0.000222  | $0.80  | Dev / CPU-fallback tier |

Spot pricing isn't exposed as a separate tier on Modal the way it is on AWS — Modal's autoscaler handles preemption. See `references/modal-api-notes.md` for the current preemption model.

### Regional Pricing

Prices vary by region. Check Modal dashboard for current regional pricing.

| Region | H200 Multiplier | A100 Multiplier |
|--------|------------------|------------------|
| US East | 1.0x | 1.0x |
| US West | 1.05x | 1.05x |
| EU West | 1.10x | 1.10x |
| Asia | 1.15x | 1.15x |

## Cost Calculation

### Basic Cost Formula

```
Total Cost = GPU_Cost_Per_Hour × Hours_Used + Volume_Storage_GB × GB_Hour_Rate + Network_GB × GB_Rate
```

### Token Cost Calculation

```python
"""
Cost calculation utilities
File: scripts/estimate_cost.py
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class CostEstimate:
    """Cost estimation for vLLM inference."""
    gpu_type: str
    hours: float
    tokens_per_second: float
    cost_per_hour: float

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        return self.gpu_cost + self.token_cost

    @property
    def gpu_cost(self) -> float:
        """Calculate GPU compute cost."""
        return self.cost_per_hour * self.hours

    @property
    def token_cost(self) -> float:
        """Calculate implied token cost per million."""
        if self.tokens_per_second == 0:
            return float('inf')
        total_tokens = self.tokens_per_second * self.hours * 3600
        return (self.gpu_cost / total_tokens) * 1_000_000

    def summary(self) -> str:
        """Generate cost summary."""
        return f"""
GPU Cost Estimate
================
GPU Type: {self.gpu_type}
Hours Used: {self.hours:.2f}
Cost/Hour: ${self.cost_per_hour:.2f}
Total GPU Cost: ${self.gpu_cost:.4f}

Throughput: {self.tokens_per_second:.2f} tokens/sec
Tokens/Million Cost: ${self.token_cost:.4f}
Total Cost: ${self.total_cost:.4f}
"""


# Pricing lookup
GPU_PRICING = {
    "H200": 3.50,
    "A100-80GB": 2.30,
    "A100-40GB": 1.50,
    "L40S": 1.10,
}


def estimate_cost(
    gpu_type: str,
    hours: float,
    avg_tokens_per_request: int = 500,
    requests_per_hour: int = 100,
) -> CostEstimate:
    """Estimate cost for inference workload."""

    cost_per_hour = GPU_PRICING.get(gpu_type, 2.30)
    total_tokens_per_hour = avg_tokens_per_request * requests_per_hour
    tokens_per_second = total_tokens_per_hour / 3600

    return CostEstimate(
        gpu_type=gpu_type,
        hours=hours,
        tokens_per_second=tokens_per_second,
        cost_per_hour=cost_per_hour,
    )


# Example usage
if __name__ == "__main__":
    estimate = estimate_cost(
        gpu_type="H200",
        hours=1.0,
        avg_tokens_per_request=500,
        requests_per_hour=1000,
    )
    print(estimate.summary())
```

### Detailed Cost Calculator

```python
"""
Detailed cost calculator with optimization scenarios
File: scripts/detailed_cost_calc.py
"""

from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class InferenceWorkload:
    """Inference workload specification."""
    model: str
    avg_input_tokens: int
    avg_output_tokens: int
    requests_per_hour: int
    peak_requests_per_hour: int
    avg_response_time_seconds: float
    peak_response_time_seconds: float

@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""
    gpu_compute: float
    cold_start: float
    volume_storage: float
    network_transfer: float
    total: float

    def to_dict(self) -> dict:
        return {
            "gpu_compute": round(self.gpu_compute, 4),
            "cold_start": round(self.cold_start, 4),
            "volume_storage": round(self.volume_storage, 4),
            "network_transfer": round(self.network_transfer, 4),
            "total": round(self.total, 4),
        }


def calculate_cold_start_cost(
    cold_start_seconds: float,
    gpu_cost_per_second: float,
    requests_per_month: int,
    warm_pool_efficiency: float = 0.95,
) -> float:
    """Calculate cold start costs."""

    # Only cold start for requests not served by warm pool
    cold_requests = requests_per_month * (1 - warm_pool_efficiency)
    cold_start_hours = (cold_requests * cold_start_seconds) / 3600

    return cold_start_hours * gpu_cost_per_second


def calculate_gpu_cost(
    workload: InferenceWorkload,
    gpu_cost_per_hour: float,
    batch_size: int = 1,
) -> float:
    """Calculate GPU compute cost."""

    # Effective time per request with batching
    time_per_request = workload.avg_response_time_seconds / batch_size
    total_gpu_seconds = workload.requests_per_hour * time_per_request
    total_gpu_hours = total_gpu_seconds / 3600

    return total_gpu_hours * gpu_cost_per_hour


def optimize_batch_size(
    workload: InferenceWorkload,
    gpu_cost_per_hour: float,
) -> tuple[int, float]:
    """Find optimal batch size for minimum cost."""

    best_batch = 1
    best_cost = calculate_gpu_cost(workload, gpu_cost_per_hour, 1)

    for batch in range(2, 33):
        cost = calculate_gpu_cost(workload, gpu_cost_per_hour, batch)

        # Early exit if cost increases
        if cost > best_cost * 1.5:
            break

        if cost < best_cost:
            best_cost = cost
            best_batch = batch

    return best_batch, best_cost


# Example workload
if __name__ == "__main__":
    workload = InferenceWorkload(
        model="google/gemma-4-26B-A4B-it",
        avg_input_tokens=500,
        avg_output_tokens=500,
        requests_per_hour=1000,
        peak_requests_per_hour=5000,
        avg_response_time_seconds=2.0,
        peak_response_time_seconds=5.0,
    )

    h200_cost_per_hour = 3.50
    a100_cost_per_hour = 2.30

    # Calculate for H200
    gpu_cost = calculate_gpu_cost(workload, h200_cost_per_hour)
    print(f"H200 GPU Cost/hour: ${gpu_cost:.4f}")

    # Find optimal batch
    batch, cost = optimize_batch_size(workload, h200_cost_per_hour)
    print(f"Optimal batch size: {batch}, Cost: ${cost:.4f}")

    # Monthly estimate
    monthly_requests = workload.requests_per_hour * 24 * 30
    monthly_gpu_cost = gpu_cost * 24 * 30
    print(f"Monthly GPU Cost: ${monthly_gpu_cost:.2f}")
```

## Optimization Strategies

### Strategy 1: Volume Caching

Volume caching reduces cold start times from ~5 minutes to ~15 seconds, dramatically reducing idle GPU costs.

```python
"""
Volume caching for cost optimization
File: examples/cost-optimization/cached_server.py
"""

import modal

app = modal.App("cached-vllm")

# Create volume for model cache
volume = modal.Volume.from_name(
    "vllm-model-cache",
    create_if_missing=True
)

CACHE_DIR = "/volumed_cache"

@app.function(
    volumes={CACHE_DIR: volume},
    gpu="H200",
    timeout=3600,
)
def cached_vllm_server():
    """vLLM server with cached model weights.

    Cold start: ~15 seconds (cached) vs ~5 minutes (uncached)
    Cost savings: ~95% reduction in idle time costs
    """

    import subprocess
    import os

    cache_path = f"{CACHE_DIR}/models/google-gemma-4-26B"

    # Check if model is cached
    if not os.path.exists(cache_path):
        print("Cache miss - downloading model (first run)")
        os.makedirs(cache_path, exist_ok=True)
        # Model download happens here
    else:
        print("Cache hit - using cached model")

    # Start vLLM with cached weights
    subprocess.Popen([
        "vllm", "serve", cache_path,
        "--port", "8000",
    ])

    return {"status": "started", "cache_path": cache_path}
```

### Strategy 2: Container Idle Timeout

Configure appropriate idle timeout to avoid paying for unused warm containers.

```python
@app.function(
    gpu="H200",
    scaledown_window=300,  # Keep warm for 5 minutes after last request
    timeout=3600,
)
def server_with_idle_timeout():
    """Server that automatically scales down after idle period."""
    pass

# Idle timeout guidelines:
# - High traffic (continuous): 0 (never scale down)
# - Medium traffic (hourly): 300-600 seconds
# - Low traffic (daily): 1800-3600 seconds
# - Sporadic traffic: 60-120 seconds
```

### Strategy 3: Batch Processing

Batch multiple requests to maximize GPU utilization per second.

```python
"""
Batch processing for throughput optimization
File: examples/cost-optimization/batch_server.py
"""

@app.function(
    gpu="H200",
    max_batch_size=32,
    batch_timeout=0.1,  # 100ms max wait for batching
)
def batched_inference(prompts: list[str]):
    """Process batched requests for cost efficiency.

    Batch processing increases throughput by 5-10x
    Cost per token reduced by 80-90%
    """

    from openai import OpenAI

    client = OpenAI(
        api_key="dummy",
        base_url="http://localhost:8000/v1"
    )

    # Process entire batch
    # vLLM handles batching internally for efficiency

    return [client.chat.completions.create(
        model="google/gemma-4-26B-A4B-it",
        messages=[{"role": "user", "content": p}],
        max_tokens=512,
    ).choices[0].message.content for p in prompts]
```

### Strategy 4: GPU Downgrade for Development

Use smaller GPU instances for development and testing.

```python
"""
Environment-based GPU selection
File: examples/cost-optimization/env_gpu_selector.py
"""

import os
import modal

def get_gpu_config():
    """Select GPU based on environment."""

    env = os.environ.get("DEPLOYMENT_ENV", "development")

    configs = {
        "development": {
            "gpu": "L40S",
            "memory": 128 * 1024,
            "scaledown_window": 60,
        },
        "staging": {
            "gpu": "A100-40GB",
            "memory": 256 * 1024,
            "scaledown_window": 300,
        },
        "production": {
            "gpu": "H200",
            "memory": 512 * 1024,
            "scaledown_window": 600,
        },
    }

    return configs.get(env, configs["development"])

# Usage
gpu_config = get_gpu_config()

@app.function(**gpu_config)
def inference():
    """Inference with environment-appropriate GPU."""
    pass
```

## Monitoring Setup

### Cost Tracking Logger

```python
"""
Cost tracking with metrics logging
File: scripts/cost_tracker.py
"""

import modal
from datetime import datetime
import json

# Volume for cost metrics
cost_volume = modal.Volume.from_name("cost-metrics", create_if_missing=True)

METRICS_DIR = "/metrics"

@app.function(volumes={METRICS_DIR: cost_volume})
def log_inference_metrics(
    tokens_generated: int,
    gpu_seconds: float,
    request_id: str,
):
    """Log inference metrics for cost analysis."""

    import os
    from datetime import datetime

    # Calculate costs
    h200_rate_per_hour = 3.50
    h200_rate_per_second = h200_rate_per_hour / 3600

    cost_usd = gpu_seconds * h200_rate_per_second

    # Create log entry
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "tokens": tokens_generated,
        "gpu_seconds": gpu_seconds,
        "cost_usd": round(cost_usd, 6),
        "tokens_per_second": round(tokens_generated / gpu_seconds, 2) if gpu_seconds > 0 else 0,
    }

    # Write to volume
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = f"{METRICS_DIR}/inference_{date_str}.jsonl"

    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return log_entry


@app.function(volumes={METRICS_DIR: cost_volume})
def get_daily_cost_summary(date: str = None) -> dict:
    """Get cost summary for a given date."""

    import json

    if date is None:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    log_file = f"{METRICS_DIR}/inference_{date}.jsonl"

    try:
        with open(log_file, "r") as f:
            entries = [json.loads(line) for line in f]
    except FileNotFoundError:
        return {"date": date, "total_cost": 0, "total_tokens": 0, "requests": 0}

    total_cost = sum(e["cost_usd"] for e in entries)
    total_tokens = sum(e["tokens"] for e in entries)
    total_requests = len(entries)

    return {
        "date": date,
        "total_cost": round(total_cost, 4),
        "total_tokens": total_tokens,
        "requests": total_requests,
        "avg_cost_per_million_tokens": round(
            (total_cost / total_tokens) * 1_000_000, 4
        ) if total_tokens > 0 else 0,
    }
```

### Real-Time Dashboard

```python
"""
Real-time cost monitoring
File: scripts/realtime_monitor.py
"""

import modal
import time
from dataclasses import dataclass

@dataclass
class CostSnapshot:
    """Real-time cost snapshot."""
    timestamp: float
    gpu_seconds_used: float
    estimated_cost: float
    requests_processed: int

class RealtimeCostMonitor:
    """Monitor costs in real-time."""

    def __init__(self, gpu_rate_per_hour: float = 3.50):
        self.gpu_rate_per_hour = gpu_rate_per_hour
        self.gpu_rate_per_second = gpu_rate_per_hour / 3600
        self.start_time = time.time()
        self.requests = 0
        self.total_tokens = 0

    def record_request(self, tokens: int, gpu_time: float):
        """Record a completed request."""
        self.requests += 1
        self.total_tokens += tokens

    def get_snapshot(self) -> CostSnapshot:
        """Get current cost snapshot."""
        elapsed = time.time() - self.start_time
        cost = elapsed * self.gpu_rate_per_second

        return CostSnapshot(
            timestamp=time.time(),
            gpu_seconds_used=elapsed,
            estimated_cost=cost,
            requests_processed=self.requests,
        )

    def print_status(self):
        """Print current status."""
        snapshot = self.get_snapshot()

        print(f"""
Cost Monitor Status
===================
Uptime: {snapshot.gpu_seconds_used:.0f} seconds
Requests: {snapshot.requests_processed}
Tokens: {snapshot.total_tokens}
Current Cost: ${snapshot.estimated_cost:.4f}
Cost/Hour: ${self.gpu_rate_per_hour:.2f}
""")
```

## Cost Mitigation Patterns

### Pattern 1: Warm Pool with Queue

```python
"""
Warm pool with queue-based request handling
File: examples/sandbox-pool/warm_pool_manager.py
"""

import modal

app = modal.App("warm-pool-vllm")

# Configuration
POOL_SIZE = 3
POOL_TTL_SECONDS = 300
REQUEST_QUEUE = modal.Queue.from_name("vllm-requests", create_if_missing=True)

@app.function(
    gpu="H200",
    timeout=600,
)
def create_warm_sandbox():
    """Create pre-warmed vLLM sandbox."""

    sandbox = modal.Sandbox.create(
        image=modal.Image.debian_slim(python_version="3.12").uv_pip_install("vllm==0.19.0"),
        gpu="H200",
    )

    # Initialize vLLM
    sandbox.exec("vllm", "serve", "google/gemma-4-26B-A4B-it")

    return {"sandbox_id": sandbox.object_id, "status": "ready"}


@app.function(
    schedule=modal.Cron("*/5 * * * *"),  # Every 5 minutes
)
def maintain_pool():
    """Maintain warm pool size."""
    print(f"Pool maintenance: target={POOL_SIZE}")
    # Implement pool maintenance logic
```

### Pattern 2: Spot/Preemptible Instances

```python
# Use lower-cost GPU types for fault-tolerant workloads
@app.function(
    gpu="A100-80gb:spot",  # Spot instance (may be interrupted)
    allow_preemption=True,  # Handle preemption gracefully
)
def spot_inference():
    """Use spot instances for cost savings."""
    # Spot instances can be 60-70% cheaper
    # Implement checkpoint/resume for long-running tasks
```

### Pattern 3: Request Coalescing

```python
"""
Request coalescing for idle time reduction
File: examples/cost-optimization/coalescing.py
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

@dataclass
class CoalescedRequest:
    """Request that can be coalesced with others."""
    prompt: str
    future: asyncio.Future
    timestamp: float

class RequestCoalescer:
    """Coalesce incoming requests to batch processing."""

    def __init__(self, max_wait: float = 0.1, max_batch: int = 16):
        self.max_wait = max_wait
        self.max_batch = max_batch
        self.pending: list[CoalescedRequest] = []

    async def submit(self, prompt: str) -> str:
        """Submit request and wait for batched result."""

        future = asyncio.Future()
        request = CoalescedRequest(
            prompt=prompt,
            future=future,
            timestamp=time.time(),
        )

        self.pending.append(request)

        # Wait for batch processing
        try:
            return await asyncio.wait_for(
                future,
                timeout=30.0,
            )
        finally:
            self.pending.remove(request)

    async def process_batch(self):
        """Process accumulated requests in a batch."""

        if not self.pending:
            return

        # Wait for more requests or timeout
        start = time.time()
        while (
            len(self.pending) < self.max_batch
            and (time.time() - start) < self.max_wait
        ):
            await asyncio.sleep(0.01)

        batch = self.pending[:self.max_batch]
        prompts = [r.prompt for r in batch]

        # Process batch (actual vLLM call here)
        results = await self._process_batch_llm(prompts)

        # Resolve futures
        for request, result in zip(batch, results):
            request.future.set_result(result)

    async def _process_batch_llm(self, prompts: list[str]) -> list[str]:
        """Process batch through vLLM."""
        # Placeholder for actual vLLM call
        return [f"Response to: {p}" for p in prompts]
```

## Cost Summary Table

| Strategy | Cost Reduction | Complexity | Best For |
|----------|---------------|------------|----------|
| Volume Caching | 80-90% on cold starts | Low | All deployments |
| Idle Timeout | 40-60% | Low | Sporadic traffic |
| Batch Processing | 50-80% per token | Medium | High throughput |
| GPU Downgrade | 30-70% | Low | Development |
| Spot Instances | 60-70% | Medium | Fault-tolerant |
| Request Coalescing | 30-50% | High | Variable load |

## Self-Host vs API: The Honest Comparison

Before deploying any model on Modal, ask: **"Can I get this cheaper via an API?"**

For most workloads in 2026, the answer is **yes**. API providers like OpenRouter pool GPU capacity across thousands of customers and pass on economies of scale that a single-user Modal deployment cannot match.

### Real-World Cost Comparison (May 2026)

| Model | OpenRouter ($/M tok) | Modal GPU required | Modal cost/hr | Modal cost/M tok (50 tok/s) |
|---|---|---|---|---|
| DeepSeek V4 Flash | $0.10 / $0.20 | 4×H200 | $18.16 | $100.89 |
| DeepSeek V4 Pro | $0.43 / $0.87 | 8×B200 | $50.00 | $277.78 |
| Gemma 4 26B-A4B | est. $0.50-$1.00 | 1×H200 | $4.54 | $25.22 |
| Qwen3-32B | est. $0.30-$0.80 | 1×H200 | $4.54 | $25.22 |

**At typical throughput (50-100 tokens/s), Modal is 50-600× more expensive per token than API inference.**

### When Self-Hosting Actually Wins

| Scenario | Why | Example |
|---|---|---|
| **High concurrency (100+ sessions)** | Single GPU serves all requests; API charges per-token per-session | 100 simultaneous agents on 1×H200 vs 100× API calls |
| **Privacy/Data residency** | No data leaves your endpoint | Regulated codebases, proprietary data |
| **Fine-tuned models** | API providers don't run your custom weights | Domain-specific fine-tunes |
| **Predictable cost cap** | Fixed GPU cost regardless of usage | Budget-sensitive batch processing |
| **Off-peak batch** | Spin up GPU, process 50M tokens, tear down | Overnight batch jobs at $4.54/hr |

### The Breakeven Math

For a given GPU cost `C_gpu` per hour and an API price `P_api` per million tokens:

```
Breakeven throughput = C_gpu / P_api   (millions of tokens per hour)
```

| Model/GPU | GPU/hr | OpenRouter/M | Breakeven throughput | Realistic max throughput |
|---|---|---|---|---|
| DS V4 Flash (4×H200) | $18.16 | $0.14 | **129.7M tok/hr** | 2-5M tok/hr |
| Gemma 4 26B (1×H200) | $4.54 | $0.75 (est.) | **6.1M tok/hr** | 5-10M tok/hr |
| Qwen3-32B (1×H200) | $4.54 | $0.50 (est.) | **9.1M tok/hr** | 2-5M tok/hr |

**Only Gemma 4 26B comes close** to breaking even because its MoE architecture (4B active) pushes high throughput. Even then, it requires constant 90%+ GPU utilization.

### Decision Table

Use this when a user asks "should I deploy X on Modal or use an API?"

```
1. Does the model have an API equivalent at reasonable pricing?
   YES → Go to 2
   NO  → Self-host (only option)

2. Do you need 100+ concurrent sessions or data privacy?
   YES → Self-host may make sense — run the breakeven math
   NO  → Use the API (cheaper by 10-600×)

3. Is it a batch job that can complete in <1 GPU-hour?
   YES → Self-host is fine (small absolute cost)
   NO  → Use the API (sustained self-host burns money)
```

### The $30 Free Credits Play

Modal's $30/mo free credits change the math for **experimentation**. You can:

- Run Gemma 4 26B for **6.6 hours/month for free** ($4.54/hr)
- Run DS V4 Flash for **~1.6 hours/month for free** ($18.16/hr)
- Run Qwen3-32B for **6.6 hours/month for free**

This is genuinely useful for: testing a model before committing to API usage, running one-off batch jobs, or benchmarking throughput. **Don't deploy for sustained serving on free credits** — you'll exhaust them in days.

### The Right Takeaway

Self-hosting on Modal is not a cost-saving measure against 2026 API pricing. It's a **capability-enabling** measure: it lets you run models the API doesn't offer, control your data, and cap your costs. If you're doing it to save money on an existing API bill, the math almost never works.

Optimize accordingly: use Modal for what it's good at, and use APIs for what they're good at. Don't try to make Modal compete on per-token cost with a subsidized API — it can't win there.

## Next Steps

- Implement [TUI/Agent Patterns](05-tui-agent-patterns.md) for terminal agents
- Review [Deployment Patterns](02-deployment-patterns.md) for production setup
- Explore [Client Integration](03-client-integration.md) for SDK usage
