# Ecosystem — where skill-forge sits

**Last verified:** 2026-04-16.

The Claude/agent skills ecosystem has several overlapping tools as of April 2026. This doc explains what each one does, where they overlap, and when to reach for which.

## The three layers

```
┌─────────────────────────────────────────────────────────────┐
│  skill-forge — methodology layer                            │
│  tier ladder · anti-slop audits · ERRATA lifecycle          │
│  verification playbook · content-drift detection            │
├─────────────────────────────────────────────────────────────┤
│  gh skill (GitHub CLI) — distribution layer (optional)      │
│  install · search · publish · update · tree-SHA versioning  │
├─────────────────────────────────────────────────────────────┤
│  Anthropic's SKILL.md format — what clients actually read   │
│  Claude Code · Claude Desktop · claude.ai · compatible hosts │
└─────────────────────────────────────────────────────────────┘
```

Each layer does one thing. Anthropic's format is what Claude clients parse. GitHub ships the skills (if you choose to use it). Skill-forge makes them good.

## Anthropic's SKILL.md format

The [anthropics/skills](https://github.com/anthropics/skills) repo documents and demonstrates the format. A skill is a directory with a `SKILL.md` at the root containing YAML frontmatter (at minimum `name` and `description`) plus Markdown instructions. Optional directories are `scripts/`, `references/`, and `assets/`.

This is the format Claude Code, Claude Desktop, and claude.ai actually parse. Every other tool — `gh skill`, skill-forge, community skill-creators — works with files in this shape.

**skill-forge conforms to this format.** Scaffolds produced by `new_skill.py` are format-compliant. Our `validate_skill.py` checks the frontmatter rules. For an authoritative reference, read Anthropic's own [`skill-creator` skill](https://github.com/anthropics/skills/tree/main/skills/skill-creator) inside that repo.

### What about agentskills.io?

A related effort at [agentskills.io](https://agentskills.io) proposes a cross-vendor "open spec" formalizing the same format for multi-vendor adoption. It's worth watching but hasn't yet established itself as *the* spec the ecosystem treats as canonical — the format itself originated at Anthropic and Anthropic's repo remains the practical source of truth. skill-forge doesn't take a position on which name prevails; we target the format, wherever it's documented.

## gh skill — the GitHub CLI (optional)

[`gh skill`](https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/) shipped on April 16, 2026 as part of GitHub CLI v2.90.0+. It provides:

- `gh skill install owner/repo [skill-name]` — install to the right directory for your agent
- `gh skill search <query>` — discover skills across GitHub
- `gh skill publish` — validate and publish your repo's skills
- `gh skill update [--all]` — check for upstream changes via tree SHA comparison
- `gh skill preview` — inspect a skill before installing

**skill-forge does not depend on `gh skill`.** A user without GitHub CLI installed can still use every skill-forge tool, and anyone can install skill-forge-produced skills via `git clone` to the right directory. `gh skill` is one install path among several — when the user has it, use it; when they don't, the manual path works identically.

### Where `gh skill` and skill-forge complement each other

| Concern | `gh skill` handles | skill-forge handles |
|---|---|---|
| Installation ergonomics | Yes (one command) | Fallback (git clone) |
| Version pinning | Yes (via `--pin`) | No |
| Tree-SHA version drift detection | Yes (via `gh skill update`) | Complementary — content drift (see below) |
| Format validation | Not directly | Yes (`validate_skill.py`) |
| Methodology, tier selection | No | Yes (this is the whole point) |
| Anti-slop audits | No | Yes |
| Source-first research tooling | No | Yes (`gh_research.py`) |
| ERRATA drift tracking | No | Yes |
| Schema-drift detection (upstream API changed shape) | No | Yes (`staleness_check.py --check-drift`) |

The split is clean: `gh skill` is a package manager. skill-forge is a quality and methodology toolkit. A skill author uses both; a skill consumer mostly just needs `gh skill` (or a `git clone`).

## Anthropic's skill-creator

[`anthropics/skills/tree/main/skills/skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator) is Anthropic's official skill-creator skill. It's the reference implementation — canonical, supported, and a great starting point.

skill-forge takes an opinionated stance that Anthropic's creator doesn't:

- **Tier ladder.** Anthropic's creator treats every skill roughly the same; skill-forge explicitly scales output to complexity.
- **Mandatory research phase for Tier 2/3.** Anthropic's creator trusts the user to verify APIs; skill-forge ships `gh_research.py` and treats source-first as non-negotiable.
- **ERRATA and drift tracking.** Anthropic's creator doesn't address maintenance; skill-forge makes it a first-class concern.
- **Anti-slop audits.** Anthropic's creator validates structure; skill-forge also audits for hallucinated-content patterns.

Both can be installed at once. Use skill-forge when you want structured methodology; use Anthropic's when you want the supported baseline.

## Community skill-creators we've learned from

- [FrancyJGLisboa/agent-skill-creator](https://github.com/FrancyJGLisboa/agent-skill-creator) — staleness detection with schema drift, `~/.agents/skills/` universal path, security scanning as separate pass
- [jezweb/claude-skills](https://github.com/jezweb/claude-skills) — ERRATA lifecycle, progressive disclosure as "context window is a public good"
- [daymade/claude-code-skills](https://github.com/daymade/claude-code-skills) — production-hardened framing, "tells you what NOT to try"
- [metaskills/skill-builder](https://github.com/metaskills/skill-builder) — sub-agent to skill conversion pattern

When these ship new patterns, skill-forge evaluates them for absorption. See `ERRATA.md` for the lifecycle.

## Decision tree — which tool should I reach for?

```
Want to install a skill someone else wrote?
  Have gh CLI? → gh skill install owner/repo [name]
  Don't?       → git clone owner/repo ~/.claude/skills/name

Want to write a new skill?
  → skill-forge: python scripts/new_skill.py --tier N --name ...

Want to check if the SKILL.md is format-valid?
  → skill-forge: python validate_skill.py ./skill/
  (Delegates to `skills-ref` if you happen to have it installed;
   our own checks run otherwise. Neither is strictly authoritative —
   the real authority is whether Claude clients parse and use it.)

Want to check if my skill is high-quality (not just format-valid)?
  → skill-forge: python scripts/audit_skill.py ./skill/

Want to publish my skill so others can gh-skill-install it?
  → gh skill publish    (validates, offers immutable releases)

Want to check if my skill has drifted?
  → gh skill update (tree-SHA version drift)
  AND skill-forge: python staleness_check.py --check-drift (API content drift)
```

The tools are complementary. They can all be used together, and none is strictly required.
