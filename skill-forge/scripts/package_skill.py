#!/usr/bin/env python3
"""
package_skill.py — zip a skill directory into a .skill archive.

Produces <name>.skill in the current directory (or --out).
Validates structure first (same rules as validate_skill.py).

Excludes: __pycache__, .DS_Store, .git, *.pyc

Usage:
    python package_skill.py /path/to/my-skill/
    python package_skill.py /path/to/my-skill/ --out /tmp/
    python package_skill.py /path/to/my-skill/ --skip-validate
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


# Import validation from the sibling script if available.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
try:
    from validate_skill import validate  # type: ignore
except ImportError:
    validate = None  # type: ignore


_EXCLUDE_DIR_NAMES = {"__pycache__", ".git", ".DS_Store", "node_modules", ".venv", "venv"}
_EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo"}
_EXCLUDE_FILE_NAMES = {".DS_Store"}


def _should_include(path: Path) -> bool:
    parts = path.parts
    if any(p in _EXCLUDE_DIR_NAMES for p in parts):
        return False
    if path.name in _EXCLUDE_FILE_NAMES:
        return False
    if path.suffix in _EXCLUDE_FILE_SUFFIXES:
        return False
    return True


def package(skill_path: Path, out_dir: Path, skip_validate: bool = False) -> Path:
    if not skip_validate and validate is not None:
        errors = validate(skill_path)
        if errors:
            print(f"Validation failed:", file=sys.stderr)
            for e in errors:
                print(f"  ✗ {e}", file=sys.stderr)
            raise SystemExit(1)

    name = skill_path.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.skill"

    if out_path.exists():
        out_path.unlink()

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(skill_path.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(skill_path.parent)  # include top dir
            if not _should_include(rel):
                continue
            z.write(path, arcname=str(rel))
            file_count += 1
            total_bytes += path.stat().st_size

    print(f"Packaged {name}")
    print(f"  {file_count} files · {total_bytes:,} bytes source")
    print(f"  → {out_path}  ({out_path.stat().st_size:,} bytes zipped)")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Package a skill directory into a .skill archive.")
    p.add_argument("skill_path", help="Path to the skill directory")
    p.add_argument("--out", default=".", help="Output directory (default: cwd)")
    p.add_argument("--skip-validate", action="store_true",
                   help="Skip validation (not recommended)")

    args = p.parse_args(argv)
    skill_path = Path(args.skill_path).resolve()
    if not skill_path.exists():
        print(f"ERROR: {skill_path} does not exist", file=sys.stderr)
        return 2

    out_dir = Path(args.out).resolve()
    package(skill_path, out_dir, skip_validate=args.skip_validate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
