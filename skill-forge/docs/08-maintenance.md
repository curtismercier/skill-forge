# Maintenance — keeping skills current

The hardest part of a skill isn't building it. It's keeping it true six months later.

## The ERRATA lifecycle

Pattern from `jezweb/claude-skills/CLAUDE.md`:

1. **`active`** — you found drift. Upstream changed; the skill says X, the real answer is now Y. Add an entry to `ERRATA.md` at the top with status `active` and the correct value. Leave the main docs unchanged.

2. **`absorbed`** — after using the correction in real work (or after a stability window), fold it into the main docs. Flip the ERRATA entry to `absorbed`. Keep the entry — it's history.

3. **`outdated`** — the underlying thing changed *again*. Mark the old entry `outdated`, add a new `active` one above.

Why this over just editing the docs directly? Because direct edits lose the "how did we get here?" history. Six months from now, the next agent won't know whether your "correction" was right or was *itself* a hallucination. ERRATA preserves the chain.

## The ERRATA entry template

```markdown
## YYYY-MM-DD — <one-line summary of the drift>

**Status:** `active` | `absorbed` | `outdated`
**Location:** <file:lines>
**Drift:** <what the skill says and why it's wrong now>
**Correct value:** <what it should say>
**How to verify:** <specific command the next agent can run>
**How to fix when absorbing:** <the concrete edit>
```

The "How to verify" field is the most important. It turns one-off corrections into reproducible recipes.

## The verification playbook

Every Tier 3 skill should ship `docs/00-verification-playbook.md`. It should answer:

- What are the canonical repos for this domain?
- How do I check if a given fact is still true?
- Specific recipes: "is decorator X still valid?" → `gh_research.py find...`
- What are the signals that something has gone stale?
- When was this skill last fully audited?

Without a playbook, the next agent has to re-derive the research method from scratch every time. That's the goose-chase.

## The one-liner for quick staleness check

Every skill should include a "is this still current?" command in the SKILL.md:

```bash
python scripts/gh_research.py releases <primary-upstream>/<repo> 3
```

If the latest release postdates the "Last verified: YYYY-MM" line in the skill's top reference file, re-audit.

## Absorption timing

Don't rush absorption. An ERRATA entry should stay `active` until:

- You've used the correction in at least one real task, OR
- A week has passed without contradiction, OR
- The correction is trivially verifiable (e.g. a rename with a deprecation warning)

Absorbing too fast risks folding in a wrong "correction." Absorbing too late means docs and reality drift apart. A week is the right ceiling for most things.

## When to rewrite rather than patch

If more than ~30% of a skill's facts have drifted, don't keep patching via ERRATA. Do a full re-audit:

1. Re-run the research phase as if starting from scratch
2. Compare against current docs
3. Rewrite the affected references/docs
4. Leave ERRATA entries as `outdated` to mark what was superseded
5. Bump the "Last verified" date on all touched files

This is heavy lifting but necessary. The signal: when the ERRATA is longer than the docs it corrects, rewrite.

## Deprecation markers in the skill itself

If an API was renamed (e.g. `container_idle_timeout` → `scaledown_window`), leave a breadcrumb in the skill: a "Known issues" section or a note in the API reference that mentions the old name and the new one. Users arriving from old docs will grep for the old name; help them find the new.

## What not to maintain

Not everything needs aggressive maintenance:

- Concepts and explanations rarely need updates (cold-start mechanics don't change quarterly)
- Cost estimates need dating but infrequent full re-checks (quarterly is fine)
- API-specific details need the most attention (monthly spot-checks if the upstream is active)

Spend maintenance budget where it matters — the external-API integration points.
