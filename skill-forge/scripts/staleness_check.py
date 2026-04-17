#!/usr/bin/env python3
"""
staleness_check.py — detect content-drift in a skill.

Complementary to `gh skill update`, not a replacement:

  gh skill update     → detects VERSION drift (tree SHA of source directory changed)
  staleness_check.py  → detects CONTENT drift (upstream world changed, even if skill's SKILL.md didn't)

The dangerous case this catches: the skill hasn't been edited in six months,
so `gh skill update` thinks it's fine. But the API it documents silently
changed its response shape, or the pricing page it cites moved, or the
dependency endpoint it relies on now returns 404. Those are *content* drifts —
the world shifted under a skill that sat still.

Three layers, each opt-in via frontmatter `metadata:`:

  1. REVIEW TRACKING
     Skill declares `metadata.last_reviewed` and `metadata.review_interval_days`.
     Compare to today; flag if overdue.

  2. DEPENDENCY HEALTH (--check-deps)
     Skill declares `metadata.dependencies` (list of URLs).
     HTTP-check each. 4xx/5xx/timeout = dependency unreachable.

  3. SCHEMA DRIFT (--check-drift)
     Skill declares `metadata.schema_expectations` (endpoint + expected keys).
     Fetch endpoint, parse JSON, compare top-level keys against expected.
     Missing keys = the API changed shape under you.

Pattern from FrancyJGLisboa/agent-skill-creator. Re-implemented here stdlib-only
so skill-forge has no pip dependencies.

Exit codes:
  0 — fresh (no drift detected)
  1 — overdue for review (but no active dependency or schema breaks)
  2 — dependency unreachable OR schema drift detected (real drift)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path


_FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


def _parse_frontmatter_yaml(text: str) -> dict:
    """Minimal YAML-ish parser for our frontmatter metadata.
    Supports: string values, lists of strings, nested objects (one level).
    Good enough for `metadata` blocks; not a full YAML parser."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}

    result: dict = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue

        if not line.startswith(" ") and ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest:
                # scalar value
                result[key] = rest.strip('"').strip("'")
            else:
                # nested block or list follows
                block, consumed = _parse_block(lines, i + 1, indent=2)
                result[key] = block
                i += consumed
        i += 1
    return result


def _parse_block(lines: list[str], start: int, indent: int = 2) -> tuple[object, int]:
    """Parse a nested block starting at `start`. Returns (value, lines_consumed)."""
    i = start
    collected_dict: dict = {}
    collected_list: list = []
    mode: str | None = None  # "dict" or "list"

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if not line.startswith(" " * indent):
            break

        content = line[indent:]
        if content.startswith("- "):
            mode = "list"
            item_content = content[2:].strip()
            if ":" in item_content and not item_content.startswith("http"):
                # list of dicts: first key-value on same line, rest nested
                key, _, rest = item_content.partition(":")
                item_dict = {key.strip(): rest.strip().strip('"').strip("'")}
                # Look ahead for more keys at deeper indent
                sub, consumed = _parse_block(lines, i + 1, indent=indent + 2)
                if isinstance(sub, dict):
                    item_dict.update(sub)
                collected_list.append(item_dict)
                i += 1 + consumed
                continue
            else:
                collected_list.append(item_content.strip('"').strip("'"))
                i += 1
                continue

        if ":" in content:
            mode = "dict"
            key, _, rest = content.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest:
                collected_dict[key] = rest.strip('"').strip("'")
                i += 1
            else:
                sub, consumed = _parse_block(lines, i + 1, indent=indent + 2)
                collected_dict[key] = sub
                i += 1 + consumed
        else:
            break

    if mode == "list":
        return collected_list, i - start
    return collected_dict, i - start


# ─────────────────────────────────────────────────────────────────────
# Layer 1: review tracking
# ─────────────────────────────────────────────────────────────────────

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _check_review_age(metadata: dict) -> tuple[str, str]:
    """Returns (status, message) where status is 'fresh', 'overdue', or 'unknown'."""
    last_reviewed = _parse_date(metadata.get("last_reviewed"))
    interval = metadata.get("review_interval_days")
    try:
        interval_days = int(interval) if interval else 90
    except (ValueError, TypeError):
        interval_days = 90

    if last_reviewed is None:
        return "unknown", f"No `last_reviewed` date in frontmatter; can't compute staleness. (Default interval would be {interval_days} days.)"

    age = (date.today() - last_reviewed).days
    if age > interval_days:
        return "overdue", f"{age} days since last_reviewed ({last_reviewed.isoformat()}); interval is {interval_days} days."
    return "fresh", f"{age} days since last_reviewed ({last_reviewed.isoformat()}); {interval_days - age} days until next review."


# ─────────────────────────────────────────────────────────────────────
# Layer 2: dependency health
# ─────────────────────────────────────────────────────────────────────

def _check_url(url: str, timeout: float = 8.0) -> tuple[bool, int | str]:
    """HEAD or GET the URL; return (ok, status_code_or_error)."""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "skill-forge-staleness-check/1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (resp.status < 400, resp.status)
    except urllib.error.HTTPError as e:
        # Some servers don't support HEAD; retry with GET
        if e.code in (400, 405, 501):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "skill-forge-staleness-check/1"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return (resp.status < 400, resp.status)
            except Exception as e2:
                return (False, str(e2))
        return (False, e.code)
    except Exception as e:
        return (False, str(e))


