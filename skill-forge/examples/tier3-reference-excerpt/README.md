# Tier 3 example: Modal LLM Inference skill

This directory is **not** a full Tier 3 skill — it's a pointer. The full example is the separate `modal-llm-inference.skill` package, which ships with:

- Top-level `SKILL.md` with decision tree and four deployment patterns
- `docs/` with 10 markdown files (foundation, deployment patterns, client integration, cost, TUI, proxy auth, cold starts, scaling, model weights, and a verification playbook)
- `ERRATA.md` tracking 5 drift entries (3 absorbed, 2 active)
- `references/modal-api-notes.md` with verified API ground truth
- `examples/basic-deployment/` with 6 runnable example servers
- `scripts/` including `gh_research.py`, a full cost estimator with 5 modes, and a real locust-on-Modal load test
- `model-lookup/` — a sub-skill answering "does this model exist and is it deployable?"
- 48 files total

## Why point-not-bundle

Including the full Modal skill here would:
- More than double the size of skill-forge
- Create version-drift risk (skill-forge getting out of sync with the standalone)
- Blur the "skill-forge is a tool, not an example library" message

Instead, skill-forge points at it and this README shows what the end-state looks like.

## Key files to study

If you want to see the Tier 3 pattern in action, look at these files from the Modal skill:

1. **`SKILL.md`** — demonstrates the "decision tree + pointers, not tutorials" pattern. Short main file routing to docs/.

2. **`docs/00-verification-playbook.md`** — the audit method. This file explains how the next agent can verify every claim in the skill.

3. **`ERRATA.md`** — drift log with `active/absorbed/outdated` lifecycle. Shows how corrections get tracked without silent rewrites.

4. **`references/modal-api-notes.md`** — verified API notes with "Last verified: April 2026" marker. Sources cited.

5. **`scripts/gh_research.py`** — the research tool the skill actually uses (and skill-forge ships the same one).

6. **`model-lookup/SKILL.md`** — sub-skill example. Shows when a distinct "is this doable?" question deserves its own triggerable skill.

## Lineage

The Modal skill was built iteratively over ~3 sessions, starting from a MiniMax-generated draft that had:

- Hallucinated pricing ($3.50/hr for H200, real is $4.54) <!-- noqa: audit -->
- Fabricated function signatures (`modal.Image.debian_windows`, real is `debian_slim`)
- Model names that didn't exist (`MiniMaxAI/MiniMax-2.7B` — real is `MiniMax-M2.7`)
- Deprecated kwargs (`container_idle_timeout` → `scaledown_window`)
- Old vLLM invocation pattern (`python -m vllm.entrypoints.openai.api_server` → `vllm serve`)

Every one of these failure modes became a heuristic in `skill-forge/references/anti-slop-heuristics.md`. The skill-forge audit script catches most of them automatically.

That transformation — from slop-ridden draft to audit-clean skill — is the template skill-forge teaches. The Modal skill is the proof that it works.
