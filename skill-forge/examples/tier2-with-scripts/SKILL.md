---
name: gh-research
description: Scan GitHub repos without cloning them — structure, file trees, function maps, code search, recent releases. Use whenever the user wants to investigate a repository before writing code against its APIs, check how recently a project has been updated, find where a function or pattern is defined, or map a codebase for documentation. Ideal for pre-generation research to avoid hallucinating APIs.
---

# gh-research — scan GitHub repos before you build

A Tier 2 skill: ships a script the agent runs during the session, plus references explaining how to read the output.

## When to use this skill

Any time the agent is about to write code against an external library or SDK. Always use this *before* generating code for an unfamiliar domain.

## The core tool

```bash
python scripts/gh_research.py structure <owner>/<repo>          # top-level file tree
python scripts/gh_research.py docs <owner>/<repo>               # doc files in priority order
python scripts/gh_research.py find <owner>/<repo> "<pattern>"   # code search
python scripts/gh_research.py read <owner>/<repo> <filepath>    # fetch raw file
python scripts/gh_research.py releases <owner>/<repo> 3         # recent releases
python scripts/gh_research.py stats <owner>/<repo>              # metadata
```

Set `GITHUB_TOKEN` in the environment to raise rate limits from 60/hr to 5000/hr.

## Typical flow

1. **Orient** — `structure <repo>` to see what's there
2. **Find docs** — `docs <repo>` (returns files in agent-priority order: CLAUDE.md, AGENTS.md, SKILL.md, llms.txt, llms-full.txt, README.md)
3. **Zoom in** — `read <repo> <file>` on the 1-2 most relevant files
4. **Verify specific APIs** — `find <repo> "<function name>"` before citing them
5. **Check recency** — `releases <repo>` to see if cached knowledge is still current

## Key reference

- `references/priority-order.md` — why agent-authored files come first in the doc scan

## Next steps for ambitious users

If you're building an agent workflow that repeatedly hits several repos, consider forking this into a Tier 3 skill with a local cache and diff-tracking. The basic tool here is the 80/20.
