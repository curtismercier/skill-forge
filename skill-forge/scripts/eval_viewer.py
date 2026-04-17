#!/usr/bin/env python3
"""
eval_viewer.py — render benchmark.json + run outputs to a single HTML file.

Produces a self-contained, zero-dependency HTML page that shows:
  - Per-eval outputs side by side (with_skill vs without_skill)
  - Per-expectation pass/fail with evidence
  - Aggregate pass-rate, timing, and token stats with stddev
  - Analyst observations (if analyzer.json present)

No server. No JS framework. No LLM calls. Opens in any browser.

Inspired by the skill-creator eval viewer at
https://github.com/anthropics/skills/tree/main/skills/skill-creator/eval-viewer
but rewritten as static HTML for portability.

Usage:
    python eval_viewer.py <benchmark_dir> --out report.html
    python eval_viewer.py <benchmark_dir> --out report.html --skill-name my-skill
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


def _esc(s) -> str:
    """HTML-escape, None → empty string."""
    if s is None:
        return ""
    return html.escape(str(s))


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _collect_eval_runs(benchmark_dir: Path) -> list[dict]:
    """Gather every run's transcript/outputs/grading for display."""
    search = benchmark_dir / "runs" if (benchmark_dir / "runs").exists() else benchmark_dir
    out: list[dict] = []

    for eval_dir in sorted(search.glob("eval-*")):
        meta = _read_json(eval_dir / "eval_metadata.json") or {}
        entry = {
            "eval_id": meta.get("eval_id", eval_dir.name),
            "eval_name": meta.get("eval_name") or eval_dir.name,
            "prompt": meta.get("prompt", ""),
            "configs": {},
        }
        for config_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            run_dirs = sorted(config_dir.glob("run-*"))
            if not run_dirs:
                continue
            runs: list[dict] = []
            for rd in run_dirs:
                grading = _read_json(rd / "grading.json") or {}
                timing = _read_json(rd / "timing.json") or {}
                transcript = ""
                tpath = rd / "transcript.md"
                if tpath.exists():
                    try:
                        transcript = tpath.read_text(errors="replace")
                    except OSError:
                        pass

                outputs_dir = rd / "outputs"
                output_files: list[str] = []
                if outputs_dir.is_dir():
                    for f in sorted(outputs_dir.iterdir()):
                        if f.is_file():
                            output_files.append(f.name)

                runs.append({
                    "run_dir": rd.name,
                    "grading": grading,
                    "timing": timing,
                    "transcript_excerpt": transcript[:2000],
                    "output_files": output_files,
                })
            entry["configs"][config_dir.name] = runs
        out.append(entry)
    return out


