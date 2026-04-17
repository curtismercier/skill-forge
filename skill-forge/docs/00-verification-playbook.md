# Verification playbook — how to audit skill-forge itself

**Audience:** the next Claude working on or updating skill-forge.

Skill-forge is itself a skill. It ships advice and tooling that can drift as:
- Anthropic evolves the skills format (new frontmatter fields, install paths)
- Community patterns emerge in awesome-claude-skills ecosystem
- Claude Code / Claude Desktop / claude.ai change install conventions
- Competing meta-skills ship novel ideas worth absorbing

This playbook tells you how to check if skill-forge's advice is still right.

## First principle

Ground truth for "how skills work" lives in **anthropics/skills** and in tools that have shipped serious production skills. If skill-forge says X and anthropics/skills or a popular community repo shows Y, the community repo wins.

## The three-source hierarchy for skill-creation advice

1. **anthropics/skills** — official repo. The `skill-creator` skill inside it is the primary canonical reference.
2. **Community skill-creators** with meaningful adoption — top hits:
   - `FrancyJGLisboa/agent-skill-creator` (354★, cross-platform, schema-drift detection)
   - `daymade/claude-code-skills` (production-hardened fork)
   - `metaskills/skill-builder` (98★, sub-agent conversion pattern)
   - `jezweb/claude-skills` (ERRATA lifecycle, progressive disclosure principles)
3. **awesome-claude-skills** indices — BehiSecc, travisvn, ComposioHQ. Good for spotting new patterns.

## Specific verification recipes

### "Is this still the correct SKILL.md frontmatter format?"
```bash
python scripts/gh_research.py read anthropics/skills skills/skill-creator/SKILL.md
# Compare frontmatter shape against skill-forge/references/skill-anatomy.md
```
Look for any new required fields, changed field names, or new optional fields (licensing, versioning, metadata blocks).

### "Are our install paths current?"
```bash
# Check Anthropic's official docs + VS Code / Claude Code plugin docs
# Key paths to verify still work:
#   ~/.claude/skills/
#   ~/.agents/skills/           (universal — Codex/Gemini/Kiro/Antigravity)
#   .cursor/rules/
#   Settings → Skills upload   (Claude Desktop / claude.ai)
```
If any path has moved, update `SKILL.md`'s install section and `references/skill-anatomy.md`.

### "Is our anti-slop list still the right list?"
```bash
# Read recent drafts from other people. Look at GitHub issues on community
# skill repos for "my skill hallucinated X" reports. Each new failure mode
# is a candidate for audit_skill.py.
python scripts/gh_research.py find <owner>/<repo> "hallucinated"
```
The heuristics file should grow over time. If it hasn't grown in 6+ months, either nothing's changed (unlikely) or we've stopped paying attention.

### "Are competing skill-creators shipping patterns we don't have?"
```bash
# Quarterly check: diff our feature set against the top community creators
python scripts/gh_research.py structure FrancyJGLisboa/agent-skill-creator
python scripts/gh_research.py structure daymade/claude-code-skills
python scripts/gh_research.py releases anthropics/skills 5
```
Novel patterns get considered for absorption. Not every pattern belongs here — skill-forge has a tier-based philosophy the other creators don't. Deliberate non-adoption is also fine.

### "Is gh_research.py's GitHub API usage still correct?"
The GitHub REST API is stable, but auth and rate-limit specifics change:
```bash
# Spot-check:
GITHUB_TOKEN=<your_token> python scripts/gh_research.py stats modal-labs/modal
# Should return JSON with name, stars, language, etc.
```
If the API call format breaks, check https://docs.github.com/rest for changes and update `gh_research.py` accordingly.

## How to tell if skill-forge has drifted

Signals that things below are stale:

- **anthropics/skills has added new required frontmatter fields** → update `validate_skill.py` and templates
- **A popular community creator ships a pattern we could absorb** → evaluate; if worth it, add an ERRATA entry and integrate
- **Install paths no longer match what users have** → update SKILL.md install section
- **`audit_skill.py` hasn't caught any new slop types in 6+ months** → look at recent drafts in awesome-claude-skills repos for new failure modes
- **Staleness-check schema-drift pattern needs new field types** (e.g. GraphQL shape checking) → extend `staleness_check.py`

When you find drift: log it in `ERRATA.md` with `active` status before editing the main docs. Keep the history.

## How this skill was originally audited

For the next agent's sanity:

1. Built initial version based on the Modal-vLLM skill experience (Tier 3 proof-of-concept)
2. Researched 6+ community skill-creators via web search
3. Fetched canonical docs from anthropics/skills and FrancyJGLisboa/agent-skill-creator
4. Folded in three novel patterns: staleness detection with schema drift, security scanning as separate pass, `--json` output contract consistency
5. Self-audited (ran `audit_skill.py` and `security_scan.py` against skill-forge itself)
6. Iterated until self-audit was clean or findings were intentional (illustrative examples suppressed with `<!-- noqa: audit -->` pragma)

**Time budget:** ~2 focused sessions. Future audits should be smaller — you're checking deltas, not rebuilding.

## The "is skill-forge still current?" one-liner

```bash
python scripts/gh_research.py releases anthropics/skills 3
python scripts/gh_research.py releases FrancyJGLisboa/agent-skill-creator 3
```

If either has a release newer than the "Last verified" marker at the top of `references/skill-anatomy.md`, re-audit those references and update as needed.

Last full audit: 2026-04-16.
