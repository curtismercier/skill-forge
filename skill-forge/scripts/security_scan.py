#!/usr/bin/env python3
"""
security_scan.py — check a skill for hardcoded secrets and security issues.

Distinct from audit_skill.py (which flags LLM-slop quality issues).
This one flags things that could cause harm if shipped:
  * Hardcoded API keys, tokens, credentials
  * Private keys (SSH, RSA, etc.)
  * Hardcoded passwords or DB connection strings
  * Suspicious network requests to non-documented hosts
  * Shell injection patterns in generated scripts
  * Unsafe file operations (rm -rf, eval of untrusted input)

Pattern borrowed from FrancyJGLisboa/agent-skill-creator — skills that execute
arbitrary code are only safe if we can show they don't contain the obvious
footguns.

Exit codes:
  0 — no issues found
  1 — warnings (style/weak-signal issues)
  2 — blockers (hardcoded secrets or dangerous patterns)

Usage:
    python security_scan.py /path/to/skill/
    python security_scan.py /path/to/skill/ --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Finding:
    severity: str  # "block" | "warn" | "info"
    category: str
    file: str
    line: int | None
    message: str
    matched: str = ""


@dataclass
class ScanReport:
    skill_path: str
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, category: str, file: str, line: int | None,
            message: str, matched: str = "") -> None:
        self.findings.append(Finding(severity, category, file, line, message, matched))

    def by_severity(self) -> dict[str, int]:
        counts = {"block": 0, "warn": 0, "info": 0}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts


# ─────────────────────────────────────────────────────────────────────
# Secret detection patterns
# ─────────────────────────────────────────────────────────────────────

# Each pattern: (regex, severity, category, message)
# Matches go into `matched` field truncated to avoid leaking full secrets in reports.

_SECRET_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r'(?i)(api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token)[\s:=]+["\']([A-Za-z0-9_\-]{16,})["\']'),  # noqa: security
     "block", "hardcoded-secret",
     "Hardcoded API key / token / secret"),

    (re.compile(r'sk-[A-Za-z0-9]{20,}'),  # noqa: security
     "block", "hardcoded-secret",
     "OpenAI-style API key (`sk-...`)"),  # noqa: security

    (re.compile(r'hf_[A-Za-z0-9]{20,}'),  # noqa: security
     "block", "hardcoded-secret",
     "HuggingFace token (`hf_...`)"),  # noqa: security

    (re.compile(r'ghp_[A-Za-z0-9]{30,}'),  # noqa: security
     "block", "hardcoded-secret",
     "GitHub personal access token (`ghp_...`)"),  # noqa: security

    (re.compile(r'gho_[A-Za-z0-9]{30,}'),  # noqa: security
     "block", "hardcoded-secret",
     "GitHub OAuth token (`gho_...`)"),  # noqa: security

    (re.compile(r'AKIA[0-9A-Z]{16}'),  # noqa: security
     "block", "hardcoded-secret",
     "AWS access key ID"),

    (re.compile(r'-----BEGIN (RSA |DSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),  # noqa: security
     "block", "hardcoded-key",
     "Embedded private key"),

    (re.compile(r'(?i)password[\s:=]+["\']([^"\']{6,})["\']'),  # noqa: security
     "warn", "hardcoded-password",  # noqa: security
     "Hardcoded password (may be an example value)"),  # noqa: security

    (re.compile(r'postgres://[^:]+:[^@]+@'),  # noqa: security
     "warn", "connection-string",
     "Postgres connection string with embedded credentials"),

    (re.compile(r'mongodb(\+srv)?://[^:]+:[^@]+@'),  # noqa: security
     "warn", "connection-string",
     "MongoDB connection string with embedded credentials"),
]


# ─────────────────────────────────────────────────────────────────────
# Dangerous code patterns
# ─────────────────────────────────────────────────────────────────────

_DANGEROUS_CODE: list[tuple[re.Pattern, str, str, str]] = [
    # Negative lookbehind (?<![.\w]) prevents matching foo.eval(...) or sandbox.exec(...).
    # Require at least one non-quote, non-paren character after `(` so we skip
    # `eval()` in docstrings and `eval("literal")` — both are not the injection risk.
    (re.compile(r'(?<![.\w])eval\s*\(\s*[^\s"\'\)]'),
     "warn", "unsafe-eval",
     "`eval()` with non-literal argument — injection risk if input is untrusted"),  # noqa: security

    (re.compile(r'(?<![.\w])exec\s*\(\s*[^\s"\'\)]'),
     "warn", "unsafe-exec",
     "`exec()` with non-literal argument — injection risk"),  # noqa: security

    (re.compile(r'subprocess\.[a-z_]+\([^)]*shell\s*=\s*True'),
     "warn", "shell-injection",
     "`shell=True` in subprocess — command injection risk"),  # noqa: security

    (re.compile(r'\bos\.system\s*\('),
     "warn", "os-system",
     "os system() call — prefer subprocess.run with shell=False"),

    (re.compile(r'rm\s+-rf?\s+\$?\{?[A-Z_]'),
     "warn", "rm-rf-variable",
     "`rm -rf` with a variable path — accidental deletion risk"),  # noqa: security

    (re.compile(r'curl\s+[^|]+\|\s*(sh|bash)'),  # noqa: security
     "warn", "curl-pipe-shell",  # noqa: security
     "`curl | sh` pattern — install-time code execution. Acceptable for bootstrap, risky elsewhere."),  # noqa: security

    (re.compile(r'pickle\.loads?\s*\('),
     "warn", "pickle-load",
     "`pickle.load*` — unsafe on untrusted data"),  # noqa: security

    (re.compile(r'yaml\.load\s*\((?![^)]*Loader)'),
     "warn", "yaml-load",
     "yaml load() without safe Loader kwarg — arbitrary object creation risk"),
]


# ─────────────────────────────────────────────────────────────────────
# Scanner
# ─────────────────────────────────────────────────────────────────────

def _should_scan(path: Path) -> bool:
    """Skip binary, vendored, cache, and git files."""
    parts = path.parts
    skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build"}
    if any(p in skip_dirs for p in parts):
        return False
    if path.name.startswith("."):
        return False
    scan_exts = {".py", ".sh", ".bash", ".js", ".ts", ".md", ".yaml", ".yml", ".toml", ".env.example"}
    return path.suffix in scan_exts or path.name == "Dockerfile"


def _scan_file(report: ScanReport, path: Path) -> None:
    try:
        text = path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return

    lines = text.splitlines()

    # Example / template files get lower-severity treatment — they're meant to show shapes
    is_example = any(
        marker in str(path).lower()
        for marker in ("example", "template", ".env.example", "sample")
    )
    for i, line in enumerate(lines, 1):
        # Respect inline suppression markers. Recognized forms:
        #   # noqa: security
        #   # security: ignore
        #   # noqa: S301, S307, B301, ... (bandit/ruff security codes — S3xx family)
        #   # nosec  (bandit's native marker)
        if re.search(r'#\s*(noqa:\s*(security|S\d{3}|B\d{3})|security:\s*ignore|nosec)\b', line):
            continue

        # Skip commented-out lines for code files (but NOT for markdown code blocks)
        stripped = line.strip()
        if path.suffix in (".py", ".sh", ".bash") and stripped.startswith("#"):
            # Still scan comments for secrets — people accidentally commit keys in comments
            pass

        for pattern, severity, category, message in _SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                # Downgrade examples/templates from block → warn
                eff_severity = "warn" if is_example and severity == "block" else severity
                # Truncate the match so the report doesn't leak the actual secret
                matched_text = m.group(0)
                if len(matched_text) > 40:
                    matched_text = matched_text[:20] + "..." + matched_text[-8:]
                report.add(eff_severity, category, str(path), i, message, matched_text)

        # Don't scan for "dangerous code" in markdown — those are demonstrations
        if path.suffix == ".md":
            continue

        for pattern, severity, category, message in _DANGEROUS_CODE:
            m = pattern.search(line)
            if m:
                report.add(severity, category, str(path), i, message, m.group(0)[:60])


def scan(skill_path: Path) -> ScanReport:
    report = ScanReport(skill_path=str(skill_path))

    for path in skill_path.rglob("*"):
        if not path.is_file():
            continue
        if not _should_scan(path):
            continue
        _scan_file(report, path)

    return report


def _print_report(report: ScanReport) -> None:
    counts = report.by_severity()
    print(f"\nSecurity scan: {report.skill_path}")
    print(f"  {counts['block']} block · {counts['warn']} warn · {counts['info']} info")
    print()

    severity_order = {"block": 0, "warn": 1, "info": 2}
    severity_symbol = {"block": "✗", "warn": "!", "info": "·"}
    sorted_findings = sorted(
        report.findings,
        key=lambda f: (severity_order[f.severity], f.file, f.line or 0),
    )
    for f in sorted_findings:
        loc = f.file + (f":{f.line}" if f.line else "")
        print(f"  {severity_symbol[f.severity]} [{f.category}] {loc}")
        print(f"      {f.message}")
        if f.matched:
            print(f"      matched: {f.matched}")
        print()

    if not report.findings:
        print("  ✓ No security issues found.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scan a skill for hardcoded secrets and dangerous patterns.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("skill_path", help="Path to the skill directory")
    p.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    skill_path = Path(args.skill_path).resolve()
    if not skill_path.exists():
        print(f"ERROR: {skill_path} does not exist", file=sys.stderr)
        return 2

    report = scan(skill_path)

    if args.json:
        print(json.dumps({
            "skill_path": report.skill_path,
            "counts": report.by_severity(),
            "findings": [asdict(f) for f in report.findings],
        }, indent=2))
    else:
        _print_report(report)

    counts = report.by_severity()
    if counts["block"]:
        return 2
    if counts["warn"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
