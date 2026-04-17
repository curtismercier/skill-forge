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
