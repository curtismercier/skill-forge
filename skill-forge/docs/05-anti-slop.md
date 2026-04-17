# Anti-slop — catching LLM hallucinations in drafts

Short doc; the full field guide is in `references/anti-slop-heuristics.md`.

## The one rule

Every fact you assert about an external API, pricing, or library must be:
- Sourced (you can point to where you verified it)
- Dated (when you last checked)
- Auditable (someone else can re-verify with a specific command)

Anything that doesn't meet these three tests is a candidate for hallucination.

## The audit workflow

```bash
# Automated mechanical checks (suspicious numbers, stale markers, slop attributions)
python scripts/audit_skill.py /path/to/draft/

# Security pass (hardcoded secrets, dangerous patterns)
python scripts/security_scan.py /path/to/draft/

# After using the skill for real, track drift
# Add entries to ERRATA.md (if Tier 3)
```

Then manually review for the patterns `audit_skill.py` can't catch automatically:

- Plausible-but-wrong function names (verify with `gh_research.py find`)
- Fabricated HuggingFace model IDs (verify with the model-lookup pattern)
- Confident statements about deprecated features (verify against canonical repos)
- Copy-pasted doc structure that signals pattern-matching rather than reasoning

## Why this matters

The most dangerous skills are the ones that *look* correct. An obviously broken skill gets caught on first use. A plausibly broken skill ships, runs once, produces wrong output, and the user debugs for an hour before realizing the skill itself was wrong.

Anti-slop work is about recognizing plausibility without substance. See `references/anti-slop-heuristics.md` for the ten patterns and how to catch them.

## The recursive case

This also applies to skill-forge's own output. If `new_skill.py` generates a scaffold that looks polished but references APIs or patterns that aren't quite right, that's slop too. Run the audit on generated skills and on skill-forge itself.
