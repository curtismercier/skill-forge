# Evals

Behavioral evaluation infrastructure for skill-forge-produced skills. Complements the static audits (`validate_skill.py`, `audit_skill.py`, `security_scan.py`, `staleness_check.py`) with runtime measurement of whether a skill actually improves outcomes.

## What's in this directory

```
evals/
├── agents/
│   ├── grader.md          prompt template for the grading subagent
│   ├── comparator.md      prompt template for blind A/B comparison
│   └── analyzer.md        prompt template for surfacing patterns in results
└── schemas/
    └── schemas.md         JSON schema reference for evals.json, grading.json,
                           benchmark.json, history.json, trigger_eval.json
```

The static analysis tooling lives in the top-level `scripts/` directory. The two pieces new in this round:

- `scripts/aggregate_benchmark.py` — reads per-run `grading.json` files, writes `benchmark.json` with mean / stddev / min / max per configuration, plus deltas. Stdlib-only.
- `scripts/eval_viewer.py` — renders `benchmark.json` + run outputs to a self-contained static HTML report. No server, no JS framework, works offline.

## How this pairs with Anthropic's skill-creator

skill-forge **uses the same input schemas** (grading.json, evals.json, trigger_eval.json) as Anthropic's [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator). Tested: Anthropic's `run_eval.py` output feeds directly into skill-forge's `aggregate_benchmark.py`, and Anthropic's `aggregate_benchmark.py` reads data produced in skill-forge's directory layout. Output benchmark.json structure differs between the two (both aggregate the same numbers into different shapes optimized for each tool's viewer) — see `schemas/schemas.md` for the exact boundary.

This means you can mix and match:

| Tool | Source | What it does |
|------|--------|--------------|
| `run_eval.py` | Anthropic | Spawns subagents to execute a skill against eval prompts. Requires `claude -p` CLI. |
| `run_loop.py` | Anthropic | The trigger-optimization loop. Requires `claude -p` CLI. |
| `improve_description.py` | Anthropic | Proposes description improvements. Requires `claude -p` CLI. |
| `aggregate_benchmark.py` | **skill-forge** | Reads grading outputs, computes stats. Pure stdlib. |
| `eval_viewer.py` | **skill-forge** | Static HTML report generator. Pure stdlib. |
| `grader.md` | **skill-forge** (adapted) | Prompt for the grading subagent. |
| `comparator.md` | **skill-forge** (adapted) | Prompt for blind A/B. |
| `analyzer.md` | **skill-forge** (adapted) | Prompt for pattern detection in aggregates. |
| `audit_skill.py`, `staleness_check.py`, etc. | skill-forge | Static audits (no LLM calls). |

Why this split: Anthropic's scripts do the **subagent plumbing** — shell out to `claude -p`, parse responses, retry on failures. That's Claude-Code-specific and well-tested; no reason to reimplement. skill-forge's scripts do **stats and presentation** — the parts that don't need an LLM and benefit from being portable across environments.

## Typical workflow

```bash
# 1. Skill creator (Anthropic's or skill-forge's scaffolding) writes evals.
#    Format: evals/evals.json per the schema in schemas/schemas.md

# 2. Anthropic's run_eval.py executes the skill against each eval, with and
#    without-skill baselines, 3 runs each.
python -m scripts.run_eval <skill-path> <workspace>/iteration-1 \
    --runs-per-eval 3 --spawn-baseline

# 3. Each grading.json is produced by the grader subagent using agents/grader.md
#    (either Anthropic's or skill-forge's — the schemas match).

# 4. skill-forge aggregates.
python scripts/aggregate_benchmark.py <workspace>/iteration-1 \
    --skill-name my-skill --iteration 1

# 5. skill-forge renders the HTML report.
python scripts/eval_viewer.py <workspace>/iteration-1 \
    --out <workspace>/iteration-1/report.html

# 6. Open the report, review, iterate.
```

## Why we vendor Anthropic's execution scripts

`run_eval.py`, `run_loop.py`, `improve_description.py`, and `generate_report.py` are vendored into `scripts/vendor/anthropic_skill_creator/` under Apache 2.0. Two reasons this is better than a soft dependency:

1. **No silent breakage** — Anthropic actively develops these scripts. Soft-depending on an in-tree path across their repo means skill-forge breaks when they restructure. Vendoring pins a known-good version.
2. **Fewer install steps** — users running skill-forge don't need to install skill-creator separately just to run trigger-tuning.

The only modification to vendored files: imports rewritten from `from scripts.X` to `from .X` so the package is self-contained. Everything else is verbatim.

`scripts/vendor/run_loop_hardened.py` is a skill-forge-owned wrapper that adds:

- Preflight check for the `claude` CLI with an install hint (upstream raises `FileNotFoundError` mid-subprocess)
- Separation of errored runs from non-triggered runs (upstream conflates them as `triggered=False`)
- Strict 1024-char enforcement with fallback to best under-limit history entry (upstream emits over-limit descriptions when its one-shot retry fails)
- Meaningful exit codes — 0 on improvement, 1 on no-improvement, 2 on error (upstream always exits 0)
- SIGINT handling that drains running subprocesses cleanly

Each hardening is opt-outable via CLI flags, so you can reproduce exact upstream behavior with `--no-preflight --max-error-rate=1.0 --no-strict-length --exit-always-zero`.

## Running without the `claude` CLI

The vendored scripts need the `claude` CLI (Claude Code v2.90+) on PATH — they shell out to `claude -p` for subagent execution.

If you don't have it:

- `aggregate_benchmark.py` and `eval_viewer.py` still work — they just need grading.json files on disk, regardless of who produced them.
- The agent markdown files (`grader.md`, `comparator.md`, `analyzer.md`) are usable prompts you can paste into any Claude session directly.
- `run_loop_hardened.py`'s preflight check will exit cleanly with an install hint rather than crashing mid-optimization.

This is the honest scope: skill-forge's eval tooling is the **stats + presentation + prompts + wrapper** layer around Anthropic's execution core. Without the execution core, everything downstream of "grading.json exists" still works; you just have to produce the grading.json yourself.
