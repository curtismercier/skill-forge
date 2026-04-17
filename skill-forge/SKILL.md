---
name: skill-forge
description: Build a Claude skill from scratch — scoped to the actual task, not over-engineered. Use whenever the person asks you to create a skill, a SKILL.md, an agent skill, or a Claude Code plugin. Also use when they want to audit, update, or refactor an existing skill. Scales output from a single-file skill to a full multi-layer system based on what the task actually needs. Includes source-first research (gh_research.py), anti-slop audits (audit_skill.py), and ERRATA-based drift tracking.
license: MIT
metadata:
  author: curtismercier
  version: "1.0.0"
  source-style: authored
  produced-by: authored
  home-repo: curtismercier/skill-forge
  created: 2026-04-16
  last_reviewed: 2026-04-16
  review_interval_days: 180
  dependencies:
    - name: anthropics/skills canonical repo
      url: https://github.com/anthropics/skills
    - name: GitHub API
      url: https://api.github.com
---

# skill-forge — build skills that fit the task

This skill helps you build other Claude skills. It is itself a skill, and it looks like the kind of skill it produces — that is the point.

**Where skill-forge sits:** [`gh skill`](https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/) (GitHub CLI) ships skills between repos and install dirs. Anthropic's [skills repo](https://github.com/anthropics/skills) documents the format that Claude Code, Claude Desktop, and claude.ai actually read. Skill-forge is the layer above that — the methodology for making skills that are actually good, not just format-compliant. All three compose. See `docs/09-ecosystem.md` for how skill-forge relates to these and to community alternatives.

**Core rule:** match the skill's complexity to the task. A haiku-helper doesn't need `ERRATA.md` and a verification playbook. A Modal-vLLM deployment skill does. Picking the wrong tier produces either fragile or bloated output.

## Step 1: classify the request on the complexity ladder

Before writing anything, classify the skill the person wants. Ask the person if the signal is ambiguous; don't guess.

| Tier | When | What it needs | Rough size |
|---|---|---|---|
| **1 — Single-file** | Formatting patterns, writing styles, prompt tricks, stable helpers | Just `SKILL.md` with frontmatter + instructions | 50-200 lines, 1 file |
| **2 — With scripts/references** | CLI wrappers, API helpers, doc generators, anything that needs verified facts or runnable tools | `SKILL.md` + `scripts/` and/or `references/` | 5-15 files |
| **3 — Full system** | Rapidly-evolving upstream (Modal, vLLM, cloud APIs), multi-stage workflows, anything needing sub-skills or drift tracking | Everything above + `docs/` + `ERRATA.md` + verification playbook + sub-skill directories | 20-80+ files |

**If in doubt, start at the lower tier and upgrade.** You can add `ERRATA.md` later; you can't easily remove an over-built structure without confusing future maintainers.

Decision signals:

- **Does the domain change faster than your knowledge cutoff handles well?** → Tier 3. You need drift tracking.
- **Does the skill need to run code during its own use** (e.g. scraping docs, hitting APIs to verify facts)? → Tier 2 or 3.
- **Is this a one-off pattern that doesn't touch external systems?** → Tier 1.
- **Will the skill have distinct "is this doable?" vs "how do I do it?" questions?** → Tier 3, with sub-skills.

## Step 2: research before you draft

**Never generate code for an external system from training knowledge alone.** Fabricated APIs are the #1 failure mode. See `references/anti-slop-heuristics.md` for the specific patterns to avoid.

For Tier 2 and Tier 3 skills, run `scripts/gh_research.py` against the canonical source:

```bash
python scripts/gh_research.py structure <owner>/<repo>
python scripts/gh_research.py docs <owner>/<repo>      # priority: CLAUDE.md, AGENTS.md, SKILL.md, llms.txt, llms-full.txt, README.md
python scripts/gh_research.py find <owner>/<repo> "<api name>"
python scripts/gh_research.py read <owner>/<repo> <path>
python scripts/gh_research.py releases <owner>/<repo>  # check for recent breaking changes
```

Also fetch `<domain>/llms.txt` or `<domain>/llms-full.txt` if the tool publishes one — Modal, Cloudflare, Anthropic, and a growing list of tool makers publish these specifically for agents.

For Tier 1 skills (stable, internal patterns), you can skip research.

## Step 3: scaffold the skill

Use `scripts/new_skill.py` to generate the starting directory:

```bash
python scripts/new_skill.py --tier 2 --name my-new-skill --domain "what the skill covers"
```

This creates the right directory structure for the tier with placeholder files keyed to the skill's purpose. Fill them in, don't over-scaffold.

## Step 4: draft the SKILL.md

The SKILL.md is the triggering artifact. Its description determines whether Claude reaches for the skill at all. See `references/description-tuning.md` for the pushy-description pattern.

