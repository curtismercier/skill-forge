# Publish-Pending Skills

Five authored skills live in `~/.soma/skills/` with no home in this repo yet.
Each needs sanitization before publication here — personal paths, business references,
and environment-specific configs must be removed or generalized.

## Status

| Skill | Author | Sanitization needed | Complexity |
|---|---|---|---|
| **arzadon-content-seo** | curtismercier | Heavy — Arzadon Fitness brand voice, domain strategy, content calendar | Full rewrite for generic fitness/wellness |
| **closer-copywriting** | arzadon-fitness/curtis | Light — author field, a few business examples | Extract sales patterns from brand context |
| **designer-kit** | gravicity | Medium — Gravicity media tree paths, architecture rules | Parameterize brand paths, make scaffold generic |
| **protocols-authoring** | curtismercier | Medium — references to `gravicity/personal/protocols/` spec tree | Generalize spec root, remove personal examples |
| **website-master** | — (authored) | Light — audit-improve cycle tied to specific site portfolio | Make audit methodology brand-agnostic |
| **meta-fable** | sage/gravicity | Medium — LEDGER laws + laws.md provenance carry personal lessons (heightRatio, Somaverse commits); evolution.md §9 references local skill-forge path | Lives at `~/Gravicity/.claude/skills/meta-fable/`. Seed a generic LEDGER for publication; keep delta protocol + gates + tripwires/countersigns intact — they ARE the product |

## Sanitization checklist (each skill needs)

- [ ] `author:` field → neutral or template value
- [ ] `home-repo:` → point to this repo, not personal org
- [ ] Absolute file paths (`/Users/user/`, `/home/curtis/`) → `${HOME}/` or `~/`
- [ ] Business domains (`gravicity.ai`, `arzadon.com`, `meetsoma.ai`) → example.com or `$DOMAIN`
- [ ] Business-specific configs → environment variables or template placeholders
- [ ] Personal names (Curtis, Jay, Soma) → generic references

## DO NOT publish while these contain:

- Real client names or URLs
- Proprietary business logic
- Credentials, tokens, API keys
- Personal contact info

See `skill-forge/skill-forge/` for the meta-skill that governs the publication process.