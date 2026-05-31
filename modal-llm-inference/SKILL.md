---
name: modal-llm-inference
description: Deploy and run OpenAI-compatible LLM inference on Modal.com using vLLM or SGLang. Covers serverless GPU deployment of open-weight models (Gemma 4, DeepSeek V4 Flash/Pro, Qwen3-32B, MiniMax-M2.7) with Volume caching, scaledown tuning, HuggingFace auth, and cost estimation. Includes engine-selection guidance (vLLM for 1-2 GPU small models; SGLang for multi-GPU, MXFP4, and large-MoE). Use this skill whenever the user mentions deploying an LLM to Modal, self-hosting open-weight models, running vLLM on cloud GPUs, OpenAI-compatible inference servers, H100/H200/A100/B200 GPU provisioning for inference, or questions like "how do I serve Gemma/MiniMax/Qwen/DeepSeek on my own GPU" — even if they don't explicitly name Modal or vLLM.
license: MIT
metadata:
  author: curtismercier
  version: "0.4.0"
  source-style: authored
  produced-by: skill-forge
  home-repo: curtismercier/skill-forge
  created: 2026-04-16
  last_reviewed: 2026-05-30
  review_interval_days: 90
  dependencies:
    - name: Modal SDK
      url: https://modal.com/docs
    - name: vLLM
      url: https://github.com/vllm-project/vllm
    - name: SGLang
      url: https://github.com/sgl-project/sglang
    - name: HuggingFace Hub
      url: https://huggingface.co/docs/hub/en/index
---

# Modal vLLM LLM Inference

Deploy OpenAI-compatible LLM inference on Modal.com with vLLM (small models, 1-2 GPUs) or SGLang (large models, 3+ GPUs, MXFP4). Serverless GPUs, per-second billing, cold starts measured in tens of seconds when weights and JIT artifacts are cached on Modal Volumes.

## When to use this skill

- Deploying an open-weight LLM (Gemma 4, MiniMax-M2.7, Qwen, DeepSeek, Llama, Mistral, etc.) to cloud GPUs without managing Kubernetes
- Standing up an OpenAI-compatible `/v1/chat/completions` endpoint for a client app, agent, or TUI
- Batch inference or warm-pool patterns on Modal
- Estimating inference cost across GPU types (T4, L40S, A100-40/80, H100, H200, B200)
- Troubleshooting cold-start, OOM, or throughput issues on Modal+vLLM

