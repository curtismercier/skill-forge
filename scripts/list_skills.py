#!/usr/bin/env python3
"""
list_skills.py — walk the monorepo and emit the skill index from SKILL.md frontmatter.

Usage:
    python3 scripts/list_skills.py              # prints markdown table to stdout
    python3 scripts/list_skills.py --json       # emit as JSON
    python3 scripts/list_skills.py --update     # rewrite the <!-- SKILLS_INDEX --> block in root README.md

Walks the repo root looking for */SKILL.md (one level deep only — the monorepo convention).
Parses YAML-like frontmatter without pulling in pyyaml. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_frontmatter(text: str) -> dict:
    """Minimal YAML-ish frontmatter parser. Handles nested metadata one level deep."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    body = m.group(1)

    fields: dict = {}
    current_key: str | None = None
    nested: dict | None = None

    for raw in body.splitlines():
        line = raw.rstrip()
        if not line:
            continue

        # Nested key (indented with 2 spaces)
        if line.startswith("  ") and nested is not None:
            sub = line.strip()
            if ":" in sub:
                k, _, v = sub.partition(":")
                nested[k.strip()] = v.strip().strip('"').strip("'")
            continue

        # Top-level key
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                # Nested block starts
                nested = {}
                fields[key] = nested
                current_key = key
            else:
                fields[key] = value.strip('"').strip("'")
                nested = None
                current_key = key

    return fields


def discover_skills(repo_root: Path) -> list[dict]:
    """Return list of {dir, name, description, version, author, produced_by, source_style}."""
    skills: list[dict] = []
    for child in sorted(repo_root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in {"scripts", "contrib"}:
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            fm = _parse_frontmatter(skill_md.read_text())
        except OSError:
            continue
        if not fm.get("name"):
            continue
        metadata = fm.get("metadata", {}) if isinstance(fm.get("metadata"), dict) else {}
        skills.append({
            "dir": child.name,
            "name": fm.get("name", child.name),
            "description": fm.get("description", ""),
            "license": fm.get("license", ""),
            "version": metadata.get("version", "—"),
            "author": metadata.get("author", "—"),
            "produced_by": metadata.get("produced-by", metadata.get("produced_by", "—")),
            "source_style": metadata.get("source-style", metadata.get("source_style", "—")),
        })
    return skills


def _short(text: str, max_len: int = 140) -> str:
    """Truncate for table display."""
    text = text.replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def render_markdown(skills: list[dict]) -> str:
    """Produce a markdown table of skills."""
    if not skills:
        return "_No skills discovered._"

    lines = [
        "| Skill | Version | Install | Description |",
        "|-------|---------|---------|-------------|",
    ]
    for s in skills:
        name = s["name"]
        install = f"`gh skill install curtismercier/skill-forge {name}`"
        lines.append(
            f"| [`{name}`](./{s['dir']}/) | `{s['version']}` | {install} | {_short(s['description'], 120)} |"
        )
    return "\n".join(lines)


def update_readme(readme_path: Path, skills: list[dict]) -> bool:
    """Replace the content between <!-- SKILLS_INDEX --> markers in the README.

    Returns True if the README was modified, False if no markers were found or no change needed.
    """
    if not readme_path.exists():
        print(f"ERROR: {readme_path} does not exist", file=sys.stderr)
        return False

    text = readme_path.read_text()
    start_marker = "<!-- SKILLS_INDEX -->"
    end_marker = "<!-- /SKILLS_INDEX -->"

    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print(
            f"WARNING: markers {start_marker} and {end_marker} not found in {readme_path}; "
            f"not updating.",
            file=sys.stderr,
        )
        return False

    new_block = f"{start_marker}\n{render_markdown(skills)}\n{end_marker}"
    new_text = text[:start_idx] + new_block + text[end_idx + len(end_marker):]

    if new_text == text:
        return False

    readme_path.write_text(new_text)
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="Output as JSON instead of markdown")
    p.add_argument("--update", action="store_true", help="Rewrite the <!-- SKILLS_INDEX --> block in root README.md")
    p.add_argument("--root", default=str(REPO_ROOT), help="Monorepo root (default: parent of this script)")
    args = p.parse_args(argv)

    root = Path(args.root).resolve()
    skills = discover_skills(root)

    if args.json:
        print(json.dumps(skills, indent=2))
        return 0

    if args.update:
        updated = update_readme(root / "README.md", skills)
        if updated:
            print(f"Updated skill index in {root / 'README.md'}")
        else:
            print(f"No change to {root / 'README.md'}")
        return 0

    print(render_markdown(skills))
    return 0


if __name__ == "__main__":
    sys.exit(main())