Short SKILL.md wins. Long SKILL.md with a decision tree pointing at sub-docs beats long SKILL.md that tries to teach everything inline. This file you're reading is an example.

## Step 5: audit before shipping

Three independent passes. Each has its own exit-code contract: 0=clean, 1=warnings, 2=blockers.

```bash
# Anti-slop — LLM hallucination patterns (suspicious numbers, stale markers, etc.)
python scripts/audit_skill.py /path/to/my-skill/

# Security — hardcoded secrets, dangerous patterns
python scripts/security_scan.py /path/to/my-skill/

# Structural — frontmatter, parse-ability, required files
python scripts/validate_skill.py /path/to/my-skill/
```

Every flag is a recommendation, not a hard stop — you review each one. `--json` on any of them gives machine-readable output for CI.

## Step 6: package

```bash
python scripts/package_skill.py /path/to/my-skill/
```

Produces `<name>.skill` — a zip archive ready to install.

## Step 7: maintain with staleness detection

For Tier 2 and 3 skills, add frontmatter metadata so the skill can tell when it's drifted:

```yaml
---
name: my-skill
description: ...
metadata:
  created: 2026-04-16
  last_reviewed: 2026-04-16
  review_interval_days: 90
  dependencies:
    - name: Some API
      url: https://api.example.com/v1/health
  schema_expectations:
    - url: https://api.example.com/v1/items
      method: GET
      expected_keys: [id, name, created_at]
---
```

Then periodic staleness checks:

```bash
python scripts/staleness_check.py /path/to/my-skill/                    # review-age only
python scripts/staleness_check.py /path/to/my-skill/ --check-deps       # HTTP-check declared URLs
python scripts/staleness_check.py /path/to/my-skill/ --check-drift      # fetch & compare JSON shapes
```

Schema drift catches the case where an API still responds 200 but silently changed its response shape — the most dangerous kind of drift because nothing visibly breaks.

## Install location

Skill-forge is a standard Claude skill — directory with a `SKILL.md` at its root. Install it however you install any skill.

**Option A — GitHub CLI (if you have `gh` v2.90.0+):**
```bash
gh skill install <your-owner>/skill-forge
# Or target a specific agent:
gh skill install <your-owner>/skill-forge --agent claude-code
```

**Option B — Direct clone (works without any extra tools):**
```bash
# Claude Code + VS Code Copilot (one install, both tools)
git clone https://github.com/<your-owner>/skill-forge.git ~/.claude/skills/skill-forge

# Universal path (Codex CLI, Gemini CLI, Kiro, Antigravity)
git clone https://github.com/<your-owner>/skill-forge.git ~/.agents/skills/skill-forge

# Cursor (per-project)
git clone https://github.com/<your-owner>/skill-forge.git .cursor/rules/skill-forge
```

**Option C — Claude Desktop / claude.ai:**
Download the `.skill` archive from Releases, then Settings → Skills → Upload.

Skill-forge does not require `gh skill` — every capability works with a plain `git clone`. When `gh skill` is present, we defer to it for install ergonomics and version pinning. See `docs/09-ecosystem.md` for the full picture of how skill-forge relates to `gh skill`, Anthropic's skills, and community alternatives.

Skill-forge sits alongside Anthropic's official `skill-creator` — both can be installed at once. Use skill-forge when you want the tier-based approach, explicit anti-slop audits, and staleness tracking. Use the official one when you want Anthropic's supported flow.

## Progressive disclosure — read the right doc

- New to skill-making? → `docs/01-foundation.md`
- Stuck on "should this be a skill at all?" → `docs/02-planning.md`
- Building a Tier 2 or 3 skill? → `docs/03-research-phase.md` is mandatory reading
- Worried about LLM slop in your draft? → `docs/05-anti-slop.md` (short), `references/anti-slop-heuristics.md` (full)
- Skill already built, how to keep it current? → `docs/08-maintenance.md`
- Where does skill-forge sit vs `gh skill`, spec, Anthropic's creator? → `docs/09-ecosystem.md`

## Reference skills

- `examples/tier1-minimal/` — what a Tier 1 skill looks like, end to end
- `examples/tier2-with-scripts/` — Tier 2 example
- `examples/tier3-reference-excerpt/` — excerpts from the Modal LLM Inference skill showing full system structure (full version at its own install location)

## Self-healing

This skill has an `ERRATA.md` tracking drift in the advice itself. Anthropic's own skill guidance evolves; community patterns shift. When you find something in here that doesn't match current best practice, log it in ERRATA before editing.

To check if this skill is still current:
```bash
python scripts/gh_research.py releases anthropics/skills 3
# If the latest release postdates the "Verified" line at the top of references/skill-anatomy.md,
# re-audit those references.
```
