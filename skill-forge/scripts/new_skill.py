#!/usr/bin/env python3
"""
new_skill.py — scaffold a Claude skill directory at the right complexity tier.

Tiers (from skill-forge's SKILL.md):
  1: single-file SKILL.md only
  2: SKILL.md + scripts/ and/or references/
  3: full system with docs/, ERRATA.md, verification playbook, sub-skills

Usage:
    python new_skill.py --tier 1 --name haiku-helper
    python new_skill.py --tier 2 --name my-api-wrapper --domain "Some API"
    python new_skill.py --tier 3 --name modal-llm-inference --domain "Modal + vLLM deployment"

Creates the directory in the current working directory by default, or use --out.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parent / "templates"


def _read_template(name: str) -> str:
    """Read a template file if it exists, else return an empty string.
    Templates are used as starting content; if missing, we fall back to minimal defaults
    so this script works even if templates haven't been shipped."""
    path = TEMPLATES / name
    return path.read_text() if path.exists() else ""


def _fill(template: str, **fields: str) -> str:
    """Minimal template fill — replaces {{KEY}} with fields[KEY]. No escaping magic."""
    for k, v in fields.items():
        template = template.replace(f"{{{{{k}}}}}", v)
    return template


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  created: {path}")


# ──────────────────────────────────────────────────────────────
# Tier builders
# ──────────────────────────────────────────────────────────────

def _skill_md_for(tier: int, name: str, domain: str,
                  license: str = "", compatibility: str = "") -> str:
    """Generate a starter SKILL.md appropriate to the tier.

    Conforms to the Claude SKILL.md format documented at
    https://github.com/anthropics/skills

    Frontmatter fields:
      - name: required, kebab-case, 1-64 chars
      - description: required, 1-1024 chars, pushy & specific
      - license: optional, license name or bundled file reference
      - compatibility: optional, environment requirements
      - metadata: optional, arbitrary key-value (we use it for staleness tracking)
      - allowed-tools: optional (experimental per the spec — not auto-added)
    """
    today = date.today().isoformat()
    description = (
        f"Skill for {domain}. " if domain else ""
    ) + (
        f"Use whenever the user mentions {name} or asks for help with related tasks. "
        f"Replace this description with something specific and pushy — see "
        f"references/description-tuning.md for the pattern."
    )

    # Build frontmatter in the spec's recommended order.
    frontmatter_lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
    ]
    if license:
        frontmatter_lines.append(f"license: {license}")
    if compatibility:
        frontmatter_lines.append(f"compatibility: {compatibility}")

    # For Tier 2/3, include the metadata block scaffold so staleness_check has something to read.
    if tier >= 2:
        frontmatter_lines.extend([
            "metadata:",
            f"  created: {today}",
            f"  last_reviewed: {today}",
            "  review_interval_days: 90",
            "  # dependencies:",
            "  #   - name: Example API",
            "  #     url: https://api.example.com/v1/health",
            "  # schema_expectations:",
            "  #   - url: https://api.example.com/v1/items",
            "  #     method: GET",
            "  #     expected_keys: [id, name, created_at]",
        ])

    frontmatter_lines.append("---")
    frontmatter = "\n".join(frontmatter_lines) + "\n"

    base = frontmatter + f"""
# {name}

<!-- Replace this with a one-line what-this-skill-does. Keep SKILL.md short;
     push detail into referenced files for tier 2/3 skills.
     Per spec, keep this file under ~500 lines. -->

## When to use this skill

<!-- Be specific. What triggers this skill? What does it NOT cover? -->

## Core pattern

<!-- The single most important thing the user should know. 3-10 lines.
     If you can't say it in 10 lines, you probably need a docs/ folder (tier 3). -->

"""

    if tier == 1:
        return base + """## How

<!-- A Tier 1 skill ends here. If you need scripts or references, you're
     Tier 2 — re-scaffold with --tier 2. -->
"""

    if tier == 2:
        return base + f"""## Scripts available in this skill

<!-- List runnable tools the agent uses during the session.
     Not examples for the user — actual tools the skill uses. -->

```bash
# Example:
python scripts/<tool>.py --help
```

## Key references

- `references/<topic>.md` — (describe what's in here)

## Verification

Last audited: {today}. When using this skill after a long gap, check:
- Is the upstream API still what we documented? (spot-check one call)
- Have any scripts been updated? (git log scripts/)
"""

    # tier == 3
    return base + f"""## Quick navigation

- `docs/01-foundation.md` — concepts
- `docs/02-...` — next decision point

## Research before building

<!-- If this skill touches external APIs, the agent MUST run gh_research.py
     before generating code. Keep this section and its commands. -->

```bash
python scripts/gh_research.py structure <owner>/<repo>
python scripts/gh_research.py find <owner>/<repo> "<api name>"
```

## Self-healing

- `docs/00-verification-playbook.md` — how the next agent audits this
- `ERRATA.md` — drift log, `active/absorbed/outdated` lifecycle

```bash
# Is this skill still current?
python scripts/gh_research.py releases <owner>/<repo> 3
# If newer than the "Verified: YYYY-MM" line in references/<name>-notes.md,
# re-audit.
```

Last audited: {today}.
"""


