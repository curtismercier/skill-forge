#!/usr/bin/env python3
"""
validate_skill.py — structural validation of a skill directory.

When the `skills-ref` reference validator happens to be on PATH,
this script delegates to it. When `skills-ref` isn't available, this script
runs its own lightweight checks so validation still works in any environment.
The practical authority for "is this valid?" is whether Claude clients parse
and use it — these checks approximate that.

What the fallback checks:
  1. SKILL.md exists at the root
  2. SKILL.md has valid YAML frontmatter with `name` and `description`
  3. `name` conforms to the spec: kebab-case, 1-64 chars, no leading/trailing
     hyphens, no consecutive hyphens
  4. `description` is non-empty and <=1024 chars (spec limit)
  5. Any Python in scripts/ parses without errors
  6. Sub-skill directories (folders with their own SKILL.md) have valid
     frontmatter too

Returns non-zero if any rule fails.

Usage:
    python validate_skill.py /path/to/skill/
    python validate_skill.py /path/to/skill/ --no-delegate    # force fallback
    python validate_skill.py /path/to/skill/ --json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str] | None:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    fields: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for line in m.group(1).splitlines():
        if line and not line.startswith(" ") and ":" in line:
            if key is not None:
                fields[key] = "\n".join(buf).strip()
            key, _, rest = line.partition(":")
            key = key.strip()
            buf = [rest.strip()]
        else:
            buf.append(line)
    if key is not None:
        fields[key] = "\n".join(buf).strip()
    return fields


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _check_name(name: str) -> str | None:
    """Validate `name` per the SKILL.md format rules. Returns error string or None."""
    if not name:
        return "is empty"
    if len(name) > 64:
        return f"is {len(name)} chars, max is 64"
    if len(name) < 1:
        return "is too short (min 1 char)"
    if name.startswith("-") or name.endswith("-"):
        return "must not start or end with a hyphen"
    if "--" in name:
        return "must not contain consecutive hyphens"
    if not _NAME_RE.match(name):
        return "must be lowercase alphanumeric with hyphens only"
    return None


def _try_skills_ref(skill_path: Path) -> tuple[bool, str] | None:
    """If `skills-ref` is on PATH, run it and return (ok, stdout). Else None."""
    if shutil.which("skills-ref") is None:
        return None
    try:
        result = subprocess.run(
            ["skills-ref", "validate", str(skill_path)],
            capture_output=True, text=True, timeout=30,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return (result.returncode == 0, output.strip())
    except (subprocess.SubprocessError, OSError) as e:
        return (False, f"skills-ref invocation failed: {e}")


def validate(skill_path: Path) -> list[str]:
    """Run the fallback validator — our in-tree checks. Used when skills-ref
    isn't available, or when the caller explicitly requests no delegation."""
    errors: list[str] = []

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        errors.append(f"Missing SKILL.md at skill root: {skill_path}")
        return errors

    fm = _parse_frontmatter(skill_md.read_text())
    if fm is None:
        errors.append(f"{skill_md}: missing YAML frontmatter (---...---)")
    else:
        name = fm.get("name", "")
        name_err = _check_name(name)
        if name_err:
            errors.append(f"{skill_md}: `name: {name}` {name_err}")

        desc = fm.get("description", "")
        if not desc:
            errors.append(f"{skill_md}: frontmatter missing or empty `description`")
        elif len(desc) > 1024:
            errors.append(f"{skill_md}: `description` is {len(desc)} chars (spec max 1024)")

        # compatibility is optional but has a length cap per spec
        compat = fm.get("compatibility", "")
        if compat and len(compat) > 500:
            errors.append(f"{skill_md}: `compatibility` is {len(compat)} chars (spec max 500)")

    # Check sub-skills (directories with their own SKILL.md)
    for child in skill_path.iterdir():
        if not child.is_dir():
            continue
        sub = child / "SKILL.md"
        if sub.exists():
            sub_fm = _parse_frontmatter(sub.read_text())
            if sub_fm is None:
                errors.append(f"{sub}: sub-skill missing YAML frontmatter")
            else:
                sub_name_err = _check_name(sub_fm.get("name", ""))
                if sub_name_err:
                    errors.append(f"{sub}: sub-skill `name` {sub_name_err}")
                if not sub_fm.get("description"):
                    errors.append(f"{sub}: sub-skill missing `description`")

    # Parse all Python files
    for py in skill_path.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            ast.parse(py.read_text())
        except SyntaxError as e:
            errors.append(f"{py}:{e.lineno}: Python syntax error: {e.msg}")

    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Validate a skill's structure against the Claude SKILL.md format.")
    p.add_argument("skill_path", help="Path to the skill directory")
    p.add_argument("--no-delegate", action="store_true",
                   help="Skip skills-ref delegation even if available; use fallback checks only")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of prose")
    args = p.parse_args(argv)

    skill_path = Path(args.skill_path).resolve()
    if not skill_path.exists():
        print(f"ERROR: {skill_path} does not exist", file=sys.stderr)
        return 2

    # Prefer the official validator when available.
    if not args.no_delegate:
        ref_result = _try_skills_ref(skill_path)
        if ref_result is not None:
            ok, output = ref_result
            if args.json:
                print(json.dumps({
                    "skill_path": str(skill_path),
                    "validator": "skills-ref",
                    "ok": ok,
                    "output": output,
                }, indent=2))
            else:
                label = "skills-ref" if ok else "skills-ref FAILED"
                print(f"[{label}] {skill_path}")
                if output:
                    print(output)
            return 0 if ok else 1

    # Fall back to our in-tree checks
    errors = validate(skill_path)

    if args.json:
        print(json.dumps({
            "skill_path": str(skill_path),
            "validator": "skill-forge fallback",
            "ok": not errors,
            "errors": errors,
        }, indent=2))
        return 1 if errors else 0

    if errors:
        print(f"Validation FAILED for {skill_path} (skill-forge fallback)")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    print(f"Validation passed for {skill_path} (skill-forge fallback checks; install `skills-ref` to cross-check)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