def _check_dependencies(metadata: dict) -> list[tuple[str, str, str]]:
    """Return list of (name, url, status_msg) tuples for unreachable deps."""
    deps = metadata.get("dependencies") or []
    if not isinstance(deps, list):
        return []

    issues: list[tuple[str, str, str]] = []
    for dep in deps:
        if isinstance(dep, dict):
            url = dep.get("url", "")
            name = dep.get("name", url)
        else:
            url = str(dep)
            name = url
        if not url:
            continue

        ok, status = _check_url(url)
        if not ok:
            issues.append((name, url, str(status)))
    return issues


# ─────────────────────────────────────────────────────────────────────
# Layer 3: schema drift
# ─────────────────────────────────────────────────────────────────────

def _fetch_json(url: str, method: str = "GET", timeout: float = 10.0) -> tuple[bool, dict | list | str]:
    try:
        req = urllib.request.Request(url, method=method, headers={
            "User-Agent": "skill-forge-staleness-check/1",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return (True, json.loads(raw))
            except json.JSONDecodeError as e:
                return (False, f"Response not valid JSON: {e}")
    except Exception as e:
        return (False, str(e))


def _check_schema_drift(metadata: dict) -> list[tuple[str, str, list[str]]]:
    """Return list of (url, reason, missing_keys) tuples for drift issues."""
    expectations = metadata.get("schema_expectations") or []
    if not isinstance(expectations, list):
        return []

    issues: list[tuple[str, str, list[str]]] = []
    for spec in expectations:
        if not isinstance(spec, dict):
            continue
        url = spec.get("url", "")
        method = spec.get("method", "GET").upper()
        expected = spec.get("expected_keys") or []
        if not url or not expected:
            continue

        ok, data = _fetch_json(url, method=method)
        if not ok:
            issues.append((url, f"Fetch failed: {data}", []))
            continue

        # Handle response being wrapped (e.g. { data: {...} }) — check top level of returned object
        if isinstance(data, list):
            issues.append((url, "Response is a list; expected object to check top-level keys", []))
            continue
        if not isinstance(data, dict):
            issues.append((url, f"Response is {type(data).__name__}; expected object", []))
            continue

        actual_keys = set(data.keys())
        missing = [k for k in expected if k not in actual_keys]
        if missing:
            issues.append((url, f"Missing keys in response", missing))

    return issues


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

@dataclass
class StalenessReport:
    skill_path: str
    review_status: str = "unknown"
    review_message: str = ""
    dependency_issues: list = field(default_factory=list)
    drift_issues: list = field(default_factory=list)


def check(skill_path: Path, check_deps: bool = False, check_drift: bool = False) -> tuple[StalenessReport, int]:
    report = StalenessReport(skill_path=str(skill_path))

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        report.review_status = "error"
        report.review_message = f"No SKILL.md at {skill_path}"
        return report, 2

    frontmatter = _parse_frontmatter_yaml(skill_md.read_text())
    metadata = frontmatter.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    # Layer 1
    status, msg = _check_review_age(metadata)
    report.review_status = status
    report.review_message = msg

    # Layer 2
    if check_deps:
        report.dependency_issues = _check_dependencies(metadata)

    # Layer 3
    if check_drift:
        report.drift_issues = _check_schema_drift(metadata)

    exit_code = 0
    if status == "overdue":
        exit_code = max(exit_code, 1)
    if report.dependency_issues:
        exit_code = max(exit_code, 2)
    if report.drift_issues:
        exit_code = max(exit_code, 2)

    return report, exit_code


def _print_report(report: StalenessReport) -> None:
    print(f"\nStaleness check: {report.skill_path}\n")

    symbol = {"fresh": "✓", "overdue": "!", "unknown": "?", "error": "✗"}.get(report.review_status, "·")
    print(f"  [review] {symbol} {report.review_status.upper()}")
    print(f"    {report.review_message}")
    print()

    if report.dependency_issues:
        print(f"  [dependencies] ✗ {len(report.dependency_issues)} unreachable")
        for name, url, status in report.dependency_issues:
            print(f"    · {name}: {url}")
            print(f"        {status}")
        print()

    if report.drift_issues:
        print(f"  [schema-drift] ✗ {len(report.drift_issues)} endpoints with issues")
        for url, reason, missing in report.drift_issues:
            print(f"    · {url}")
            print(f"        {reason}")
            if missing:
                print(f"        missing top-level keys: {', '.join(missing)}")
        print()

    if report.review_status == "fresh" and not report.dependency_issues and not report.drift_issues:
        print("  ✓ All good.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Detect staleness in a skill.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("skill_path", help="Path to the skill directory")
    p.add_argument("--check-deps", action="store_true",
                   help="HTTP-check declared dependencies")
    p.add_argument("--check-drift", action="store_true",
                   help="Fetch declared endpoints and check for schema drift")
    p.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    skill_path = Path(args.skill_path).resolve()
    if not skill_path.exists():
        print(f"ERROR: {skill_path} does not exist", file=sys.stderr)
        return 2

    report, exit_code = check(skill_path,
                               check_deps=args.check_deps,
                               check_drift=args.check_drift)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        _print_report(report)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