def _tier1(out: Path, name: str, domain: str, license: str = "", compatibility: str = "") -> None:
    skill_md = _skill_md_for(1, name, domain, license=license, compatibility=compatibility)
    _write(out / "SKILL.md", skill_md)


def _tier2(out: Path, name: str, domain: str, license: str = "", compatibility: str = "") -> None:
    skill_md = _skill_md_for(2, name, domain, license=license, compatibility=compatibility)
    _write(out / "SKILL.md", skill_md)

    _write(out / "scripts" / "README.md",
           f"# Scripts for {name}\n\nRunnable tools the agent uses during a session.\n"
           "Not user-facing examples — those go in `examples/`.\n")

    _write(out / "references" / f"{name}-notes.md",
           f"""# {name} — verified notes

**Last verified:** {date.today().isoformat()}

Ground-truth notes verified against the canonical source. When anything in this
skill says "do X", the authority for why is here.

## Source

<!-- GitHub repo URL, docs URL, or both -->

## API notes

<!-- Add verified notes as you confirm them. Date each major section. -->
""")


def _tier3(out: Path, name: str, domain: str, license: str = "", compatibility: str = "") -> None:
    skill_md = _skill_md_for(3, name, domain, license=license, compatibility=compatibility)
    _write(out / "SKILL.md", skill_md)

    today = date.today().isoformat()

    # Scaffold a CLAUDE.md at the skill root using the bundled template.
    # Auto-loaded by Claude Code when anyone works in this skill's directory.
    claude_md = _claude_md_for(name, domain)
    if claude_md:
        _write(out / "CLAUDE.md", claude_md)

    _write(out / "ERRATA.md", _errata_starter(name, today))

    _write(out / "docs" / "00-verification-playbook.md",
           _playbook_starter(name, domain, today))

    _write(out / "docs" / "01-foundation.md",
           f"# {name} — Foundation\n\n## Purpose\n\n<!-- concepts and architecture -->\n")

    _write(out / "scripts" / "README.md",
           f"# Scripts for {name}\n\n"
           "Every tier-3 skill should include `gh_research.py` "
           "(copy from skill-forge's scripts/) for source-first research.\n")

    _write(out / "references" / f"{name}-notes.md",
           f"""# {name} — verified API notes

**Last verified:** {today}.

## Canonical sources

<!-- List the repos and doc URLs you're sourcing from -->

## Verified API notes

<!-- Date each major section as you verify it -->
""")

    _write(out / "examples" / "README.md",
           f"# Examples for {name}\n\n"
           "Runnable example code the skill's user can adapt. "
           "Each example should have inline comments citing the canonical source.\n")


def _claude_md_for(name: str, domain: str) -> str:
    """Load the CLAUDE.md template and fill in skill-specific placeholders.
    Returns empty string if the template isn't present (graceful fallback:
    tier-3 scaffolding still works, just without the CLAUDE.md)."""
    template = _read_template("CLAUDE.md.template")
    if not template:
        return ""
    return _fill(template,
                 NAME=name,
                 DOMAIN=domain or "<!-- describe this skill's purpose in 1-2 sentences -->")


