# Scaling vLLM Endpoints — autoscaler parameters and patterns

<!--
SOURCE: https://modal.com/docs/guide/scale  (fetched 2026-04-16)
Refactored for LLM inference specifically. The upstream guide covers all
Modal Functions; this doc focuses on what matters for vLLM/SGLang servers.
-->

**The question this doc answers:** how many replicas should I run, and when does Modal scale them up or down?

## How Modal's autoscaler works

Every Modal Function has a pool of containers. Modal's autoscaler adjusts the pool size based on current load:

- **Input arrives, no warm container available** → autoscaler boots a new one
- **Container has been idle for `scaledown_window` seconds** → autoscaler shuts it down

That's the whole model. Four parameters on `@app.function` or `@app.cls` tune this:

| Parameter | Purpose | Common values for vLLM |
|---|---|---|
| `min_containers` | Floor on pool size even when idle. Default: 0 (scale to zero). | `0` for dev, `1-2` for production |
| `max_containers` | Ceiling on pool size. Default: None. | `10-50` to cap runaway costs |
| `buffer_containers` | Extra idle containers while Function is active. Default: 0. | `1-2` for bursty traffic |
| `scaledown_window` | Seconds a container stays idle before shutdown. Default: 60. Range: 2-1200. | `60` for dev, `600-900` for production |

```python
@app.function(
    gpu="H200",
    min_containers=1,          # always at least one warm
    max_containers=10,         # cap for cost control
    buffer_containers=2,       # pre-warm for bursts
    scaledown_window=900,      # 15 min idle before shutdown
)
def serve():
    ...
```

## Dynamic updates — change scaling without redeploying

Call `Function.update_autoscaler()` at runtime to adjust parameters without redeploy:

```python
import modal

serve = modal.Function.from_name("gemma-4-vllm-server", "serve")
serve.update_autoscaler(min_containers=3, buffer_containers=2)
```

This is powerful for time-of-day scaling. A common pattern: schedule a cron function that bumps `min_containers` during business hours and back down overnight.

```python
@app.function(schedule=modal.Cron("0 9 * * 1-5"))  # 9am weekdays
def scale_up_for_business_hours():
    serve = modal.Function.from_name("gemma-4-vllm-server", "serve")
    serve.update_autoscaler(min_containers=4)

@app.function(schedule=modal.Cron("0 19 * * 1-5"))  # 7pm weekdays
def scale_down_overnight():
    serve = modal.Function.from_name("gemma-4-vllm-server", "serve")
    serve.update_autoscaler(min_containers=0)
```

Settings revert to decorator values on next `modal deploy`. Dynamic updates are additive, not destructive.

## For vLLM specifically — what matters

### `@modal.concurrent` is NOT the autoscaler

`@modal.concurrent(max_inputs=N)` controls how many **inputs a single container handles simultaneously**. It's orthogonal to autoscaling. For vLLM:

- `max_inputs` should roughly match how many simultaneous requests your vLLM instance can handle without degrading token/s per request
- For 8B models on H200 with reasonable KV cache, `max_inputs=32` to `64` is typical
- Setting it too high causes request queuing inside vLLM; too low means you scale out replicas earlier than needed

The autoscaler only boots new containers when the *existing* containers are at their `max_inputs` ceiling.

### Scaling limits you'll hit

Modal enforces these per-Function limits:

- **2,000 pending inputs** (unassigned to containers)
- **25,000 total inputs** (running + pending)
- `.map()` processes **up to 1000 inputs concurrently** per invocation

For inference APIs (not batch), you won't hit these. For batch processing (e.g. `examples/batch-processing/batch_inference.py`), use `.spawn()` instead — it allows up to 1 million pending inputs.

## Parallel batch execution with `.map()` and `.starmap()`

When you have N independent inputs and want to fan out across containers:

```python
@app.function(gpu="H200", max_containers=20)
def score_prompt(prompt: str) -> float:
    # Each call gets a container, up to max_containers in parallel
    ...

@app.local_entrypoint()
def main():
    prompts = [...]  # list of prompts
    scores = list(score_prompt.map(prompts))
```

Modal runs up to `max_containers` copies in parallel. Each copy processes its input. Results come back ordered.

Pitfalls the upstream doc calls out:

- `score_prompt.map(prompts)` — this is **Modal's map method on the function object**. NOT Python's builtin `map()`.
- Python's builtin `map(score_prompt, prompts)` will execute sequentially, not in parallel. This is a common error.
- For multi-argument functions, use `.starmap()` with a list of tuples, or `.map()` with one iterator per argument.

For exception handling, pass `return_exceptions=True`:

```python
results = list(score_prompt.map(prompts, return_exceptions=True))
# results is a list of (score | Exception)
```

## Decision patterns

### Low-traffic chat app (< 100 requests/day)
```python
min_containers=0, scaledown_window=60, buffer_containers=0
```
Let it scale to zero. Cold starts are acceptable because they happen rarely.

### Internal team tool (steady business-hours traffic)
```python
min_containers=1 during hours (via cron), 0 overnight
scaledown_window=600
```
Dynamic update pattern from above. Cheap, responsive during work hours.

### Production SaaS endpoint (bursty, latency-sensitive)
```python
min_containers=2, buffer_containers=2, scaledown_window=900, max_containers=20
```
Always 2 warm replicas, plus 2 buffers ready to absorb bursts. Max of 20 caps cost.

### Batch scoring job (finite workload)
```python
max_containers=50
# and use .map() or .spawn()
```
No `min_containers` needed — the job runs once and terminates. `max_containers` controls parallelism.

## References for the next agent

- Upstream guide: https://modal.com/docs/guide/scale
- Container lifecycle methods: https://modal.com/docs/guide/lifecycle-functions
- Input concurrency (different from autoscaling): https://modal.com/docs/guide/concurrent-inputs
- Our cost estimator's `--amortize` mode models the scaling vs. cold-start trade-off
