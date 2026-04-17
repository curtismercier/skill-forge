# Why agent-authored files come first

**Last verified:** 2026-04-16.

The `gh_research.py docs` command scans in this priority order:

```
CLAUDE.md > AGENTS.md > SKILL.md > llms.txt > llms-full.txt > README.md > CONTRIBUTING.md > ARCHITECTURE.md > CHANGELOG.md
```

Then scans doc directories (`docs/`, `doc/`, `documentation/`, `.github/`) for `.md`/`.mdx`/`.rst`/`.txt` files.

## Why this order

**Agent-authored files (top of list)** are written for LLMs to read. They cut the noise, state the essentials, and usually follow a "what you need to know fast" structure. When a project has these, they're by definition the highest-signal intro.

- `CLAUDE.md` — Anthropic's convention (mostly used in Claude Code projects and agent-targeted skills)
- `AGENTS.md` — emerging industry-neutral convention, same idea
- `SKILL.md` — if the repo is itself a skill or includes skills, this is the meta
- `llms.txt` / `llms-full.txt` — emerging standard (Modal, Cloudflare, Anthropic, Jina, and many more publish these). The `-full.txt` variant concatenates everything an agent should know.

**Human-authored docs (middle tier)** are written for humans — README, CONTRIBUTING, ARCHITECTURE. Still valuable, but usually buried in narrative and marketing. Read after agent-authored files.

**Change logs and directories (bottom tier)** are useful for version-checking but not first-read material.

## What this priority gets you in practice

Running `docs modal-labs/modal-examples` returns agent-intended files first, which for Modal's example repo includes a `README.md` at the root and then surfaces each example's inline documentation. For projects that publish an `llms.txt`, that file alone often answers 80% of what an agent needs.

## When to deviate

If the user asks about a *specific file* they know exists (e.g. "show me their test runner"), skip the priority scan and just `read` the path. The priority order is for initial orientation.

## Pattern borrowed from

This priority list is drawn from Curtis's `soma-scrape.sh` toolkit (see his meetsoma repo). The SOMA tools do the same scanning pattern but with a richer UX including multi-provider discover across npm, MDN, and GitHub code search.
