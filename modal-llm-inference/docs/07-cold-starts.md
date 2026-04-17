# Cold Start Performance — a field guide

<!--
SOURCE: https://modal.com/docs/guide/cold-start  (fetched 2026-04-16)
Refactored from Modal's official guide. If anything here drifts, re-fetch and
compare. See docs/00-verification-playbook.md for the method.
-->

**The question this doc answers:** when a user hits my vLLM endpoint, why did it take 90 seconds, and what can I do about it?

## What a cold start actually is

Modal runs Functions in containers. If a container is already warm, your request is handled in milliseconds. If not, Modal spins up a new one — that's the **cold start**. Two separable costs:

1. **Queue time** — your input waits for a container to become ready
2. **Initialization work** — the container runs, but the first request hits un-cached state (weights not in memory, JIT not compiled, etc.)

These have different cures. Figure out which one is hurting you before picking a fix.

## Diagnosing which cost is hitting you

Look at Modal's dashboard for the Function:

- **Inputs spending time in "pending"** → queue time dominates → optimize container warmup or run more warm containers
- **First request to a new container is slow but subsequent ones are fast** → initialization dominates → move work earlier or use snapshots

Don't guess. The fix for each is different and often unrelated.

## Three levers for queue time

### 1. `scaledown_window` — how long idle containers stay warm

Default: 60 seconds. Range: 2 seconds to 20 minutes.

```python
@app.function(gpu="H200", scaledown_window=15 * 60)   # stay warm 15 min after last request
def serve():
    ...
```

Increases the chance a subsequent request lands on a warm container, at the cost of paying for idle GPU time. For vLLM on H200 that's ~$0.08/min — so a 15-minute scaledown window costs ~$1.20 of idle time per cooldown, but saves ~$1.90 of cold-start compute (90s cold start × $1.26/min). Net positive for moderately trafficked endpoints.

### 2. `min_containers` — always-on floor

```python
@app.function(gpu="H200", min_containers=1)
def serve():
    ...
```

Sets a floor so the function never scales to zero. For a chat app with steady traffic, this eliminates cold starts entirely for the first N users. For cost, see `scripts/estimate_cost.py --single --min-replicas 1`.

### 3. `buffer_containers` — overprovision while active

```python
@app.function(gpu="H200", buffer_containers=2)
def serve():
    ...
```

Keeps N extra warm containers ready while the function is handling traffic. Useful for bursty patterns where one new user predicts more users arriving soon.

**Trade-off rule:** all three of these increase cost. Use the estimator to model the break-even. For low-traffic workloads, `scaledown_window=900` + `min_containers=0` is usually right. For latency-sensitive production, `min_containers=1` + modest `buffer_containers` is worth the money.

## Four levers for initialization latency

### 1. Pre-download weights to a Volume

The biggest initialization cost for LLM serving is usually weight download. Our `gemma_server.py` and `minimax_server.py` examples already do this — weights are cached in `huggingface-cache` Volume and `vllm-cache` Volume. First-ever deploy downloads; every subsequent cold start reads from the Volume.

See `docs/09-model-weights.md` for the full pattern.

### 2. Move work into `@modal.enter` (not the function body)

Initialization inside `@modal.enter` runs during the warmup period, before the container is considered "warm." No request traffic lands on a container until `@modal.enter` finishes, so this just shifts the latency from user-visible request time to warmup time. Combine with `buffer_containers` to hide the warmup latency behind the buffer.

```python
@app.cls(gpu="H200", image=vllm_image)
class VllmServer:
    @modal.enter()
    def start(self):
        # Weight load + server start happen here, not on first request
        self.proc = subprocess.Popen(["vllm", "serve", MODEL_NAME, ...])
        _wait_ready(self.proc)
```

### 3. Memory snapshots (for JIT work, not weight loading)

Memory snapshots freeze the container state (CPU memory + optionally GPU memory) after warmup. Subsequent cold starts restore from snapshot instead of re-running JIT compilation.

**Critical constraint to remember:** snapshots do **not** speed up weight loading from storage. They help with JIT artifacts (CUDA graphs, torch.compile, Python imports). If your cold start is 90 seconds and 80 of those are weight download, snapshots will shave only ~10 seconds.

See `examples/basic-deployment/gemma_snapshot_server.py` for the runnable pattern. See `references/modal-api-notes.md` for all the caveats (multi-GPU incompatibility, 2-3 snapshot creations per GPU type, etc.).

Quantify the trade-off for your workload: `python scripts/estimate_cost.py --amortize --cold-starts-per-hour 2 --hours 720`.

### 4. Load large files concurrently

If `@modal.enter` has to load multiple models, don't do it serially. Modal's disk + network bandwidth is high, so parallel I/O wins. Relevant for multi-model pipelines (embedder + reranker + LLM), rare for single-model vLLM.

## The cold-start decision tree

```
Is cold-start latency a user-visible problem?
├── NO → Leave defaults. scaledown_window=60 is fine.
│
└── YES → Is it queue time or initialization?
    │
    ├── QUEUE TIME:
    │   └── Is traffic bursty?
    │       ├── YES → buffer_containers=2-4 + longer scaledown_window
    │       └── NO (steady) → min_containers=1
    │
    └── INITIALIZATION:
        └── Is most of the init time weight download?
            ├── YES → Pre-download to a Volume (our examples do this)
            │         Snapshots won't help significantly.
            │
            └── NO (JIT / imports dominate) → Memory snapshots
                └── But also: single-GPU only, alpha feature, see caveats
```

## What NOT to do

- Don't crank `min_containers` to "solve" cold starts you haven't profiled. You'll pay for idle GPU time without knowing if the user experience actually improved.
- Don't assume snapshots are a universal speedup. Read the caveats. Multi-GPU tensor-parallel (e.g. our MiniMax example) can't use them.
- Don't add `buffer_containers` without `scaledown_window` — buffers only help while the function is *active*, and scaling behavior matters more than you think for spiky traffic.

## References for the next agent

- Modal's own guide (re-fetch to check for updates): https://modal.com/docs/guide/cold-start
- Runnable example with snapshots: `examples/basic-deployment/gemma_snapshot_server.py`
- Quantitative amortization model: `scripts/estimate_cost.py --amortize ...`
- The autoscaler parameter reference: `docs/08-scaling.md`