def _errata_starter(name: str, today: str) -> str:
    return f"""# ERRATA — {name}

Drift log. Pattern borrowed from [jezweb/claude-skills](https://github.com/jezweb/claude-skills/blob/main/CLAUDE.md).

**Lifecycle:** `active` (drift found, correction here) → `absorbed` (folded into main docs) → `outdated` (the thing changed again; new `active` entry replaces this one).

Add new entries at the top.

---

## {today} — scaffold initialized

**Status:** `absorbed`
**Location:** this skill was generated fresh.
**Drift:** none yet; populated by `skill-forge/scripts/new_skill.py`.
**Next review:** when the first external API call here breaks or feels stale.

---

## Template for new entries

```markdown
## YYYY-MM-DD — <one-line summary>

**Status:** `active` | `absorbed` | `outdated`
**Location:** <files:lines>
**Drift:** <what the skill says, why it's wrong>
**Correct value:** <what it should say>
**How to verify:** <specific command or URL>
**How to fix when absorbing:** <concrete edit>
```
"""


def _playbook_starter(name: str, domain: str, today: str) -> str:
    return f"""# {name} — verification playbook

**Audience:** the next Claude working on this skill.

## First principle

Ground truth lives in source trees. If your training data disagrees with the canonical repo at HEAD, the repo wins.

## Verification hierarchy

1. **<Tool>'s llms.txt** if they publish one
2. **Canonical repo source** via `scripts/gh_research.py`
3. **Official HTML docs** via `web_fetch`

## Canonical repos for this skill

<!-- List the repos this skill sources facts from. Example:
- `owner/repo` — what's there
-->

## Specific verification recipes

<!-- As you confirm API points, add recipes here so the next agent doesn't re-derive. -->

### "Is this API still valid?"
```bash
python scripts/gh_research.py find <owner>/<repo> "<api name>"
```

## How to tell if a fact in this skill is stale

- <signal specific to the domain>
- Error messages that suggest removed APIs
- Version pins older than the "Verified:" marker

Last verified: {today}. Domain: {domain or 'not specified'}.
"""


# ──────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scaffold a new Claude skill at the right complexity tier. Conforms to the SKILL.md format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--tier", type=int, required=True, choices=[1, 2, 3],
                   help="Complexity tier: 1=single file, 2=scripts/refs, 3=full system")
    p.add_argument("--name", required=True,
                   help="Skill directory name (kebab-case, 1-64 chars per spec)")
    p.add_argument("--domain", default="",
                   help="What the skill covers (one phrase, shows up in description)")
    p.add_argument("--license", default="",
                   help="Optional: SPDX license identifier (e.g. MIT, Apache-2.0)")
    p.add_argument("--compatibility", default="",
                   help="Optional: environment requirements (e.g. 'Requires Python 3.12+')")
    p.add_argument("--out", default=".",
                   help="Parent directory (default: cwd)")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing directory with the same name")

    args = p.parse_args(argv)

    # Validate name against spec: kebab-case, 1-64 chars, no consecutive hyphens, no leading/trailing hyphen
    import re
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", args.name) or len(args.name) > 64:
        print(f"ERROR: '{args.name}' is not a valid skill name.", file=sys.stderr)
        print("  Must be: 1-64 chars, lowercase, digits, hyphens only, no consecutive hyphens.", file=sys.stderr)
        return 1

    out = Path(args.out) / args.name

    if out.exists() and not args.force:
        print(f"ERROR: {out} already exists. Use --force to overwrite.", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)

    print(f"Creating Tier {args.tier} skill: {args.name}")
    print(f"  at: {out}")
    print()

    kwargs = {"license": args.license, "compatibility": args.compatibility}
    if args.tier == 1:
        _tier1(out, args.name, args.domain, **kwargs)
    elif args.tier == 2:
        _tier2(out, args.name, args.domain, **kwargs)
    else:
        _tier3(out, args.name, args.domain, **kwargs)

    print()
    print("Next steps:")
    print(f"  1. Edit {out}/SKILL.md — make the description specific and pushy")
    if args.tier >= 2:
        print(f"  2. For external-API skills, run: python scripts/gh_research.py ... to verify your plan")
        print(f"  3. Populate references/*.md with sourced facts")
    if args.tier == 3:
        print(f"  4. Fill in docs/01-foundation.md with concepts")
    print(f"  5. Run audit_skill.py {out} before shipping")
    print(f"  6. Run validate_skill.py {out} to check structure")
    print(f"  7. Publish: gh skill publish   OR   package_skill.py {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
