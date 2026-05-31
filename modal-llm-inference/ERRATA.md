# ERRATA — Known discrepancies and drift

This file tracks corrections to the main skill docs as they are discovered. The pattern is borrowed from [jezweb/claude-skills/CLAUDE.md](https://github.com/jezweb/claude-skills/blob/main/CLAUDE.md).

**Lifecycle:** `active` (known drift, correction here) → `absorbed` (correction folded into main docs) → `outdated` (the underlying thing changed again; a new `active` entry replaces this one).

Always add new entries at the top. Keep absorbed/outdated entries for history — they show *how* the skill has evolved.

---

## 2026-04-16 — vLLM `timeout=300` on long cold-start functions

**Status:** `active`
**Location:** `docs/02-deployment-patterns.md:45`, `docs/02-deployment-patterns.md:173`, `docs/04-cost-management.md` (multiple)
**Drift:** Example snippets use `timeout=300` (5 min) on `@app.function` decorators that run vLLM. On first-ever boot, vLLM weight download + JIT compilation can exceed 5 minutes, causing timeout failures.
**Correct value:** `timeout=600` (10 min) minimum; `timeout=900` (15 min) if the model is >30B params or weights aren't cached in a Volume yet.
**How to verify:** watch the container startup in Modal's dashboard on first deploy. If cold-start time approaches the timeout, bump it.
**How to fix when absorbing:** grep for `timeout=300` in the docs and bump to 600 only where the `@app.function` runs vLLM (not for short-lived client calls).

---

## 2026-04-16 — Missing parser flags in doc snippets

**Status:** `active`
**Location:** `docs/01-foundation.md`, `docs/02-deployment-patterns.md`, `docs/04-cost-management.md`, `docs/05-tui-agent-patterns.md` — all `"vllm", "serve", "google/gemma-4-26B-A4B-it"` invocations
**Drift:** Doc snippets invoke `vllm serve google/gemma-4-26B-A4B-it` without the parser flags that current vLLM requires for Gemma 4's tool calling and reasoning features.
**Correct value:** always include:
```
--enable-auto-tool-choice
--reasoning-parser gemma4
--tool-call-parser gemma4
```
(For MiniMax-M2.7 it's `--reasoning-parser minimax --tool-call-parser minimax-m2 --trust-remote-code`.)
**How to verify:** `python scripts/gh_research.py find vllm-project/vllm "reasoning-parser"` to see the current list of supported parsers; or read the canonical example at `examples/basic-deployment/gemma_server.py` which has the full correct invocation.
**How to fix when absorbing:** since the docs are pattern demonstrations (not copy-paste servers), the pragmatic fix is leaving them minimal and letting the canonical-source banner at each doc's top point readers to `examples/basic-deployment/*.py` for the full flag list. Alternatively, add a single "full flag reference" block in `docs/01-foundation.md`.

---

## 2026-04-16 — `container_idle_timeout` deprecated in favor of `scaledown_window`

**Status:** `absorbed`
**Location:** Previously in `docs/01-foundation.md`, `docs/04-cost-management.md`, etc.
**Drift:** Modal 1.0 renamed the `container_idle_timeout` kwarg on `@app.function` to `scaledown_window`. Both names worked for a deprecation period; as of Modal 1.x the old name emits a warning.
**Correct value:** `scaledown_window=<seconds>`
**Absorbed in commit:** 2026-04-16 audit pass. All 5 instances across the docs were renamed via sed.
**Verification command:** `grep -r "container_idle_timeout" docs/ examples/ scripts/` should return nothing.

---

## 2026-04-16 — `python -m vllm.entrypoints.openai.api_server` → `vllm serve`

**Status:** `absorbed`
**Location:** Previously in `docs/01-foundation.md`, `docs/02-deployment-patterns.md`, `docs/04-cost-management.md`, `docs/05-tui-agent-patterns.md`.
**Drift:** Old-style vLLM invocation via `python -m vllm.entrypoints.openai.api_server --model X` was replaced by `vllm serve X` as the canonical form in vLLM 0.5+.
**Correct value:** `vllm serve <model-name> --port 8000 ...`
**Absorbed in commit:** 2026-04-16 audit pass. All 10 instances replaced via Python regex.
**Verification command:** `grep -r "vllm.entrypoints.openai.api_server" docs/` should return nothing.

---

## 2026-04-16 — vLLM version pin `>=0.6.0` was ~18 months stale

**Status:** `absorbed`
**Location:** Previously in `docs/01-foundation.md`, `docs/02-deployment-patterns.md`, `docs/04-cost-management.md`, `docs/05-tui-agent-patterns.md`.
**Drift:** Original draft pinned `vllm>=0.6.0`. By April 2026, vLLM has shipped multiple breaking changes since 0.6.
**Correct value:** `vllm==0.19.0` (verified against Modal's canonical examples at modal-labs/modal-examples).
**Absorbed in commit:** 2026-04-16 audit pass. All 10 instances bumped. Upgraded from `pip_install` to `uv_pip_install` in the same pass (Modal's current idiom).
**Next review:** check https://github.com/vllm-project/vllm/releases quarterly. When vLLM 0.20+ ships with breaking changes, bump this pin and re-test the snapshot example (sleep-mode API has churned before).

---

## 2026-05-30 — Zero DeepSeek V4 coverage across entire skill

**Status:** `active`
**Location:** SKILL.md, docs/01-foundation.md, docs/02-deployment-patterns.md, docs/04-cost-management.md, model-lookup/SKILL.md, scripts/estimate_cost.py
**Drift:** The skill covers Gemma 4 and MiniMax only. DeepSeek V4 Flash and Pro are the most significant open-weight releases of 2026 (93.5% LiveCodeBench, 80.6% SWE Verified) and are not mentioned anywhere — no model entry, no deploy config, no benchmark data, no cost estimate.
**Correct value:** Add DeepSeek V4 Flash (284B total / 13B active, FP4+FP8, 4×H200 min) and DeepSeek V4 Pro (1.6T total / 49B active, MXFP4, 8×B200 min) across:
  - SKILL.md target models table
  - model-lookup/SKILL.md known providers
  - docs/01-foundation.md GPU requirements + engine decision tree
  - docs/04-cost-management.md pricing + self-vs-API section
  - scripts/estimate_cost.py model database
  - GPU fit table in SKILL.md
**How to verify:** `grep -r "DeepSeek\|deepseek" . --include="*.md" --include="*.py" | grep -v node_modules | grep -v __pycache__ | wc -l` should be >0 (was 0 before this fix).
**How to fix when absorbing:** See the 2026-05-30 audit pass — all files updated together.

---

## 2026-05-30 — Skill assumes vLLM only; SGLang is canonical for large models

**Status:** `active`
**Location:** SKILL.md, docs/01-foundation.md, docs/02-deployment-patterns.md, references/modal-api-notes.md
**Drift:** The skill describes itself as "using vLLM" and covers only vLLM patterns. Modal's own GitHub has `deepseek_v4.py` (SGLang on Blackwell), `very_large_models.py` (SGLang for 100B+ models), and SGLang is explicitly preferred over vLLM for large models. DeepSeek V4's canonical path is SGLang with `flashinfer_mxfp4`. The skill doesn't mention SGLang as a deployment option.
**Correct value:** Add SGLang as a parallel track:
  - SKILL.md: update description to "using vLLM or SGLang", add SGLang dependency
  - docs/01-foundation.md: add engine decision tree (vLLM for 1-2 GPU small models, SGLang for 3+ GPU large models)
  - docs/02-deployment-patterns.md: add SGLang `Cls` + `@modal.experimental.http_server` pattern
  - references/modal-api-notes.md: add SGLang image tags, deepseek_v4.py reference
**How to verify:** `grep -r "SGLang\|sglang" docs/*.md | wc -l` should show substantive references, not just passing mentions.

---

## 2026-05-30 — Missing "should I self-host?" cost decision framework

**Status:** `active`
**Location:** docs/04-cost-management.md
**Drift:** The cost document compares GPU types against each other but never answers the question users actually ask: "is this cheaper than OpenRouter/an API?" It optimizes for cold-start cost, idle-timeout tuning, and batch sizing — all internal efficiency — without acknowledging that for most workloads at 2026 API pricing, self-hosting is 10-600× more expensive per token.
**Correct value:** Add a "Self-Host vs API" section to `docs/04-cost-management.md` that presents honest break-even math with real API pricing examples (DeepSeek V4 Flash at $0.10/$0.20/M via OpenRouter vs $18.16/hr on 4×H200), describes the specific conditions where self-hosting wins (high concurrency, privacy, fine-tuned models), and provides a decision table.
**How to verify:** `grep -r "OpenRouter\|API\|self-host\|break-even\|breakeven" docs/04-cost-management.md` should return a substantive section.

---

## 2026-05-30 — GPU memory snapshots incompatible with tensor-parallel multi-GPU

**Status:** `active`
**Location:** SKILL.md (snapshot deployment shape), docs/02-deployment-patterns.md, docs/07-cold-starts.md
**Drift:** The skill mentions GPU memory snapshots as a cold-start mitigation but doesn't document that they are incompatible with tensor-parallel multi-GPU setups. Modal's own docs confirm: "Generally incompatible with multi-GPU tensor-parallel setups — our MiniMax example (4×H200) cannot use GPU snapshots today." The snapshot deployment shape in SKILL.md says "single-GPU only" but doesn't explain why.
**Correct value:** Add explicit warning: GPU memory snapshots use CUDA's cuMem API which doesn't support multi-GPU tensor-parallel memory topologies. Attempting to combine them silently fails or causes undefined behavior. Single-GPU deployments only.
**How to verify:** `grep -r "tensor-parallel\|multi-GPU\|incompatible" docs/07-cold-starts.md | grep -i snapshot` should find the warning.

---

## 2026-05-30 — Missing Modal GitHub example references

**Status:** `active`
**Location:** SKILL.md (Key references section), references/modal-api-notes.md
**Drift:** The skill references `vllm_inference.py` as the canonical Modal example but doesn't mention `very_large_models.py`, `deepseek_v4.py`, or `config_deepseek_v4.yaml` — all found in `modal-labs/modal-examples/06_gpu_and_ml/llm-serving/` during today's research. These cover SGLang patterns, multi-GPU tensor-parallel, and YAML-based config that are essential for large models.
**Correct value:** Add these to the Key references section in SKILL.md and to references/modal-api-notes.md:
  - `deepseek_v4.py` — Modal's official DeepSeek V4 Pro deployment (SGLang, 8×B200, MXFP4)
  - `config_deepseek_v4.yaml` — reference YAML for MoE tuning, EAGLE spec decode, batching
  - `very_large_models.py` — SGLang pattern for 100B+ models with dummy-weights iteration
**How to verify:** `grep -r "deepseek_v4\|config_deepseek\|very_large_models" SKILL.md references/` should find all three.

---

## Template for new entries

```markdown
## YYYY-MM-DD — <one-line summary of the drift>

**Status:** `active` | `absorbed` | `outdated`
**Location:** <files:lines where the drift shows up>
**Drift:** <what the skill currently says, and why it's wrong>
**Correct value:** <what it should say>
**How to verify:** <specific command or URL the next agent can run>
**How to fix when absorbing:** <the concrete edit to make>
```
