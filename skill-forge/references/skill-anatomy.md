# Skill anatomy — what lives where and why

**Last verified:** 2026-04-16.

The canonical source is Anthropic's own skills repo: https://github.com/anthropics/skills. This doc synthesizes what they show plus patterns that have emerged in community skills.

## The three-tier complexity ladder

See `SKILL.md` for the summary table. The key insight: tier should match task, not aspiration. Over-building a skill is as costly as under-building one.

## Tier 1 — single-file skill

```
my-skill/
└── SKILL.md
```

The entire skill is one file with YAML frontmatter and markdown instructions. Appropriate when:

- The skill is a writing pattern, formatting rule, or prompt template
- It doesn't call external systems
- Advice is stable — doesn't drift monthly
- The instructions fit comfortably in 50-200 lines

Examples from the ecosystem:
- Many of Anthropic's example skills (e.g. specific writing-style skills) are Tier 1
- Most "meta-prompt" skills are Tier 1

## Tier 2 — scripts and/or references

```
my-skill/
├── SKILL.md
├── scripts/
│   └── helper.py
└── references/
    └── api-notes.md
```

Add `scripts/` when the skill needs to *run code during the session* — scraping, calling an API, checking a live fact. Not example code for the user (that goes in `examples/`), but tools the agent uses while executing the skill.

Add `references/` when the skill relies on external facts that need to be sourced and dated (APIs, pricing, version numbers).

Appropriate when:
- Domain is real but stable (facts don't shift weekly)
- Skill needs one or two runnable tools
- Advice is scoped enough that a verification playbook would be overkill

## Tier 3 — full system

```
my-skill/
├── SKILL.md
├── ERRATA.md
├── README.md
├── docs/
│   ├── 00-verification-playbook.md
│   ├── 01-foundation.md
│   └── ...
├── examples/
│   └── ...
├── references/
│   ├── skill-anatomy.md
│   └── ...
├── scripts/
│   ├── gh_research.py
│   └── ...
├── configs/
│   └── ...
└── sub-skill-name/              # sub-skills get their own SKILL.md
    ├── SKILL.md
    └── scripts/
```

Appropriate when:
- Upstream evolves faster than knowledge cutoffs track
- Multiple distinct workflows need their own treatment
- A "preflight" question ("is this doable?") precedes the main task — deserves a sub-skill
- Cost of drift is high — skill needs explicit self-healing

**Key file roles:**

- **`SKILL.md`** — the router. Keep it short. Decision trees pointing at docs and scripts, not tutorials.
- **`ERRATA.md`** — the drift log. See `references/errata-lifecycle.md` for the pattern.
- **`docs/00-verification-playbook.md`** — how the next agent audits the skill. This is the single most valuable file for long-lived skills.
- **`docs/NN-*.md`** — progressive-disclosure content. Each file is a focused concern; SKILL.md routes to the right one.
- **`references/`** — sourced facts with dates. API notes, verified pricing, known gotchas.
- **`scripts/`** — runnable tools, not examples. `gh_research.py` is standard for any external-API skill.
- **`examples/`** — user-facing example code they can adapt.
- **`configs/`** — if the skill has declarative configuration templates.
- **Sub-skills** — directories with their own `SKILL.md`. Loaded by Claude as separate skills. Use when a question is distinct enough that the user might want it independently.

## Sub-skills — when and how

A sub-skill is a sibling directory inside a skill with its own `SKILL.md`. It triggers independently. Use when:

- The sub-skill answers a different question than the main skill (example: `model-lookup` in the Modal skill answers "does this model exist and is it deployable?" — distinct from "how do I deploy?")
- The sub-skill might be useful on its own, not just as a prerequisite
- Keeping it separate lets Claude pull just the sub-skill for simple cases

Don't sub-skill for:
- A docs section that just needs its own file (that's `docs/`)
- A script that's part of the main workflow (that's `scripts/`)

## Progressive disclosure principle

Even in a Tier 3 skill, SKILL.md should be short. It should *route* the reader to the right doc, not contain the doc. This mirrors how Claude loads skills — metadata scanning first (just name + description), full content only when triggered. The same principle inside the skill: the main file should be scannable, detail pushed to files loaded on demand.

`jezweb/claude-skills/CLAUDE.md` puts this as: "the context window is a public good." Same idea.

## Anti-patterns

- **SKILL.md that's a tutorial.** Split it. SKILL.md is a router; tutorials go in docs/.
- **A single giant references/notes.md covering everything.** Split by topic. One reference file per distinct fact-cluster.
- **scripts/ with ten single-use scripts.** Consolidate. Each script should have a clear use case.
- **Empty ERRATA.md in a Tier 1 skill.** The ERRATA pattern is overhead. Only use it when you have drift to track.
- **Verification playbook with no verification recipes.** If you can't write specific recipes, you're not at Tier 3 yet — demote.

## Sources

- **Anthropic skills repo:** https://github.com/anthropics/skills — canonical source for the format
- **jezweb/claude-skills CLAUDE.md:** https://github.com/jezweb/claude-skills/blob/main/CLAUDE.md — ERRATA lifecycle, progressive disclosure, "context window is a public good"
- **awesome-claude-skills (BehiSecc):** https://github.com/BehiSecc/awesome-claude-skills — broad curated index
- **awesome-claude-skills (travisvn):** https://github.com/travisvn/awesome-claude-skills — includes skill-creator patterns
- **awesome-claude-skills (ComposioHQ):** https://github.com/ComposioHQ/awesome-claude-skills — canonical skill-creator SKILL.md
- **FrancyJGLisboa/agent-skill-creator:** https://github.com/FrancyJGLisboa/agent-skill-creator — staleness detection with schema drift, security scanning, cross-platform install, the `~/.agents/skills/` universal path convention
- **daymade/claude-code-skills:** https://github.com/daymade/claude-code-skills — production-hardened fork, "tells you what NOT to try" framing
- **metaskills/skill-builder:** https://github.com/metaskills/skill-builder — converting sub-agents to skills pattern
