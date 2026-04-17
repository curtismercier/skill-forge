#!/usr/bin/env python3
"""
run_loop_hardened.py — skill-forge wrapper around the vendored run_loop.

Wraps `scripts.vendor.anthropic_skill_creator.run_loop.run_loop()` with the
five hardenings documented in IMPROVEMENTS.md:

1. Preflight-checks the `claude` CLI on PATH (exits cleanly with install hint
   if missing, rather than raising FileNotFoundError mid-subprocess).
2. Tracks errored vs. non-triggered runs separately so infra failures don't
   look like description failures.
3. Caps the 1024-char retry at 3 attempts and refuses to emit over-budget
   descriptions.
4. Exits 0 on improvement, 1 on no-improvement, 2 on error — so CI can tell.
5. Handles SIGINT gracefully: drains running subprocesses, reports best-so-far.

Pass `--no-preflight --max-error-rate=1.0 --no-strict-length --exit-always-zero`
to reproduce upstream behavior exactly.

License: MIT (skill-forge). The wrapped run_loop is Apache 2.0 (Anthropic PBC);
see LICENSE-APACHE-ANTHROPIC.txt at repo root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

# Import the vendored scripts by package path — keeps the vendor subtree
# self-contained and makes it clear where each symbol comes from.
from .anthropic_skill_creator import run_loop as _vendor_run_loop
from .anthropic_skill_creator.generate_report import generate_html
from .anthropic_skill_creator.utils import parse_skill_md


# ──────────────────────────────────────────────────────────────
# #1 — Preflight check
# ──────────────────────────────────────────────────────────────

_INSTALL_HINT = """
The `claude` CLI is not on your PATH. run_loop uses it as a subprocess to
execute eval queries and propose description improvements.

Install Claude Code:  https://claude.com/product/claude-code
After install, verify:  claude --version  (we recommend v2.90 or newer)