If the user is asking about closed-source APIs (OpenAI, Anthropic, Google's hosted Gemini), this skill isn't the right match — they want an API client, not a self-hosted deployment.

## Quick navigation

| File | What's in it |
|---|---|
| [model-lookup/SKILL.md](model-lookup/SKILL.md) | **Sub-skill.** Discover open-weight LLMs on HuggingFace and check vLLM/SGLang compatibility *before* writing deployment code. Use when the user asks about a specific model/provider or wants recommendations. |
| [docs/01-foundation.md](docs/01-foundation.md) | Core concepts: Modal primitives, vLLM vs SGLang decision tree, Volume caching, architecture |
| [docs/02-deployment-patterns.md](docs/02-deployment-patterns.md) | Advanced patterns: scaling, snapshots, multi-GPU, container optimization |
| [docs/03-client-integration.md](docs/03-client-integration.md) | Python, JS, and terminal client patterns against the vLLM/SGLang endpoint |
| [docs/04-cost-management.md](docs/04-cost-management.md) | GPU cost comparison, throughput-vs-latency tradeoffs, budget tuning, **self-host vs API comparison** |
| [docs/05-tui-agent-patterns.md](docs/05-tui-agent-patterns.md) | TUI and agent integration patterns |
| [references/modal-api-notes.md](references/modal-api-notes.md) | Verified Modal Python API surface: Cls vs Function URLs, experimental HTTP server, secret conventions, SGLang image tags |

Load the specific doc that matches the user's question. Don't front-load all of them.

**Before recommending a deployment, check the model-lookup sub-skill** if the user is naming a specific model or provider — it catches cases like Prism ML's Bonsai (gguf/mlx only, not vLLM-deployable) before the user writes any code.

## Target models (verified against HuggingFace + Modal docs, April 2026)

| Model | HF repo | Size | Notes |
|---|---|---|---|
| Gemma 4 26B-A4B-it | `google/gemma-4-26B-A4B-it` | 26B total / 4B active (MoE), multimodal | Runs on a single H200; Modal's canonical vLLM example. Fastest of the Gemma 4 family. |
| Gemma 4 31B-it | `google/gemma-4-31B-it` | 30.7B dense, multimodal, 256K ctx | Beats 26B-A4B on every benchmark. Slower (dense, not MoE). Single H200 fits; vLLM + SGLang supported. |
| MiniMax-M2.7 | `MiniMaxAI/MiniMax-M2.7` | 229B total / 10B active (MoE), FP8 native | "Very large model" — follows Modal's `very_large_models.py` pattern. 4×H200 recommended floor (2×H200 possible with tiny KV cache) |
| DeepSeek V4 Flash | `deepseek-ai/DeepSeek-V4-Flash` | 284B total / 13B active (MoE), FP4 + FP8 mixed | Near-frontier coding (93.5% LiveCodeBench). **SGLang canonical** with `flashinfer_mxfp4`. 4×H200 min ($18.16/hr). Pre-converted FP8 also available at `sgl-project/DeepSeek-V4-Flash-FP8`. |
| DeepSeek V4 Pro | `deepseek-ai/DeepSeek-V4-Pro` | 1.6T total / 49B active (MoE), MXFP4 | Open-weight frontier — matches Opus 4.6 on SWE Verified (80.6%). Requires 8×B200 ($50/hr) for MXFP4 path. Modal's `deepseek_v4.py` uses SGLang `flashinfer_mxfp4`. |
| Qwen3-32B | `Qwen/Qwen3-32B` | 32B dense | Best quality-per-GPU ratio in open weight. Runs on 1×H200 ($4.54/hr). Strong general + coding. vLLM or SGLang both fine. |

If the user wants a different model, the deployment pattern (Image → Volumes → `@modal.web_server` wrapping `vllm serve`) is the same — only the model ID, GPU count, and `--tensor-parallel-size` change.

## Core pattern: `vllm serve` inside `@modal.web_server`

Small-to-medium models (fits on 1-2 GPUs) follow Modal's canonical `vllm_inference.py` pattern:

```python
vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.19.0")
    .uv_pip_install("transformers==5.5.0")     # Gemma 4 needs this
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})     # Xet backend — faster than hf_transfer
)

@app.function(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=15 * 60,                  # Modal v1 name (was container_idle_timeout)
    timeout=10 * 60,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,   # weights
        "/root/.cache/vllm": vllm_cache_vol,        # JIT artifacts (CUDA graphs, torch.compile)
    },
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=8000, startup_timeout=10 * 60)
def serve():
    subprocess.Popen(" ".join([
        "vllm", "serve", MODEL_NAME,
        "--revision", MODEL_REVISION,          # pin to avoid surprise updates
        "--served-model-name", MODEL_NAME, "llm",
        "--host", "0.0.0.0", "--port", "8000",
        "--async-scheduling",
        "--no-enforce-eager",                  # CUDA graphs on; best steady-state throughput
        "--tensor-parallel-size", str(N_GPU),
        # model-specific parsers:
        "--enable-auto-tool-choice",
        "--reasoning-parser", "gemma4",
        "--tool-call-parser", "gemma4",
    ]), shell=True)
```

**Large models (100B+ params, e.g. MiniMax-M2.7, DeepSeek V4 Flash/Pro)** follow a different pattern — see `minimax_server.py`. For DeepSeek V4 specifically, use Modal's `deepseek_v4.py` (SGLang on Blackwell) or SGLang's cookbook (https://docs.sglang.ai/cookbook/autoregressive/DeepSeek/DeepSeek-V4) which has an interactive command generator for Flash on H200 or Pro on B200. Key differences:
- Weights pre-downloaded at **Image build time** via `image.run_function(download_model, ...)` so the one-time ~230GB download isn't in the cold-start path
- Uses `modal.Cls` with `@modal.enter`/`@modal.exit` for explicit lifecycle control
- Uses `modal.experimental.http_server` instead of `modal.web_server` for lower-latency routing
- 4×H200 minimum for M2.7 FP8

Two Modal Volumes are non-negotiable for good cold starts: one for HF weights, one for vLLM's compilation cache. Without them, every cold boot re-downloads the model (minutes for small, tens of minutes for large) and re-compiles CUDA graphs (tens of seconds to minutes).

## Getting started

### Prerequisites

- Modal account (free tier includes $30/mo GPU credit)
- HuggingFace account + token with model access accepted (Gemma 4 is gated)
- Python 3.10+

### Setup

```bash
pip install modal
modal setup                                             # first-time auth
modal secret create huggingface-secret HF_TOKEN=hf_xxx  # convention across Modal examples
```

### First deployment

```bash
# Gemma 4 on a single H200 (canonical simple pattern)
modal deploy examples/basic-deployment/gemma_server.py

# MiniMax-M2.7 on 4×H200 (very-large-models pattern: Cls + pre-downloaded weights)
modal deploy examples/basic-deployment/minimax_server.py

# Iterate on server config without downloading 230GB of weights:
APP_USE_DUMMY_WEIGHTS=1 modal serve examples/basic-deployment/minimax_server.py
```

Both commands print a public URL like `https://<workspace>--gemma-4-vllm-server-serve.modal.run`. The OpenAI-compatible routes live at `/v1/*`; interactive docs are at `/docs`.

### Test

The server files include a `local_entrypoint` named `test()` that does a healthcheck + a streamed completion. Just:

```bash
modal run examples/basic-deployment/gemma_server.py
```

For manual testing from your laptop against a deployed URL, `test_client.py` takes `BASE_URL` and `MODEL_NAME` via env:

```bash
BASE_URL=https://<workspace>--gemma-4-vllm-server-serve.modal.run/v1 \
  MODEL_NAME=llm \
  python examples/basic-deployment/test_client.py
```

(The servers pass `--served-model-name MODEL_NAME llm`, so clients can use either the full HF repo ID or the short alias `"llm"`.)

## Directory layout

```
modal-llm-inference/
├── SKILL.md                              # this file
├── docs/
│   ├── 01-foundation.md                  # core concepts
│   ├── 02-deployment-patterns.md         # advanced deployment
│   ├── 03-client-integration.md          # client SDKs
│   ├── 04-cost-management.md             # cost optimization
│   └── 05-tui-agent-patterns.md          # TUI/agent patterns
├── examples/
│   ├── basic-deployment/
│   │   ├── gemma_server.py               # single-GPU H200 deploy (vLLM simple pattern)
│   │   ├── gemma_snapshot_server.py      # same model, ~10x faster cold starts via snapshots
│   │   ├── gemma_secured_server.py       # same model, Modal proxy auth enforced
│   │   ├── minimax_server.py             # multi-GPU tensor-parallel deploy (SGLang Cls pattern)
│   │   ├── deepseek_v4_flash_server.py   # DS V4 Flash 4×H200 (SGLang, flashinfer_mxfp4)
│   │   ├── config_deepseek_v4_flash.yaml # companion config for DS V4 Flash
│   │   ├── test_client.py                # OpenAI client smoke tests (supports proxy auth)
│   │   └── tool_calling_client.py        # agent loop with real tools (time/weather/calculate)
│   ├── tui-agent/
│   │   └── custom_tui_client.py          # terminal chat client
│   ├── batch-processing/
│   │   └── batch_inference.py            # throughput-oriented batch jobs
│   └── sandbox-pool/
│       └── warm_pool_manager.py          # warm pool pattern
├── docs/
│   ├── 00-verification-playbook.md       # ★ how to verify/audit any fact in this skill
│   ├── 01-foundation.md                  # concepts & architecture
│   ├── 02-deployment-patterns.md         # multi-replica, queue-based, auto-scaling
│   ├── 03-client-integration.md          # Python/JS/streaming client patterns
│   ├── 04-cost-management.md             # cost concepts & optimization
│   ├── 05-tui-agent-patterns.md          # TUI/agent patterns
│   ├── 06-proxy-auth.md                  # Modal proxy auth — the one auth pattern to use
│   ├── 07-cold-starts.md                 # ★ diagnosing & fixing cold-start latency
│   ├── 08-scaling.md                     # ★ autoscaler parameters + dynamic updates
│   └── 09-model-weights.md               # ★ HF → Volume → vLLM pipeline
├── ERRATA.md                             # ★ drift-tracking log (active/absorbed/outdated)
├── configs/
│   ├── gemma-4-config.yaml               # reference tuning for Gemma 4
│   ├── minimax-2.7-config.yaml           # reference tuning for MiniMax-M2.7
│   ├── deepseek-v4-flash-config.yaml     # reference tuning for DS V4 Flash
│   └── production-config.yaml            # production hardening template
└── scripts/
    ├── setup_secrets.py                  # helper for HF token secret
    ├── estimate_cost.py                  # GPU cost comparison + snapshot caveats + amortize mode
    ├── gh_research.py                    # ★ scan GitHub repos without cloning (use before guessing APIs)
    └── load_test/                        # locust-on-Modal load testing
        ├── load_test.py
        ├── locustfile.py
        └── README.md
```

## GPU fit table

Verified against Modal's pricing page and the models' VRAM requirements. FP8 row counts weights only — add 20–40% for KV cache.

| GPU | VRAM | Gemma 4 26B (1×) | Qwen3-32B (1×) | DS V4 Flash (4×) | DS V4 Pro (8×) |
|---|---|---|---|---|---|
| B200 | 192 GB | ✅ Overkill | ✅ Overkill | 1-2× works | **8× required** (MXFP4) |
| H200 | 141 GB | **✅ 1×** — canonical | **✅ 1×** — canonical | **✅ 4×** — recommended | ❌ FP4 only, no MXFP4 |
| H100 | 80 GB | ⚠️ Tight; FP8/AWQ | ⚠️ Tight | ⚠️ 4-8× FP8 only | ❌ |
| A100-80GB | 80 GB | ⚠️ Quantized only | ⚠️ Quantized | ❌ | ❌ |
| A100-40GB | 40 GB | ❌ | ❌ | ❌ | ❌ |
| L40S | 48 GB | ❌ | ❌ | ❌ | ❌ |

For any other model, compute `weights_in_bytes × 1.3` and match to the smallest GPU whose VRAM exceeds that. If it doesn't fit, add GPUs and set `--tensor-parallel-size N`.

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| Cold start >2 min on every request | No Modal Volumes mounted, weights re-downloading | Wire up `hf_cache_vol` and `vllm_cache_vol` — see `gemma_server.py` |
| `OOM during CUDA graph capture` | `gpu_memory_utilization` too high leaving no room for graphs | Drop from 0.95 to 0.90, or pass `--enforce-eager` to disable graphs |
| `403` from HuggingFace on first load | Gated model, token not attached or access not accepted | Accept the model's license on HF, then `modal secret create huggingface-secret ...` |
| `container_idle_timeout` TypeError | Modal API v1 renamed the parameter | Use `scaledown_window` instead |
| Server process dies after a few seconds | `subprocess.Popen` without the `@modal.web_server` decorator | Use `@modal.web_server(port=..., startup_timeout=...)` + subprocess pattern |

## Four deployment shapes (pick one based on your situation)

This skill provides four runnable examples covering the real distribution of needs:

| Pattern | File | When to use |
|---|---|---|
| **Simple** | `gemma_server.py` | Model fits on 1-2 GPUs, iterating on config, don't need optimal cold starts. Modal's canonical `vllm_inference.py` pattern. |
| **Snapshot** | `gemma_snapshot_server.py` | Same model fit, but you care about cold starts (scale-from-zero traffic). Adds ~10× cold-start reduction via `modal.Cls` + GPU memory snapshots + vLLM sleep mode. **Single-GPU only** — GPU snapshots are incompatible with tensor-parallel multi-GPU (cuMem API vs NCCL topology). |
| **Secured** | `gemma_secured_server.py` | You want Modal's proxy auth — unauthorized requests rejected by Modal before any container spins up (zero cost for bad traffic). Uses `requires_proxy_auth=True`. See `docs/06-proxy-auth.md`. |
| **Large** | `minimax_server.py` | 100B+ models with pre-downloaded weights. Cls + `modal.enter`/`modal.exit` + `modal.experimental.http_server`. Modal's `very_large_models.py` pattern. |
| **DeepSeek V4 Flash** | `deepseek_v4_flash_server.py` | DS V4 Flash (284B, 13B active) on 4×H200. **SGLang** with `flashinfer_mxfp4`. EAGLE spec decode. YAML config. $18.16/hr. |
| **DeepSeek V4 Pro** | Modal's `deepseek_v4.py` | DS V4 Pro (1.6T, 49B active) on 8×B200. SGLang `flashinfer_mxfp4` (Blackwell required). $50/hr. See modal-labs/modal-examples. |

These are composable — you can combine snapshot + secured, for example, by setting `requires_proxy_auth=True` on the snapshot example's `@modal.web_server` decorator. Don't pick based on "which is newest" — pick based on model size, traffic pattern, and whether the endpoint needs to be public.

### Upstream Sources

This skill adapts patterns from Modal's canonical examples. When a pattern is directly derived, the upstream URL is noted in the example file header. Key sources:

| Pattern | Upstream | Engine |
|---|---|---|
| `gemma_server.py` | [vllm_inference.py](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/vllm_inference.py) | vLLM |
| `minimax_server.py` | [very_large_models.py](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/very_large_models.py) | SGLang |
| `deepseek_v4_flash_server.py` | Modal's [deepseek_v4.py](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/deepseek_v4.py) + SGLang [cookbook](https://docs.sglang.ai/cookbook/autoregressive/DeepSeek/DeepSeek-V4) | SGLang |
| `sglang_snapshot_server.py` (not in this skill) | [sglang_snapshot.py](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/sglang_snapshot.py) | SGLang |
| `sglang_kitchen_sink.py` (not in this skill) | [sglang_kitchen_sink.py](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/sglang_kitchen_sink.py) | SGLang |

When upstream examples update their API patterns, the skill's copies should follow. Run `modal deploy` on the upstream example and verify before absorbing changes here.

## Load testing

`scripts/load_test/` contains a real locust-on-Modal setup adapted from Modal's canonical load test. Point `TARGET_HOST` at your deployed URL:

```bash
export TARGET_HOST=https://<workspace>--gemma-4-vllm-server-serve.modal.run

# Headless benchmark: 36 users, 2 minutes
modal run scripts/load_test/load_test.py --r 1 --u 36 --t 2m

# Interactive locust UI (Modal prints the URL)
modal serve scripts/load_test/load_test.py
```

Results land in a Modal Volume as timestamped CSV + HTML reports. Details in `scripts/load_test/README.md`.

## Securing endpoints (Modal proxy auth)

For almost any deployed endpoint, add `requires_proxy_auth=True` to the web decorator:

```python
@modal.web_server(port=VLLM_PORT, startup_timeout=10*MINUTES, requires_proxy_auth=True)
def serve():
    subprocess.Popen(["vllm", "serve", MODEL_NAME, ...])
```

Modal rejects unauthorized requests at its proxy layer, **before any container starts** — so unauthorized traffic costs zero. Clients send `Modal-Key` + `Modal-Secret` headers. Tokens created at https://modal.com/settings/proxy-auth-tokens.

Full guide with OpenAI SDK, curl, and Node examples: `docs/06-proxy-auth.md`. Runnable example: `examples/basic-deployment/gemma_secured_server.py`.

Don't roll your own bearer-token middleware unless you need per-user auth — Modal's proxy auth is strictly better for workspace-level protection.

## Cost estimation

`scripts/estimate_cost.py` uses Modal's verified per-second GPU pricing (April 2026) and honest throughput ranges to estimate before you deploy.

```bash
# Show the current Modal GPU price sheet
python scripts/estimate_cost.py --rates

# Pointers to post-hoc billing APIs (modal.billing, App tags, budget cap)
python scripts/estimate_cost.py --tracking

# Compare GPU options for a model + workload
python scripts/estimate_cost.py --compare --model gemma-4-31b --requests 100000

# Same comparison with snapshot-mode caveats appended
python scripts/estimate_cost.py --compare --model gemma-4-26b-a4b --rps 0.1 --hours 24 --snapshot

# Specific deployment: 2 rps for 24h on an H100, always-on
python scripts/estimate_cost.py --single --model gemma-4-26b-a4b --gpu H100 \
    --rps 2 --hours 24 --min-replicas 1

# Conservative quote: use low-end throughput estimates only
python scripts/estimate_cost.py --compare --model minimax-m27 --requests 10000 --worst-case
```

Known models: `gemma-4-26b-a4b`, `gemma-4-31b`, `minimax-m27`. Add more in `MODELS` at the top of the script — throughput ranges should be honest published benchmarks, not marketing numbers.

**Always-on vs. serverless.** Scale-to-zero (default) means you pay only for seconds of actual compute. `--min-replicas 1` keeps a warm replica — you pay for the full window regardless of traffic. For a typical "chat app that gets hit once an hour" use case, serverless is 10-50× cheaper; for a latency-sensitive production API, always-on is worth the cost.

**Run the estimator BEFORE every deploy.** This isn't paranoia — a mis-sized GPU or a runaway prompt loop on a B200 can burn real money fast. The estimator is cheap; the surprise isn't.

See [docs/04-cost-management.md](docs/04-cost-management.md) for deeper methodology and vLLM throughput-tuning tradeoffs, and [references/modal-api-notes.md](references/modal-api-notes.md) for the verified pricing sheet.

## Research before building

Before guessing at Modal or vLLM APIs, use `scripts/gh_research.py` to scan the canonical source. It's stdlib-only Python (no bash/jq/gh dependencies) and runs anywhere.

```bash
# What's actually in Modal's examples repo?
python scripts/gh_research.py structure modal-labs/modal-examples
python scripts/gh_research.py docs modal-labs/modal-examples   # agent-authored files first

# Does this API exist, and where?
python scripts/gh_research.py find modal-labs/modal "requires_proxy_auth"

# Read the canonical file before adapting its pattern:
python scripts/gh_research.py read modal-labs/modal-examples \
    06_gpu_and_ml/llm-serving/vllm_inference.py

# Check recent releases for breaking changes before trusting cached knowledge:
python scripts/gh_research.py releases modal-labs/modal 3
```

Doc discovery follows priority order: `CLAUDE.md > AGENTS.md > SKILL.md > llms.txt > llms-full.txt > README.md` — agent-authored files first, since those are the highest-signal.

Set `GITHUB_TOKEN` in the environment to raise the API limit from 60/hr to 5000/hr. For Modal specifically, also fetch https://modal.com/llms.txt — Modal publishes it explicitly for LLM agents.

## Self-healing — verifying this skill is still current

Before trusting any time-sensitive fact in this skill (pricing, API names, vLLM flags, model IDs), consult the **verification playbook**:

- **`docs/00-verification-playbook.md`** — specific recipes for confirming decorators, flags, pricing, model IDs. Tells you exactly which repo to grep, which URL to fetch, and how to recognize drift.
- **`ERRATA.md`** — drift-tracking log with `active/absorbed/outdated` lifecycle (pattern from jezweb/claude-skills). When you find staleness, log it here before rewriting; gives history, not just current state.

The one-liner to run when you arrive at this skill after a while:
```bash
python scripts/gh_research.py releases modal-labs/modal 3
python scripts/gh_research.py releases vllm-project/vllm 3
```
If either shows a release newer than the "Verified: YYYY-MM" marker at the top of `references/modal-api-notes.md`, that file may have drifted — re-audit.

## Tool-calling (function calling) from clients

The server examples already enable auto tool choice (`--enable-auto-tool-choice --tool-call-parser gemma4`). The client side follows the OpenAI spec exactly.

See `examples/basic-deployment/tool_calling_client.py` for the full agent loop: user question → model requests tool call → client executes tool → result returned as `role: "tool"` → model produces final answer. Handles multiple tool calls per round and loops until the model returns a non-tool message (bounded by `max_tool_rounds`).

```bash
BASE_URL=https://<workspace>--gemma-4-vllm-server-serve.modal.run/v1 \
    python examples/basic-deployment/tool_calling_client.py
```

Key pattern reminders when adapting to your own tools:
- Tools schema is JSON Schema (not Pydantic) and goes in the `tools=` parameter of `chat.completions.create`
- Append the assistant's tool-call message to history before tool results — the model needs to see its own request echoed back
- Tool results are `role: "tool"` with matching `tool_call_id` — don't lose the ID
- Return JSON strings from tools; the model parses them back as structured data
- For production: validate tool arguments (type, range), handle exceptions as tool errors (not raises), and log tool calls separately from user messages

vLLM tool-calling reference: https://docs.vllm.ai/en/latest/features/tool_calling.html

## Key references

### Modal (primary sources — hit these when uncertain)
- **[Modal's `llms.txt`](https://modal.com/llms.txt)** — Modal publishes this specifically for LLM agents. When you lack certainty about anything Modal-related, fetch this first
- **[Developing with LLMs guide](https://modal.com/docs/guide/developing-with-llms)** — Modal's own rules for agent-written Modal code
- [Modal vLLM canonical example](https://modal.com/docs/examples/vllm_inference) — the reference implementation the Gemma pattern follows
- [Modal very-large-models example](https://modal.com/docs/examples/very_large_models) — the pattern the MiniMax server follows (SGLang, 100B+ models)
- [Modal DeepSeek V4 example](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/deepseek_v4.py) — Modal's official DS V4 Pro deployment (SGLang, 8×B200, MXFP4)
- [Modal DeepSeek V4 config](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/llm-serving/config_deepseek_v4.yaml) — reference YAML for MoE tuning, EAGLE spec decode, batching
- [Modal Ministral 3 + memory snapshots](https://modal.com/docs/examples/ministral3_inference) — how to cut cold starts 10× further with GPU memory snapshots
- [SGLang DeepSeek V4 cookbook](https://docs.sglang.ai/cookbook/autoregressive/DeepSeek/DeepSeek-V4) — interactive config generator for Flash-on-H200 and Pro-on-B200
- [High-performance LLM inference guide](https://modal.com/docs/guide/high-performance-llm-inference)
- [Modal pricing](https://modal.com/pricing) — always re-verify before quoting costs
- [LLM Almanac](https://modal.com/llm-almanac) — Modal's own benchmark data
- [Modal GPU Glossary](https://modal.com/gpu-glossary) — for explaining VRAM, tensor parallelism, KV cache

### Modal source (77 public repos)
- [github.com/modal-labs](https://github.com/modal-labs) — org page
- [modal-labs/modal-examples](https://github.com/modal-labs/modal-examples) — canonical reference code
- [modal-labs/modal-client](https://github.com/modal-labs/modal-client) — SDK source of truth
- [modal-labs/multinode-training-guide](https://github.com/modal-labs/multinode-training-guide)
- [modal-labs/awesome-modal](https://github.com/modal-labs/awesome-modal) — community-built projects

### vLLM and model cards
- [vLLM docs](https://docs.vllm.ai/)
- [vLLM supported models](https://docs.vllm.ai/en/latest/models/supported_models.html) — check before assuming architecture support
- [Gemma 4 26B-A4B-it](https://huggingface.co/google/gemma-4-26B-A4B-it)
- [Gemma 4 31B-it](https://huggingface.co/google/gemma-4-31B-it)
- [MiniMax-M2.7](https://huggingface.co/MiniMaxAI/MiniMax-M2.7)

For verified API specifics, GPU pricing, and gotchas encountered in practice, see **[references/modal-api-notes.md](references/modal-api-notes.md)**.
