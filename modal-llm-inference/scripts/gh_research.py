#!/usr/bin/env python3
"""
gh_research.py — Scan GitHub repos without cloning, for Claude skill research.

Inspired by Curtis's soma-github.sh / soma-scrape.sh. Stdlib-only Python port
so it runs anywhere this skill lives, without bash/jq/gh dependencies.

Purpose: when investigating a question about Modal, vLLM, or any related tool,
use this BEFORE guessing at APIs. Ground truth lives in source trees, not in
model training data or search snippets.

Priority order for doc discovery (agent-authored files first, highest signal):
  CLAUDE.md > AGENTS.md > SKILL.md > llms.txt > llms-full.txt > README.md

Commands:
    gh_research.py structure <owner/repo>            Top-level tree with sizes
    gh_research.py tree <owner/repo>                 Full recursive file list
    gh_research.py read <owner/repo> <path>          Fetch raw file contents
    gh_research.py find <owner/repo> <pattern>       Search code via GitHub API
    gh_research.py docs <owner/repo>                 List doc files by priority
    gh_research.py stats <owner/repo>                Repo metadata (stars, lang, size)
    gh_research.py releases <owner/repo> [n]         Last N releases + changelogs

Environment:
    GITHUB_TOKEN    Optional. Raises API limit from 60/hr to 5000/hr.
    GH_BRANCH       Branch to scan (default: main, falls back to master/trunk)

Examples:
    # Before building a Modal skill, scan what's in Modal's own examples repo:
    python gh_research.py structure modal-labs/modal-examples
    python gh_research.py docs modal-labs/modal-examples
    python gh_research.py find modal-labs/modal-examples "requires_proxy_auth"
    python gh_research.py read modal-labs/modal-examples 07_web_endpoints/basic_web.py

    # Check for recent changes before trusting a cached approach:
    python gh_research.py releases modal-labs/modal 3
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any


DOC_PRIORITY = [
    "CLAUDE.md",
    "AGENTS.md",
    "SKILL.md",
    "llms.txt",
    "llms-full.txt",
    "README.md",
    "CONTRIBUTING.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
]
DOC_DIRS = ["docs", "doc", "documentation", "wiki", "guide", "guides", ".github"]


def _fetch(url: str, accept_json: bool = True) -> Any:
    req = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if accept_json:
        req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
        if accept_json:
            return json.loads(data)
        return data.decode("utf-8", errors="replace")


def _resolve_branch(repo: str, requested: str | None) -> str:
    """Pick a valid branch. Fall back from requested to default_branch, then to main/master."""
    if requested:
        return requested
    try:
        meta = _fetch(f"https://api.github.com/repos/{repo}")
        return meta.get("default_branch", "main")
    except Exception:
        return "main"


def cmd_structure(repo: str, branch: str | None = None) -> int:
    branch = _resolve_branch(repo, branch)
    tree = _fetch(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    blobs = [t for t in tree.get("tree", []) if t.get("type") == "blob"]
    if not blobs:
        print(f"No files found in {repo}@{branch}")
        return 1

    # Bucket by top-level directory
    by_top: dict[str, dict[str, Any]] = {}
    root: list[tuple[int, str]] = []
    for b in blobs:
        path, size = b["path"], b.get("size", 0)
        parts = path.split("/")
        if len(parts) == 1:
            root.append((size, path))
        else:
            top = parts[0]
            d = by_top.setdefault(top, {"files": 0, "bytes": 0, "exts": set()})
            d["files"] += 1
            d["bytes"] += size
            ext = parts[-1].rsplit(".", 1)[-1] if "." in parts[-1] else ""
            if ext:
                d["exts"].add(ext)

    print(f"\n📁 {repo}@{branch} — {len(blobs)} files total\n")
    for size, path in sorted(root):
        print(f"  {size:>10,}  {path}")
    print()
    for name in sorted(by_top):
        d = by_top[name]
        exts = ", ".join(sorted(d["exts"])[:5])
        print(f"  {d['bytes']:>10,}  {name}/ ({d['files']} files) [{exts}]")
    return 0


def cmd_tree(repo: str, branch: str | None = None) -> int:
    branch = _resolve_branch(repo, branch)
    tree = _fetch(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    print(f"\n🌳 {repo}@{branch}\n")
    for t in tree.get("tree", []):
        if t.get("type") == "blob":
            print(f"  {t.get('size', 0):>10,}  {t['path']}")
    return 0


def cmd_read(repo: str, path: str, branch: str | None = None) -> int:
    branch = _resolve_branch(repo, branch)
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        content = _fetch(url, accept_json=False)
    except urllib.error.HTTPError as e:
        print(f"Not found: {path} (HTTP {e.code})", file=sys.stderr)
        return 1
    print(content)
    return 0


def cmd_find(repo: str, pattern: str) -> int:
    q = urllib.parse.quote(f"{pattern} repo:{repo}")
    data = _fetch(f"https://api.github.com/search/code?q={q}&per_page=20")
    items = data.get("items", [])
    total = data.get("total_count", 0)
    print(f"\n🔍 '{pattern}' in {repo} — {total} results\n")
    for item in items:
        print(f"  {item.get('path', '')}")
    if total == 0:
        print("  (no matches — try a broader query, or the repo may be private)")
    return 0


def cmd_docs(repo: str, branch: str | None = None) -> int:
    """List all doc-relevant files in priority order — agent-authored first."""
    branch = _resolve_branch(repo, branch)
    tree = _fetch(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
    all_paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]

    print(f"\n📚 Doc files in {repo}@{branch} (priority order)\n")

    # Priority files at root
    print("  ── agent-authored & top-level ──")
    found_any = False
    for pf in DOC_PRIORITY:
        if pf in all_paths:
            print(f"  ✓  {pf}")
            found_any = True
    if not found_any:
        print("  (none at root — unusual; repo may use docs/ convention)")

    # Files in known doc directories
    print("\n  ── in doc directories ──")
    for d in DOC_DIRS:
        matches = [p for p in all_paths if p.startswith(f"{d}/") and
                   p.lower().endswith((".md", ".mdx", ".txt", ".rst"))]
        if matches:
            print(f"  {d}/ ({len(matches)} files)")
            for m in matches[:10]:
                print(f"    · {m}")
            if len(matches) > 10:
                print(f"    · ... ({len(matches) - 10} more)")
    return 0


def cmd_stats(repo: str) -> int:
    d = _fetch(f"https://api.github.com/repos/{repo}")
    print(f"\n📊 {d.get('full_name', repo)}")
    print(f"  Description:  {d.get('description', '')}")
    print(f"  Stars:        {d.get('stargazers_count', 0):,}")
    print(f"  Forks:        {d.get('forks_count', 0):,}")
    print(f"  Language:     {d.get('language', '?')}")
    print(f"  Size:         {d.get('size', 0):,} KB")
    print(f"  License:      {(d.get('license') or {}).get('spdx_id', 'none')}")
    print(f"  Updated:      {d.get('updated_at', '?')}")
    print(f"  Open issues:  {d.get('open_issues_count', 0)}")
    print(f"  Default br.:  {d.get('default_branch', '?')}")
    topics = d.get("topics", [])
    if topics:
        print(f"  Topics:       {', '.join(topics)}")
    return 0


def cmd_releases(repo: str, n: int = 5) -> int:
    releases = _fetch(f"https://api.github.com/repos/{repo}/releases?per_page={n}")
    if isinstance(releases, dict) and "message" in releases:
        print(f"Error: {releases['message']}", file=sys.stderr)
        return 1
    print(f"\n📋 Last {len(releases)} releases of {repo}\n")
    for r in releases:
        tag = r.get("tag_name", "?")
        date = (r.get("published_at") or "?")[:10]
        name = r.get("name", "") or ""
        body = (r.get("body") or "(no changelog)").strip()
        print(f"━━━ {tag} ({date}) {name} ━━━")
        for line in body.split("\n")[:30]:
            print(f"  {line}")
        extra = len(body.split("\n")) - 30
        if extra > 0:
            print(f"  ... ({extra} more lines)")
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    try:
        if cmd == "structure":
            return cmd_structure(argv[1])
        if cmd == "tree":
            return cmd_tree(argv[1])
        if cmd == "read":
            return cmd_read(argv[1], argv[2])
        if cmd == "find":
            return cmd_find(argv[1], argv[2])
        if cmd == "docs":
            return cmd_docs(argv[1])
        if cmd == "stats":
            return cmd_stats(argv[1])
        if cmd == "releases":
            n = int(argv[2]) if len(argv) > 2 else 5
            return cmd_releases(argv[1], n)
    except IndexError:
        print(f"Missing arguments for '{cmd}'. Run with --help for usage.", file=sys.stderr)
        return 2
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("GitHub API rate limit hit. Set GITHUB_TOKEN to raise limits to 5000/hr.",
                  file=sys.stderr)
        else:
            print(f"HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 1

    print(f"Unknown command: {cmd}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
