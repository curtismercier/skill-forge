# Research phase — source-first, always

**This is mandatory reading for Tier 2 and Tier 3 skills.** Skipping it is the #1 cause of hallucinated skills.

## The rule

Do not generate code against an external API from training-data knowledge alone. Always confirm the current API against the canonical source first.

Why: training data has a cutoff. APIs evolve. Your model "knows" an SDK shape from 18 months ago; today's SDK may have renamed half its kwargs. If you write the skill from memory, the skill is wrong before it ships.

## The source hierarchy

Check in this order and stop at the first that answers your question:

1. **The tool's own `llms.txt` or `llms-full.txt`** (if published)
   - Modal: `https://modal.com/llms-full.txt`
   - Anthropic: `https://docs.claude.com/llms.txt`
   - Cloudflare: `https://developers.cloudflare.com/llms.txt`
   - An increasing number of tools publish these specifically for agents
   - `web_fetch` the file or save it locally for grep

2. **Canonical repo source** via `gh_research.py`
   - The SDK repo usually has the ground truth for signatures
   - Example repos show real usage patterns
   - Search with `find`, browse with `structure`, read with `read`

3. **Official HTML docs** via `web_fetch`
   - Good for narrative explanations when source is terse
   - Worse than source for exact API signatures (docs can lag source)

## `gh_research.py` — the standard research tool

```bash
# 1. Orient
python scripts/gh_research.py structure modal-labs/modal-examples

# 2. Find agent-authored docs (priority order: CLAUDE.md > AGENTS.md > SKILL.md > llms.txt > ...)
python scripts/gh_research.py docs modal-labs/modal-examples

# 3. Verify a specific API
python scripts/gh_research.py find modal-labs/modal "requires_proxy_auth"

# 4. Read the canonical file
python scripts/gh_research.py read modal-labs/modal-examples \
    06_gpu_and_ml/llm-serving/vllm_inference.py

# 5. Check recency
python scripts/gh_research.py releases modal-labs/modal 3
```

Set `GITHUB_TOKEN` in env to raise rate limits from 60/hr to 5000/hr.

## What to actually verify

For every factual claim in the skill:

- **Function signatures** — which kwargs exist, which are required, what defaults
- **Environment variables** — names, expected values
- **URLs** — endpoints still live, paths still route
- **Version pins** — what's current stable on PyPI/npm/crates.io
- **Model IDs** — do the HuggingFace / model-hub IDs resolve to real artifacts
- **Pricing** — fetch the provider's pricing page
- **CLI flags** — parse the current version's `--help`

## What to *not* bother verifying

- Stable concepts from established fields (linear algebra, CS fundamentals)
- Style conventions (the PEP-8 rules don't change quarterly)
- Language features older than the model's training data by a few years
- Your own skill's internal file names

## The "is this stale?" check

Before trusting cached research from a previous session:

```bash
python scripts/gh_research.py releases <owner>/<repo> 3
```

If the most recent release postdates your last verification, re-check. Breaking changes cluster in major releases; one recent major release = re-verify.

## The research output

End the research phase with a scratch file or notes listing:

- The canonical repo(s) / docs URL(s) for this skill's domain
- Current version pins for any pinned dependency
- 5-10 API points you confirmed (function names, kwarg names)
- Anything that surprised you or contradicted your initial assumptions

That scratch becomes the start of `references/<domain>-notes.md` in the final skill, with "Last verified: <date>" at the top.

## Why this takes real time

Good research for a Tier 3 skill is often 1-2 hours. Feels slow. But the alternative is writing a plausible-looking skill that fails the first time it's used, which costs a user *their* session debugging your hallucinations. The research time is amortized across every future use.

Skip this step at the project's peril. The audit script will catch some issues, but it can't replace real source-reading.
