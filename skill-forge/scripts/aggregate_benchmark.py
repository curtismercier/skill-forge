#!/usr/bin/env python3
"""
aggregate_benchmark.py — turn per-run grading.json files into benchmark.json.

Reads all `grading.json` files under a benchmark directory, computes mean/stddev/
min/max for pass_rate, time, and tokens, and emits `benchmark.json` in the schema
interoperable with Anthropic's skill-creator output.

Expected directory layout (matches skill-creator and flexible enough for
skill-forge's own layout):

    <benchmark_dir>/
    ├── eval-<id>/
    │   ├── eval_metadata.json          (optional; provides eval_name)
    │   ├── <config>/                   (e.g. with_skill, without_skill)
    │   │   ├── run-1/
    │   │   │   ├── grading.json
    │   │   │   └── timing.json         (optional)
    │   │   ├── run-2/...
    │   │   └── run-N/...
    │   └── <another_config>/...
    └── eval-<id>/...

Also accepts legacy layout with a `runs/` subdirectory wrapping the eval-* dirs.

Usage:
    python aggregate_benchmark.py <benchmark_dir>
    python aggregate_benchmark.py <benchmark_dir> --skill-name modal-llm-inference
    python aggregate_benchmark.py <benchmark_dir> --iteration 2 --out benchmark.json

Stdlib-only. No pip dependencies.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def _stats(values: list[float]) -> dict:
    """Mean, sample stddev, min, max. Empty list → zeroed dict."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0
    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "n": n,
    }


def _load_run(run_dir: Path) -> dict | None:
    """Read one run's grading.json (+ optional timing.json) into a flat dict."""
    grading_file = run_dir / "grading.json"
    if not grading_file.exists():
        return None
    try:
        grading = json.loads(grading_file.read_text())
    except json.JSONDecodeError as e:
        print(f"  skip {grading_file} (invalid JSON: {e})", file=sys.stderr)
        return None

    summary = grading.get("summary", {})
    result = {
        "run_dir": str(run_dir),
        "pass_rate": float(summary.get("pass_rate", 0.0)),
        "passed": int(summary.get("passed", 0)),
        "failed": int(summary.get("failed", 0)),
        "total": int(summary.get("total", 0)),
    }

    # Timing — check grading.timing first, then sibling timing.json.
    timing = grading.get("timing", {}) or {}
    result["time_seconds"] = float(timing.get("total_duration_seconds", 0.0))
    result["tokens"] = int(timing.get("total_tokens", 0))

    timing_file = run_dir / "timing.json"
    if (result["time_seconds"] == 0.0 or result["tokens"] == 0) and timing_file.exists():
        try:
            td = json.loads(timing_file.read_text())
            if result["time_seconds"] == 0.0:
                result["time_seconds"] = float(td.get("total_duration_seconds", 0.0))
            if result["tokens"] == 0:
                result["tokens"] = int(td.get("total_tokens", 0))
        except json.JSONDecodeError:
            pass

    return result


def _load_eval_dir(eval_dir: Path) -> dict:
    """Return {config_name: [run dicts]} for one eval directory."""
    configs: dict[str, list[dict]] = {}
    eval_name = None

    meta = eval_dir / "eval_metadata.json"
    if meta.exists():
        try:
            eval_name = json.loads(meta.read_text()).get("eval_name")
        except json.JSONDecodeError:
            pass

    for config_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
        run_dirs = sorted(config_dir.glob("run-*"))
        if not run_dirs:
            continue  # skip inputs/outputs/misc dirs
        config_name = config_dir.name
        configs.setdefault(config_name, [])
        for run_dir in run_dirs:
            row = _load_run(run_dir)
            if row is not None:
                configs[config_name].append(row)

    return {"eval_id": _extract_eval_id(eval_dir), "eval_name": eval_name, "configs": configs}


def _extract_eval_id(eval_dir: Path) -> int | str:
    """Try eval_metadata.json first, else parse from directory name."""
    meta = eval_dir / "eval_metadata.json"
    if meta.exists():
        try:
            eid = json.loads(meta.read_text()).get("eval_id")
            if eid is not None:
                return eid
        except json.JSONDecodeError:
            pass
    # eval-<id>-<slug> or eval-<id>
    parts = eval_dir.name.split("-", 2)
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return eval_dir.name


