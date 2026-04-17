# Verification Playbook — how to confirm any fact in this skill is still true

**Audience:** the next Claude working on this skill. Don't go on a goose chase. This is the map.

## First principle: ground truth lives in source trees, not in your training data

If your training data disagrees with what `gh_research.py read` shows you from a canonical repo, the canonical repo wins. Period. Modal ships breaking changes; vLLM ships breaking changes; the LLM model landscape shifts monthly. The code actually in the repo at HEAD is what works today.

## The three-source hierarchy

When verifying anything about Modal, vLLM, or a specific model, check sources in this order and stop at the first that answers the question:

1. **Modal's llms.txt** — https://modal.com/llms.txt and https://modal.com/llms-full.txt
   Modal publishes these explicitly for LLM agents. They are *the* agent-optimized reference.
   `llms-full.txt` is the entire doc site concatenated — one fetch gets you everything.

2. **Canonical repo source** — use `scripts/gh_research.py`:
   ```bash
   # Is this API current?
   python scripts/gh_research.py find modal-labs/modal "requires_proxy_auth"

   # What's the actual signature?
   python scripts/gh_research.py read modal-labs/modal py/modal/_partial_function.py

   # What example shows the pattern?
   python scripts/gh_research.py structure modal-labs/modal-examples
   python scripts/gh_research.py read modal-labs/modal-examples 06_gpu_and_ml/llm-serving/vllm_inference.py
   ```

3. **Modal's official docs (HTML pages)** — `web_fetch` on `modal.com/docs/...`
   Best for narrative explanations when source-only reading is opaque.
   The sidebar menu in the fetched HTML contains a complete page list — use it to discover pages.

## Canonical repos to know about

| Repo | What lives there | When to consult |
|---|---|---|
| `modal-labs/modal` | Python client SDK source (`py/modal/`) | Decorator signatures, parameter types, error classes |
| `modal-labs/modal-examples` | Runnable example apps | Real-world patterns, CLI incantations, combinations |
| `vllm-project/vllm` | vLLM source + docs | vLLM flags, supported architectures, parser names |
| `huggingface/transformers` | Model config classes | Model-specific quirks, tokenizer modes, revisions |

## Specific verification recipes

### "Is this Modal decorator still valid?"
```bash
python scripts/gh_research.py find modal-labs/modal "def _<decorator_name>"
python scripts/gh_research.py read modal-labs/modal py/modal/_partial_function.py
```
Look for the function signature and its kwargs. If you added a new kwarg recently, search for references in `modal-examples` to confirm usage patterns.

### "Does this vLLM flag exist in the current version?"
```bash
# Check vllm's CLI parser
python scripts/gh_research.py find vllm-project/vllm "--<flag-name>"
# Or check the entry-point file
python scripts/gh_research.py read vllm-project/vllm vllm/entrypoints/openai/cli_args.py
```

### "Does this HuggingFace model still exist / has its repo ID changed?"
Use the model-lookup sub-skill:
```bash
python model-lookup/scripts/find_models.py --query "<model family>" --inspect
```
This hits the HF API live. If a model you assumed exists doesn't show up, it has been renamed or unpublished.

### "What's the current Modal GPU pricing?"
```bash
# Fetch the pricing page directly
# https://modal.com/pricing
# Our references/modal-api-notes.md has a dated snapshot — check its "Verified: YYYY-MM" line.
# If the date is >3 months old, re-verify before quoting to anyone.
```

### "Is this environment variable / feature flag still named X?"
```bash
python scripts/gh_research.py find modal-labs/modal-examples "<ENV_VAR_NAME>"
# Often the most-recent example file is the most-trustworthy.
```

## How to tell if a fact in this skill is stale

Signals that something below is drifting:

- **API names in this skill don't appear in `modal-labs/modal` at HEAD** → rename or removal happened
- **Snippets use import paths that `pip install modal` doesn't provide** → package refactor
- **vLLM flags return "unrecognized argument"** → vLLM breaking change (check vLLM releases)
- **HF model IDs 404** → model repo rename/deletion
- **Modal dashboard shows different behavior than our docs describe** → UI/backend change, update docs

When you find staleness: **don't silently rewrite the doc**. Add an ERRATA.md entry (see below) so the history is preserved. Only fold the correction into the main doc once you're confident it's stable.

## The ERRATA.md lifecycle

This skill uses the pattern from `jezweb/claude-skills/CLAUDE.md`:

1. **active** — you found a drift. Add it to `ERRATA.md` with status `active` and the correct value. Leave the docs unchanged.
2. **absorbed** — after a successful use (or a week of stability), fold the correction into the canonical doc and flip status to `absorbed`. Keep the ERRATA entry as a record.
3. **outdated** — the underlying thing changed again. Mark `outdated`, add a new `active` entry above.

Why this matters: silent edits create "is the doc or the code right?" ambiguity. ERRATA makes drift history legible.

## How this skill was originally audited

For the next agent's sanity, here's what I actually did:

1. Cloned `modal-labs/modal-examples` and `modal-labs/modal` into a sandbox
2. Grepped for every claim the original draft made (`get_web_url`, `requires_proxy_auth`, `enable_memory_snapshot`, etc.)
3. Compared training-data assumptions against source. Several were wrong (the URL retrieval pattern is a 3×2 matrix, not a 2-line rule).
4. Cross-referenced Modal's own published docs (`modal.com/docs/guide/*`) for narrative context
5. Verified the vLLM flag list against `vllm-project/vllm` source
6. Checked the pricing page directly for per-second GPU rates

**Time budget:** this was ~3 sessions of focused work. Future audits should be smaller — you're checking deltas, not rebuilding from scratch. Use `gh_research.py releases modal-labs/modal 5` to see what's changed recently; that tells you where to look.

## The "is this skill still current?" one-liner

Run this before trusting the skill for anything time-sensitive:

```bash
# Check how recent the most important upstream repos are.
# If any has moved significantly since references/modal-api-notes.md's verified date, re-audit.
python scripts/gh_research.py releases modal-labs/modal 3
python scripts/gh_research.py releases vllm-project/vllm 3
```

If either shows a release dated after the "Verified: YYYY-MM" line at the top of `references/modal-api-notes.md`, treat that file as potentially drifted until you've rechecked.
