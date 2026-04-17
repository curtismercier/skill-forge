# Modal API & Ecosystem Reference

Ground-truth notes verified against Modal's actual source. When anything in the skill says "do X", the authority for why is here.

**Last verified:** April 2026. Versions and APIs change — check the source links if in doubt.

## Canonical Modal resources (official)

### Documentation and LLM guidance
- **[Modal docs](https://modal.com/docs)** — the canonical, living reference
- **[Modal's `llms.txt`](https://modal.com/llms.txt)** — Modal publishes this specifically for LLM agents. Hit it when reasoning about Modal and you lack certainty
- **[Developing with LLMs guide](https://modal.com/docs/guide/developing-with-llms)** — Modal's own rules and patterns they recommend for agent code
- **[High-performance LLM inference guide](https://modal.com/docs/guide/high-performance-llm-inference)** — what to optimize, when, and the tradeoffs
- **[LLM Almanac](https://modal.com/llm-almanac)** — Modal's benchmarks of open-weight models on their platform (GLM, DeepSeek, Qwen, Llama, etc.)
- **[Model Library](https://modal.com/library)** — their curated list of deployable models
- **[GPU Glossary](https://modal.com/gpu-glossary)** — clear explanations of VRAM, tensor parallelism, KV cache, etc.

### Public GitHub repos (77 total, as of April 2026)
Organization: https://github.com/modal-labs

Highest-leverage for this skill:

| Repo | What it is | Why it matters |
|---|---|---|
| [modal-examples](https://github.com/modal-labs/modal-examples) | Reference code for every Modal feature | The `vllm_inference.py` and `very_large_models.py` files in `06_gpu_and_ml/llm-serving/` are the canonical patterns this skill follows |
| [modal-client](https://github.com/modal-labs/modal-client) | The Python/JS/Go SDKs | When you need the actual API shape — e.g. `get_web_url` is an async method on Functions only |
| [multinode-training-guide](https://github.com/modal-labs/multinode-training-guide) | Distributed training patterns | Useful reference when scaling beyond single-node inference |
| [awesome-modal](https://github.com/modal-labs/awesome-modal) | Curated community projects | Good for finding patterns others have shipped |
| [sglang fork](https://github.com/modal-labs/sglang) | Modal's SGLang fork | SGLang is preferred over vLLM for some large models (see `very_large_models.py`) |
| synchronicity, mountpoint-s3, gvisor fork | Infrastructure libraries | Usually not relevant for inference; here for completeness |

The rest of the 77 repos are language bindings, infrastructure libraries, internal tools, and demos. When stuck, check `modal-examples` first — it's continuously tested against the current Modal API.

## Verified API specifics (the stuff I got wrong before)

### Image base
- **Use:** `modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12").entrypoint([])`
- **Don't use:** `modal.Image.debian_slim()` for vLLM work. It technically installs, but the canonical example uses the CUDA-devel base for a reason — you get the full CUDA toolkit, which some kernels at build time expect.
- **Definitely don't use:** `modal.Image.debian_windows()` — not a thing. If you see this in code, it's LLM-hallucinated.

### Install method
- `.uv_pip_install(...)` — preferred, fast
- `.pip_install(...)` — works, slower, some quirks
- For vLLM specifically: `uv_pip_install("vllm==0.19.0")` then separately `uv_pip_install("transformers==5.5.0")` — splitting these is intentional and needed for Gemma 4 as of vLLM 0.19.

### Weight download env vars
- **Correct (current):** `HF_XET_HIGH_PERFORMANCE=1` — enables HuggingFace's Xet backend
- **Older:** `HF_HUB_ENABLE_HF_TRANSFER=1` — still works but Xet is faster on large weights
- Set `HF_HUB_CACHE=/root/.cache/huggingface` when you're mounting a Volume there

### Scaledown / idle timeout
- **Correct (Modal v1):** `scaledown_window=N` in seconds
- **Deprecated:** `container_idle_timeout=N` — this name was renamed. If you see it in old code, swap.

### Secret naming convention
- Modal's own examples consistently use **`huggingface-secret`** (not `huggingface-token`)
- Inside the secret, the env var should be `HF_TOKEN=hf_xxx`
- Create with: `modal secret create huggingface-secret HF_TOKEN=hf_xxx`
- Reference with: `modal.Secret.from_name("huggingface-secret")`

### Web URL retrieval (differs by decorator AND entrypoint style)

This trips people up. The URL-retrieval method depends on two things: which decorator you used, and whether your `local_entrypoint` is async. Verified against `modal-examples/06_gpu_and_ml/llm-serving/*.py`:

| Decorator | Sync entrypoint | Async entrypoint |
|---|---|---|
| `@modal.web_server(...)` on a function | `serve.get_web_url()` | `await serve.get_web_url.aio()` |
| `@modal.web_server(...)` on a Cls method | `VllmServer().serve.get_web_url()` | same, or `.aio()` form |
| `@modal.experimental.http_server(...)` on a Cls | `Server._experimental_get_flash_urls()[0]` | `(await Server._experimental_get_flash_urls.aio())[0]` |

Key things to remember:
- `_experimental_get_flash_urls` returns a **list** — always index `[0]` for the primary URL
- `get_web_url` returns a **single string**
- The `.aio()` form is required if and only if you're calling it from an `async` context
- These are methods on Function/Cls objects, not module-level attributes

Source: verify by `grep "get_web_url\|get_flash_urls" modal-examples/06_gpu_and_ml/llm-serving/*.py` — 18+ examples cover every combination.

### Proxy authentication (Modal's first-class endpoint protection)

Modal rejects unauthorized requests at the infrastructure level, **before** any container spins up — so unauthorized requests cost you nothing.

Add `requires_proxy_auth=True` to any of these decorators:
- `@modal.web_server(port=..., requires_proxy_auth=True)` — for vLLM/SGLang/subprocess servers (our case)
- `@modal.fastapi_endpoint(requires_proxy_auth=True)` — for simple Python handlers
- `@modal.asgi_app(requires_proxy_auth=True)` — for FastAPI/Starlette apps
- `@modal.wsgi_app(requires_proxy_auth=True)` — for Flask/Django apps

Verified in `modal-client/py/modal/_partial_function.py` — 8 occurrences of `requires_proxy_auth` across 4 decorator signatures.

**Client flow:**
1. Create a Proxy Auth Token pair at `https://modal.com/settings/proxy-auth-tokens` — you get a Token ID (`wk-...`) and Token Secret (`ws-...`). Save the secret immediately; it's shown only once.
2. Every request must include both headers: `Modal-Key: <token-id>` and `Modal-Secret: <token-secret>`.
3. Modal's dashboard decorates secured endpoint URLs with a 🔑 emoji.

**OpenAI SDK with proxy auth:** pass the headers via `default_headers`:
```python
client = OpenAI(
    api_key="dummy",
    base_url="https://<workspace>--<app>-<fn>.modal.run/v1",
    default_headers={
        "Modal-Key": os.environ["MODAL_TOKEN_ID"],
        "Modal-Secret": os.environ["MODAL_TOKEN_SECRET"],
    },
)
```

**Curl:**
```bash
curl -H "Modal-Key: $MODAL_TOKEN_ID" -H "Modal-Secret: $MODAL_TOKEN_SECRET" \
     https://<workspace>--<app>-<fn>.modal.run/health
```

See `examples/basic-deployment/gemma_secured_server.py` for a runnable vLLM example.
Reference: https://modal.com/docs/guide/webhook-proxy-auth

### GPU memory snapshots — what they actually do

Verified against https://modal.com/docs/guide/memory-snapshots (pulled April 2026).

**What snapshots DO:**
- 3-10× cold-start speedup (Modal's own published measurement, not marketing)
- Skip JIT compilation + Python import phase on container wake
- Capture CUDA graphs, torch.compile artifacts, and CPU memory state

**What snapshots DO NOT do:**
- They **do not speed up model weight loading** from storage — snapshots use the same distributed FS that Volumes use
- If your cold start is dominated by weight download, snapshots won't help and may even add overhead

**Incompatibilities (GPU snapshots are alpha):**
- Generally **incompatible with multi-GPU tensor-parallel setups** — our MiniMax example (4×H200) cannot use GPU snapshots today
- Incompatible with non-CUDA GPU code
- Can conflict with `torch.compile` — mitigation is `TORCHINDUCTOR_COMPILE_THREADS=1`
- Watch for `torch.cuda.is_available()` / `torch.cuda.get_device_capability()` during import: they initialize CUDA as zero-device, breaking snapshots. `xformers` is known to do this.

**Billing side-effects to know about:**
- Modal needs 2-3 snapshots per GPU type to fully cover the worker pool (CPU-only needs ~6)
- First few invocations of a new Function create snapshots — slower + billed as normal startup
- Redeploying with a new GPU type or any code change invalidates existing snapshots
- No separate snapshot storage line item — bundled into Function billing
- Modal periodically recaptures snapshots to track platform runtime updates

**How to verify snapshots are active:** the Function's Containers tab shows snapshot-creation and snapshot-restore icons. Logs contain `Snapshot created. Restoring Function from memory snapshot.`

**Decision rule:** snapshots are a single-GPU cold-start optimization. If `--min-replicas ≥ 1` (always-on), they rarely matter. If you're scale-from-zero with frequent wake-ups, they pay for themselves.

Run `scripts/estimate_cost.py --snapshot ...` for a comparison that surfaces these caveats inline.

### Deployment patterns (two distinct shapes)

**Shape A: Simple — `@modal.web_server` on a function.**
For models that fit on 1-2 GPUs, download weights on first boot, and don't need tight cold-start control.
Example: `gemma_server.py` in this skill; Modal's `vllm_inference.py`.

**Shape B: Lifecycle-controlled — `@app.cls` + `@modal.enter` / `@modal.exit` + `@modal.experimental.http_server`.**
For very large models (100B+), pre-downloaded weights at Image build time, regional proxy routing.
Example: `minimax_server.py` in this skill; Modal's `very_large_models.py` and `nemotron_inference.py`.

The shape you need depends on the model size, not personal preference.

### Image build-time weight download (for large models)

```python
def _download_weights(repo_id, revision=None):
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id=repo_id, revision=revision)

image = image.run_function(
    _download_weights,
    volumes={"/root/.cache/huggingface": hf_cache_vol},
    secrets=[modal.Secret.from_name("huggingface-secret")],
    kwargs={"repo_id": MODEL_NAME},
    timeout=60 * MINUTES,  # large downloads take real time
)
```

This moves the one-time download out of the cold-start path. Without it, first user to hit the cold endpoint waits for the full download.

## Pricing facts (verified April 2026)

Source: https://modal.com/pricing

### Per-second GPU rates
```
B200           $0.001736/sec  $6.25/hr   (192GB VRAM)
H200           $0.001261/sec  $4.54/hr   (141GB VRAM)
H100           $0.001097/sec  $3.95/hr   (80GB VRAM)
RTX_PRO_6000   $0.000842/sec  $3.03/hr   (48GB VRAM)
A100-80GB      $0.000694/sec  $2.50/hr   (80GB VRAM)
A100-40GB      $0.000583/sec  $2.10/hr   (40GB VRAM)
L40S           $0.000542/sec  $1.95/hr   (48GB VRAM)
A10            $0.000306/sec  $1.10/hr   (24GB VRAM)
L4             $0.000222/sec  $0.80/hr   (24GB VRAM)
T4             $0.000164/sec  $0.59/hr   (16GB VRAM)
```

### CPU and memory
- CPU: $0.0000131 per physical core per second (0.125 cores minimum per container)
- Memory: $0.00000222 per GiB per second

### Multipliers
- **Region selection:** 1.25× (low) to 2.5× (high) on top of base
- **Non-preemptible:** 3× on top of base
- These stack — non-preemptible + high-region = 7.5×

### Plan tiers
- **Starter** ($0/mo): $30/mo free credit, 3 seats, 100 containers, 10 GPU concurrency
- **Team** ($250/mo): $100/mo free credit, unlimited seats, 1000 containers, 50 GPU concurrency
- **Enterprise** (custom): volume discounts, HIPAA, SSO, audit logs

### Credit programs
- Startups: up to $25k free credits
- Academics (grad students, labs): up to $10k free credits

## What this skill should NOT pretend to know

If someone asks a question that touches these areas, don't guess — hit the live source:
- Pricing (it changes): always re-verify against modal.com/pricing
- Model availability and repo paths on HuggingFace: use `model-lookup/scripts/find_models.py`
- vLLM supported architectures: https://docs.vllm.ai/en/latest/models/supported_models.html (adds models every release)
- Current vLLM + transformers versions for a specific model: check the model card and Modal's canonical example, not training data

## Gotchas observed in practice

1. **Gated models (Gemma family).** Accept the license on HF first, then create the secret. Skipping the license acceptance produces a cryptic 403 on first weight fetch.

2. **`gpu_memory_utilization` too high causes OOM during CUDA graph capture.** Start at 0.90. If you see OOM in `capture_model_size` in the vLLM logs, drop to 0.85 or pass `--enforce-eager`.

3. **MoE models report smaller "active param" sizes.** Gemma 4 26B-A4B has 26B total / 4B active — plan GPU fit for 26B (weights-at-rest size), plan throughput for 4B (what's actually computed per token).

4. **FP8 native models.** MiniMax-M2.7 ships as FP8 on Hopper/Blackwell. Don't pass `--dtype half` — let vLLM detect. The FP8 weights are ~half the size of bf16 but still need native FP8 hardware (H100/H200/B200; not A100).

5. **`--trust-remote-code`.** MiniMax-M2.7 needs this. Many "custom" architectures do. Don't panic when you see it required — audit the repo first, then pass the flag if the code checks out.

6. **Throughput numbers are NOT guarantees.** The cost estimator uses published ranges, which are optimistic averages at moderate batch sizes. Real production throughput at long context + high concurrency is often 40-60% of the stated peak. Use `--worst-case` for conservative quotes.