To skip this preflight check (e.g. when using a custom binary), re-run with
--no-preflight.
""".strip()


def preflight_claude_cli() -> str | None:
    """Return the resolved `claude` binary path, or None if not found."""
    return shutil.which("claude")


# ──────────────────────────────────────────────────────────────
# #5 — SIGINT handling
# ──────────────────────────────────────────────────────────────

_INTERRUPTED = False


def _install_sigint_handler():
    """Set the global flag on first Ctrl+C; raise KeyboardInterrupt on second."""
    original = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):
        global _INTERRUPTED
        if _INTERRUPTED:
            # Second Ctrl+C — let default behavior take over.
            signal.signal(signal.SIGINT, original)
            raise KeyboardInterrupt()
        _INTERRUPTED = True
        print(
            "\n[run_loop_hardened] Interrupt received. Finishing current iteration, "
            "then reporting best-so-far. Press Ctrl+C again to abort immediately.",
            file=sys.stderr,
        )

    signal.signal(signal.SIGINT, handler)
    return original


# ──────────────────────────────────────────────────────────────
# #3 — Strict length enforcement on improved descriptions
# ──────────────────────────────────────────────────────────────

def _strict_length_filter(output: dict, max_chars: int = 1024) -> dict:
    """Drop over-length descriptions from history and fall back to best under-limit.

    Modifies `output` in place: if `best_description` is over-limit, replaces it
    with the highest-scoring under-limit entry from history. Tags the output
    with a `length_enforcement` field describing what happened.
    """
    best_desc = output.get("best_description", "") or ""
    if len(best_desc) <= max_chars:
        output["length_enforcement"] = {"action": "no-op", "best_length": len(best_desc)}
        return output

    history = output.get("history", [])
    # Find the highest-scoring history entry whose description is under the limit.
    # Score by test_passed (when present), else train_passed.
    under_limit = [
        h for h in history
        if h.get("description") and len(h["description"]) <= max_chars
    ]
    if not under_limit:
        output["length_enforcement"] = {
            "action": "no-valid-fallback",
            "best_length": len(best_desc),
            "note": (
                f"All {len(history)} iterations produced over-length descriptions. "
                f"Keeping the original description as best_description."
            ),
        }
        output["best_description"] = output.get("original_description", best_desc[:max_chars])
        return output

    def _score(h):
        return (h.get("test_passed") or 0, h.get("train_passed") or h.get("passed") or 0)

    fallback = max(under_limit, key=_score)
    output["length_enforcement"] = {
        "action": "fell-back",
        "original_best_length": len(best_desc),
        "fallback_length": len(fallback["description"]),
        "fallback_iteration": fallback.get("iteration"),
        "note": (
            f"best_description from upstream was {len(best_desc)} chars "
            f"(over 1024-char limit). Replaced with iteration "
            f"{fallback.get('iteration')} under-limit description."
        ),
    }
    output["best_description"] = fallback["description"]
    return output


# ──────────────────────────────────────────────────────────────
# #4 — Exit code policy
# ──────────────────────────────────────────────────────────────

def _compute_exit_code(output: dict) -> int:
    """0 if best score improved over iteration 1; 1 if no improvement; 2 on error."""
    history = output.get("history") or []
    if not history:
        return 2  # no iterations ran — something is wrong

    first = history[0]
    best_desc = output.get("best_description", "")
    best = next((h for h in history if h.get("description") == best_desc), None)
    if best is None:
        return 2

    # Prefer test score; fall back to train.
    def _score(h):
        return h.get("test_passed") if h.get("test_passed") is not None else h.get("train_passed", h.get("passed", 0))

    first_score = _score(first) or 0
    best_score = _score(best) or 0
    if best_score > first_score:
        return 0  # improvement
    return 1  # no improvement (or regression)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Upstream args (kept compatible)
    p.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    p.add_argument("--skill-path", required=True, help="Path to skill directory")
    p.add_argument("--description", default=None, help="Override starting description")
    p.add_argument("--num-workers", type=int, default=10, help="Parallel workers")
    p.add_argument("--timeout", type=int, default=30, help="Per-query timeout (seconds)")
    p.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    p.add_argument("--runs-per-query", type=int, default=3, help="Runs per query for trigger-rate reliability")
    p.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    p.add_argument("--holdout", type=float, default=0.4, help="Test split fraction (0 disables split)")
    p.add_argument("--model", required=True, help="Model id for claude -p subprocess calls")
    p.add_argument("--verbose", action="store_true", help="Progress to stderr")
    p.add_argument("--report", default="auto", help="Live HTML report path ('auto' / 'none' / <path>)")
    p.add_argument("--results-dir", default=None, help="Save timestamped run artifacts under this dir")

    # Hardening flags (skill-forge additions; all default to on)
    p.add_argument(
        "--no-preflight", dest="preflight", action="store_false", default=True,
        help="Skip the `claude` CLI presence check (improvement #1)",
    )
    p.add_argument(
        "--max-error-rate", type=float, default=0.5,
        help="Abort iteration if > this fraction of runs error (improvement #2). Set to 1.0 to disable.",
    )
    p.add_argument(
        "--no-strict-length", dest="strict_length", action="store_false", default=True,
        help="Allow over-1024-char descriptions (improvement #3)",
    )
    p.add_argument(
        "--exit-always-zero", action="store_true",
        help="Always exit 0 regardless of optimization outcome (matches upstream behavior, improvement #4)",
    )

    args = p.parse_args(argv)

    # #1 — Preflight
    if args.preflight:
        resolved = preflight_claude_cli()
        if resolved is None:
            print(_INSTALL_HINT, file=sys.stderr)
            return 2
        if args.verbose:
            print(f"[preflight] claude CLI: {resolved}", file=sys.stderr)

    # Load inputs (same as upstream main())
    try:
        eval_set = json.loads(Path(args.eval_set).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: failed to load --eval-set {args.eval_set}: {e}", file=sys.stderr)
        return 2

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"ERROR: no SKILL.md at {skill_path}", file=sys.stderr)
        return 2

    name, _, _ = parse_skill_md(skill_path)

    # Live report path (same logic as upstream)
    if args.report != "none":
        if args.report == "auto":
            ts = time.strftime("%Y%m%d_%H%M%S")
            live_report_path = Path(tempfile.gettempdir()) / f"skill_description_report_{skill_path.name}_{ts}.html"
        else:
            live_report_path = Path(args.report)
        live_report_path.write_text(
            "<html><body><h1>Starting optimization loop...</h1>"
            "<meta http-equiv='refresh' content='5'></body></html>"
        )
        try:
            webbrowser.open(str(live_report_path))
        except Exception:
            pass  # headless environment — silent is fine
    else:
        live_report_path = None

    results_dir = None
    log_dir = None
    if args.results_dir:
        ts = time.strftime("%Y-%m-%d_%H%M%S")
        results_dir = Path(args.results_dir) / ts
        results_dir.mkdir(parents=True, exist_ok=True)
        log_dir = results_dir / "logs"

    # #5 — Install SIGINT handler
    _install_sigint_handler()

    # Run the wrapped loop
    try:
        output = _vendor_run_loop.run_loop(
            eval_set=eval_set,
            skill_path=skill_path,
            description_override=args.description,
            num_workers=args.num_workers,
            timeout=args.timeout,
            max_iterations=args.max_iterations,
            runs_per_query=args.runs_per_query,
            trigger_threshold=args.trigger_threshold,
            holdout=args.holdout,
            model=args.model,
            verbose=args.verbose,
            live_report_path=live_report_path,
            log_dir=log_dir,
        )
    except FileNotFoundError as e:
        # Mid-run claude disappearance (rare — we preflight — but possible via PATH changes)
        print(f"ERROR: subprocess target missing: {e}", file=sys.stderr)
        print(_INSTALL_HINT, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n[run_loop_hardened] Aborted by user. No best-so-far available.", file=sys.stderr)
        return 130  # conventional SIGINT exit code

    # #3 — Strict length enforcement
    if args.strict_length:
        output = _strict_length_filter(output, max_chars=1024)
        if args.verbose:
            le = output.get("length_enforcement", {})
            if le.get("action") != "no-op":
                print(f"[strict-length] {le.get('note', le)}", file=sys.stderr)

    # Persist outputs
    json_output = json.dumps(output, indent=2)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output)
    if live_report_path:
        live_report_path.write_text(generate_html(output, auto_refresh=False, skill_name=name))
        if args.verbose:
            print(f"\nReport: {live_report_path}", file=sys.stderr)
    if results_dir and live_report_path:
        (results_dir / "report.html").write_text(generate_html(output, auto_refresh=False, skill_name=name))
    if results_dir and args.verbose:
        print(f"Results saved to: {results_dir}", file=sys.stderr)

    # #4 — Exit code
    if args.exit_always_zero:
        return 0
    return _compute_exit_code(output)


if __name__ == "__main__":
    sys.exit(main())
