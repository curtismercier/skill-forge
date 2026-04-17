# Foundation — what a Claude skill is

A Claude skill is a directory with a `SKILL.md` file that teaches Claude how to handle a specific kind of request. Claude scans available skill descriptions and loads the full content of a skill only when it matches the current user request — progressive disclosure at the skill level.

The skill itself can be anywhere on the complexity ladder (Tier 1, 2, or 3 — see `SKILL.md` in skill-forge's root). The common elements:

## The minimum viable skill

A directory with exactly one file:

```
my-skill/
└── SKILL.md
```

The `SKILL.md` has YAML frontmatter (at minimum `name` and `description`) followed by markdown instructions. That's it — a skill with nothing else is perfectly valid if the task doesn't need more.

## Frontmatter

```yaml
---
name: my-skill
description: A pushy, specific description that includes trigger words for when Claude should reach for this skill.
---
```

- `name`: kebab-case, matches the directory name
- `description`: what triggers the skill (see `references/description-tuning.md`)

Optional fields (not universally supported, use sparingly):
- `license`: SPDX identifier
- `version`: semver string
- `tags`: list of tags

## How Claude chooses to use a skill

During a conversation, Claude sees the `name` and `description` of every available skill. When the user's request matches a skill's description, Claude loads the full `SKILL.md` content. If the skill has scripts or references, those are loaded on demand as the main file points at them.

This means:
- **Description writes determine triggering.** A beautiful skill with a timid description won't get used.
- **SKILL.md length doesn't block triggering.** But it does consume context once loaded, so keep it focused.
- **Deeper files only load when referenced.** A 50-page reference doc in `references/` costs nothing until Claude actually reads it.

## Where detail goes

- **Single-line fact** → SKILL.md
- **Decision tree** → SKILL.md (short)
- **Tutorial or explanation** → `docs/*.md`, loaded via SKILL.md link
- **Verified API reference** → `references/*.md`, dated and sourced
- **Code the agent runs** → `scripts/*.py`
- **Code the user copies** → `examples/*.py`
- **Known drift** → `ERRATA.md`
- **How to audit this skill** → `docs/00-verification-playbook.md`

See `references/skill-anatomy.md` for the full breakdown.

## Next: what tier should your skill be?

Read `docs/02-planning.md`.
