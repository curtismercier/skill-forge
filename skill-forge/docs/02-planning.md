# Planning — picking the right tier

Answer these questions honestly. Each one pushes you up or down the ladder.

## Question 1: Is this skill about a domain that changes faster than 6 months?

Examples of fast-changing domains:
- Cloud serverless platforms (Modal, Cloudflare Workers, Vercel)
- LLM ecosystems (vLLM, SGLang, TensorRT-LLM)
- Frontend frameworks (React, Next.js, Svelte patterns)
- Any SaaS API with active feature development

Examples of stable domains:
- Unix text processing (awk, sed, jq — the basics)
- Writing patterns (haiku, sonnets, screenwriting structure)
- Established algorithms (sorting, graph traversal)
- Git usage patterns (the core 95% — rebase, merge, cherry-pick)

**Fast-changing** → Tier 3. You need `ERRATA.md` and a verification playbook.
**Stable** → Tier 1 or 2 depending on the other questions.

## Question 2: Does the skill need to run code during use?

If the agent running the skill needs to:
- Hit an API to check a live fact
- Scrape documentation
- Query a database for schema
- Validate something that changes (e.g. "is this HF model still available?")

...then you need `scripts/`. That's minimum Tier 2.

If the skill only teaches a pattern or writes content, no scripts needed. Tier 1 is fine.

## Question 3: Does the skill depend on verifiable facts?

If the skill asserts specific things about external APIs (pricing, function signatures, flag names, version pins), those facts must be:
- Sourced (cited back to upstream)
- Dated (when you last checked)
- Auditable (someone can verify them later)

That's `references/*.md` — minimum Tier 2.

If the skill is pure pattern with no external dependencies, skip references. Tier 1.

## Question 4: Does the skill have distinct preflight vs main-task questions?

Example from the Modal skill: "does this model exist and is it deployable on Modal?" is a different question from "how do I deploy it?" The first is preflight; the second is the main task.

When preflight and main task have different answer shapes, the preflight often deserves its own sub-skill (triggerable independently, reusable across main tasks). That's Tier 3.

If there's just one question shape, skip sub-skills.

## Question 5: How long do you expect this skill to be useful?

- **Weeks** (one-off for a current project) → Tier 1 if possible. Don't over-invest.
- **Months** → Tier 2. Basic verification.
- **Years** → Tier 3. The maintenance burden is real; plan for it.

## Summary decision

```
Fast-changing + facts-heavy + long-lived → Tier 3
Scripts needed + stable-ish          → Tier 2
Pattern only + no external deps      → Tier 1
```

If you're genuinely unsure between 2 and 3, start at 2 and upgrade if maintenance pain appears. Downgrading from 3 to 2 is awkward; upgrading 2 → 3 is easy.

## After you pick

```bash
python scripts/new_skill.py --tier <N> --name <skill-name> --domain "<description>"
```

Then proceed to `docs/03-research-phase.md` if tier ≥ 2.