# ──────────────────────────────────────────────────────────────
# HTML rendering
# ──────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #fafafa;
  --panel: #ffffff;
  --border: #e5e5e5;
  --text: #111;
  --muted: #666;
  --accent: #3c63d1;
  --pass: #1f7a1f;
  --fail: #b82020;
  --warn: #a65f00;
  --code-bg: #f4f4f4;
  --skill-forge: #3c63d1;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a1a;
    --panel: #242424;
    --border: #3a3a3a;
    --text: #e8e8e8;
    --muted: #a0a0a0;
    --accent: #7b94e8;
    --pass: #5fb35f;
    --fail: #d96a6a;
    --warn: #d9a666;
    --code-bg: #1e1e1e;
  }
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  background: var(--bg);
  margin: 0;
  padding: 2rem 3rem;
  max-width: 1400px;
}
h1 { font-size: 22px; margin: 0 0 .5rem; }
h2 { font-size: 18px; margin: 2rem 0 .5rem; border-bottom: 1px solid var(--border); padding-bottom: .25rem; }
h3 { font-size: 16px; margin: 1.5rem 0 .5rem; }
.brand { color: var(--skill-forge); font-weight: 500; }
.muted { color: var(--muted); font-size: 13px; }
.panel {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin: .75rem 0;
}
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
.stat { display: flex; flex-direction: column; padding: .75rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; }
.stat-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
.stat-value { font-size: 20px; font-weight: 500; margin-top: .25rem; }
.stat-delta { font-size: 13px; margin-top: .25rem; }
.delta-positive { color: var(--pass); }
.delta-negative { color: var(--fail); }
.delta-neutral { color: var(--muted); }
table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
th, td { text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--border); font-size: 13px; }
th { font-weight: 500; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .5px; }
.pass-mark { color: var(--pass); font-weight: 500; }
.fail-mark { color: var(--fail); font-weight: 500; }
.eval-card { margin: 1rem 0; border: 1px solid var(--border); border-radius: 8px; background: var(--panel); overflow: hidden; }
.eval-header { padding: .75rem 1.25rem; background: var(--bg); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.eval-body { padding: 1rem 1.25rem; }
.configs-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 900px) { .configs-grid { grid-template-columns: 1fr; } }
.config-panel { border: 1px solid var(--border); border-radius: 6px; padding: .75rem 1rem; background: var(--bg); }
.config-name { font-weight: 500; color: var(--accent); font-size: 13px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: .5rem; }
details { margin: .5rem 0; }
summary { cursor: pointer; font-size: 13px; color: var(--muted); padding: .25rem 0; }
summary:hover { color: var(--text); }
pre { background: var(--code-bg); padding: .75rem 1rem; border-radius: 6px; font-size: 12px; line-height: 1.4; overflow-x: auto; margin: .5rem 0; }
code { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
.exp-list { margin: .5rem 0 0; padding-left: 1.25rem; font-size: 13px; }
.exp-list li { margin: .25rem 0; }
.evidence { color: var(--muted); font-size: 12px; margin-left: .5rem; font-style: italic; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; }
"""


def _render_overall(benchmark: dict) -> str:
    overall = benchmark.get("overall", {})
    if not overall:
        return ""

    cards: list[str] = []
    for cfg, data in sorted(overall.items()):
        if cfg == "delta":
            continue
        pr = data.get("pass_rate", {})
        cards.append(f"""
        <div class="stat">
          <div class="stat-label">{_esc(cfg)}</div>
          <div class="stat-value">{_pct(pr.get('mean', 0))}</div>
          <div class="muted">±{_pct(pr.get('stddev', 0))} &middot; {_esc(data.get('total_runs', 0))} runs</div>
        </div>
        """)

    delta_html = ""
    if "delta" in overall:
        d = overall["delta"]["pass_rate"]
        cls = "delta-positive" if d > 0 else "delta-negative" if d < 0 else "delta-neutral"
        arrow = "↑" if d > 0 else "↓" if d < 0 else "→"
        delta_html = f"""
        <div class="stat">
          <div class="stat-label">Δ pass rate</div>
          <div class="stat-value {cls}">{arrow} {d * 100:+.1f}%</div>
          <div class="muted">with_skill vs without_skill</div>
        </div>
        """

    return f"""
    <h2>Overall</h2>
    <div class="stat-row">
      {''.join(cards)}
      {delta_html}
    </div>
    """


def _render_per_eval_table(benchmark: dict) -> str:
    per_eval = benchmark.get("per_eval", [])
    if not per_eval:
        return ""

    configs = benchmark.get("configurations", [])
    header_cols = "".join(f"<th>{_esc(c)}<br><span class='muted'>pass&nbsp;·&nbsp;σ&nbsp;·&nbsp;n</span></th>" for c in configs)

    rows: list[str] = []
    for entry in per_eval:
        name = entry.get("eval_name") or entry.get("eval_id", "—")
        cells: list[str] = []
        for cfg in configs:
            cd = entry.get(cfg, {})
            pr = cd.get("pass_rate", {})
            cells.append(
                f"<td>{_pct(pr.get('mean', 0))} · ±{_pct(pr.get('stddev', 0))} · {cd.get('n_runs', 0)}</td>"
            )
        delta = entry.get("delta", {})
        delta_str = ""
        if "pass_rate" in delta:
            d = delta["pass_rate"]
            cls = "delta-positive" if d > 0 else "delta-negative" if d < 0 else "delta-neutral"
            delta_str = f"<td class='{cls}'>{d * 100:+.1f}%</td>"
        else:
            delta_str = "<td>—</td>"
        rows.append(f"<tr><td>{_esc(name)}</td>{''.join(cells)}{delta_str}</tr>")

    return f"""
    <h2>Per-eval breakdown</h2>
    <table>
      <thead><tr><th>Eval</th>{header_cols}<th>Δ</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    """


def _render_expectations(grading: dict) -> str:
    exps = grading.get("expectations", [])
    if not exps:
        return "<div class='muted'>No grading data.</div>"
    items: list[str] = []
    for e in exps:
        mark = "<span class='pass-mark'>✓</span>" if e.get("passed") else "<span class='fail-mark'>✗</span>"
        evidence = _esc(e.get("evidence", ""))
        items.append(
            f"<li>{mark} {_esc(e.get('text', ''))}"
            + (f"<br><span class='evidence'>{evidence}</span>" if evidence else "")
            + "</li>"
        )
    summary = grading.get("summary", {})
    return f"""
    <div class="muted">Pass rate: {_pct(summary.get('pass_rate', 0))} ({summary.get('passed', 0)}/{summary.get('total', 0)})</div>
    <ul class="exp-list">{''.join(items)}</ul>
    """


def _render_eval_card(eval_entry: dict) -> str:
    name = eval_entry.get("eval_name", "")
    prompt = eval_entry.get("prompt", "")
    configs = eval_entry.get("configs", {})

    panels: list[str] = []
    for cfg_name, runs in sorted(configs.items()):
        run_blocks: list[str] = []
        for r in runs:
            grading = r.get("grading", {})
            timing = r.get("timing", {})
            files_html = ""
            if r.get("output_files"):
                files_html = "<div class='muted'>Output files: " + ", ".join(
                    _esc(f) for f in r["output_files"]
                ) + "</div>"
            tokens = timing.get("total_tokens", 0) or r.get("grading", {}).get("timing", {}).get("total_tokens", 0)
            duration = timing.get("total_duration_seconds", 0) or r.get("grading", {}).get("timing", {}).get("total_duration_seconds", 0)
            run_blocks.append(f"""
            <details>
              <summary>{_esc(r['run_dir'])} — {duration:.1f}s · {int(tokens):,} tokens</summary>
              {_render_expectations(grading)}
              {files_html}
            </details>
            """)
        panels.append(f"""
        <div class="config-panel">
          <div class="config-name">{_esc(cfg_name)}</div>
          {''.join(run_blocks)}
        </div>
        """)

    prompt_block = f"<details><summary>Prompt</summary><pre><code>{_esc(prompt)}</code></pre></details>" if prompt else ""

    return f"""
    <div class="eval-card">
      <div class="eval-header">
        <strong>{_esc(name)}</strong>
        <span class="muted">id: {_esc(eval_entry.get('eval_id'))}</span>
      </div>
      <div class="eval-body">
        {prompt_block}
        <div class="configs-grid">{''.join(panels)}</div>
      </div>
    </div>
    """


def render_html(benchmark: dict, runs: list[dict], skill_name: str = "") -> str:
    title = skill_name or benchmark.get("skill_name") or "skill"
    gen_at = benchmark.get("generated_at", "")
    iteration = benchmark.get("iteration")
    iter_label = f" · iteration {iteration}" if iteration is not None else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_esc(title)} — benchmark</title>
  <style>{_CSS}</style>
</head>
<body>
  <h1><span class="brand">skill-forge</span> / {_esc(title)}</h1>
  <div class="muted">generated {_esc(gen_at)}{iter_label}</div>

  {_render_overall(benchmark)}
  {_render_per_eval_table(benchmark)}

  <h2>Per-eval details</h2>
  {''.join(_render_eval_card(r) for r in runs)}

  <footer>
    Generated by <code>skill-forge/scripts/eval_viewer.py</code>.
    Schema compatible with
    <a href="https://github.com/anthropics/skills/tree/main/skills/skill-creator">anthropics/skills</a>.
  </footer>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render a benchmark directory to a static HTML report.")
    p.add_argument("benchmark_dir", help="Directory containing benchmark.json and eval-* subdirs")
    p.add_argument("--out", default="", help="Output HTML path (default: <benchmark_dir>/report.html)")
    p.add_argument("--skill-name", default="", help="Override skill name shown in the title")
    args = p.parse_args(argv)

    bench_dir = Path(args.benchmark_dir).resolve()
    if not bench_dir.exists():
        print(f"ERROR: {bench_dir} does not exist", file=sys.stderr)
        return 2

    bench_json_path = bench_dir / "benchmark.json"
    if not bench_json_path.exists():
        print(f"ERROR: no benchmark.json in {bench_dir}. Run aggregate_benchmark.py first.", file=sys.stderr)
        return 2

    benchmark = json.loads(bench_json_path.read_text())
    runs = _collect_eval_runs(bench_dir)

    out_path = Path(args.out) if args.out else (bench_dir / "report.html")
    out_path.write_text(render_html(benchmark, runs, skill_name=args.skill_name))

    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