def _aggregate_config(runs: list[dict]) -> dict:
    """Turn a list of run rows for one config into stats."""
    if not runs:
        return {"pass_rate": _stats([]), "time_seconds": _stats([]), "tokens": _stats([]), "n_runs": 0}
    return {
        "pass_rate": _stats([r["pass_rate"] for r in runs]),
        "time_seconds": _stats([r["time_seconds"] for r in runs]),
        "tokens": _stats([float(r["tokens"]) for r in runs]),
        "n_runs": len(runs),
    }


def aggregate(benchmark_dir: Path, skill_name: str = "", iteration: int | None = None) -> dict:
    # Tolerate both the legacy `runs/` wrapper and the flat layout.
    search = benchmark_dir / "runs" if (benchmark_dir / "runs").exists() else benchmark_dir
    eval_dirs = sorted(search.glob("eval-*"))
    if not eval_dirs:
        raise FileNotFoundError(f"No eval-* directories under {search}")

    per_eval: list[dict] = []
    all_configs: set[str] = set()

    for ed in eval_dirs:
        info = _load_eval_dir(ed)
        if not info["configs"]:
            continue
        entry = {
            "eval_id": info["eval_id"],
            "eval_name": info["eval_name"],
        }
        for cfg_name, runs in info["configs"].items():
            all_configs.add(cfg_name)
            entry[cfg_name] = _aggregate_config(runs)

        # Compute delta where there's a canonical (with_skill, without_skill) pair.
        # Fall back to first two configs alphabetically if the pair isn't there.
        pair = None
        if "with_skill" in entry and "without_skill" in entry:
            pair = ("with_skill", "without_skill")
        elif len(info["configs"]) >= 2:
            first_two = sorted(info["configs"].keys())[:2]
            pair = (first_two[0], first_two[1])
        if pair:
            a, b = pair
            entry["delta"] = {
                "pass_rate": round(entry[a]["pass_rate"]["mean"] - entry[b]["pass_rate"]["mean"], 4),
                "time_seconds": round(entry[a]["time_seconds"]["mean"] - entry[b]["time_seconds"]["mean"], 4),
                "tokens": round(entry[a]["tokens"]["mean"] - entry[b]["tokens"]["mean"], 4),
                "compared": [a, b],
            }

        per_eval.append(entry)

    # Overall stats — pool all runs per config.
    overall: dict[str, dict] = {}
    for cfg in sorted(all_configs):
        pooled_rates: list[float] = []
        total_runs = 0
        for ed in eval_dirs:
            info = _load_eval_dir(ed)
            for run in info["configs"].get(cfg, []):
                pooled_rates.append(run["pass_rate"])
                total_runs += 1
        overall[cfg] = {"pass_rate": _stats(pooled_rates), "total_runs": total_runs}

    # Overall delta
    if "with_skill" in overall and "without_skill" in overall:
        overall["delta"] = {
            "pass_rate": round(
                overall["with_skill"]["pass_rate"]["mean"] - overall["without_skill"]["pass_rate"]["mean"], 4
            )
        }

    return {
        "schema_version": 1,
        "skill_name": skill_name,
        "iteration": iteration,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "configurations": sorted(all_configs),
        "per_eval": per_eval,
        "overall": overall,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("benchmark_dir", help="Directory containing eval-* subdirectories")
    p.add_argument("--skill-name", default="", help="Name of the skill being benchmarked")
    p.add_argument("--iteration", type=int, default=None, help="Iteration number")
    p.add_argument("--out", default="", help="Output path (default: <benchmark_dir>/benchmark.json)")
    p.add_argument("--json", action="store_true", help="Also print the JSON to stdout")
    args = p.parse_args(argv)

    bench_dir = Path(args.benchmark_dir).resolve()
    if not bench_dir.exists():
        print(f"ERROR: {bench_dir} does not exist", file=sys.stderr)
        return 2

    try:
        result = aggregate(bench_dir, skill_name=args.skill_name, iteration=args.iteration)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else (bench_dir / "benchmark.json")
    out_path.write_text(json.dumps(result, indent=2) + "\n")

    # Short human summary to stderr (so stdout stays clean for --json piping)
    print(f"Aggregated {len(result['per_eval'])} eval(s), {len(result['configurations'])} configuration(s)")  # noqa: security
    print(f"  configurations: {', '.join(result['configurations'])}")
    if "delta" in result["overall"]:
        d = result["overall"]["delta"]["pass_rate"]
        arrow = "↑" if d > 0 else ("↓" if d < 0 else "→")
        print(f"  overall pass_rate delta: {arrow} {d:+.4f}")
    print(f"  wrote {out_path}")

    if args.json:
        print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
