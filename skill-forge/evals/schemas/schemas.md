# Eval Schemas

This document defines the JSON schemas skill-forge's eval tooling reads and writes. **They are intentionally compatible with [Anthropic's skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) format.** If you run Anthropic's `run_eval.py` against your skill, its outputs drop in to skill-forge's `aggregate_benchmark.py` unchanged, and vice versa.

---

## evals.json

Defines the eval set for a skill. Lives at `<skill>/evals/evals.json`.

```json
{
  "skill_name": "modal-llm-inference",
  "evals": [
    {
      "id": 1,
      "prompt": "Deploy the Qwen2.5-7B model with vLLM on an L40S, with OpenAI-compatible endpoints and a 5-minute idle timeout.",
      "expected_output": "A working Modal app file with correct decorators, model class, and @modal.asgi_app wrapping the vLLM OpenAI server.",
      "files": [],
      "expectations": [
        "The deployment uses @app.cls with gpu='L40S'",
        "The model class caches the HuggingFace download via modal.Volume",
        "The idle timeout uses scaledown_window=300, not container_idle_timeout",
        "The entrypoint invokes `vllm serve`, not the deprecated api_server module"
      ]
    }
  ]
}
```

**Fields:**

- `skill_name` — matches the skill's frontmatter `name`
- `evals[].id` — unique integer
- `evals[].prompt` — the task to run
- `evals[].expected_output` — human-readable description of success (the grader doesn't use this directly; it's for humans)
- `evals[].files` — optional input file paths, relative to skill root
- `evals[].expectations` — list of verifiable assertions the grader evaluates

---

## grading.json

The grader's output per-run. Lives at `<workspace>/iteration-<N>/eval-<id>/<config>/run-<n>/grading.json`.

```json
{
  "expectations": [
    {
      "text": "The deployment uses @app.cls with gpu='L40S'",
      "passed": true,
      "evidence": "Line 42 of output/app.py: `@app.cls(image=vllm_image, gpu='L40S', ...)`"
    },
    {
      "text": "The idle timeout uses scaledown_window=300",
      "passed": false,
      "evidence": "output/app.py line 44 uses `container_idle_timeout=300` which is deprecated. Should be `scaledown_window=300`."
    }
  ],
  "implicit_claims": [],
  "expectation_critique": [],
  "summary": {
    "total": 4,
    "passed": 3,
    "failed": 1,
    "pass_rate": 0.75,
    "notes": "The deprecated API usage is a drift issue — upstream Modal renamed the parameter in SDK 0.64."
  },
  "timing": {
    "total_duration_seconds": 23.3,
    "total_tokens": 84852
  }
}
```

**Required fields** (downstream tools depend on these names, do not rename):

- `expectations[].text` — the assertion text
- `expectations[].passed` — boolean
- `expectations[].evidence` — specific citation
- `summary.pass_rate` — float in `[0, 1]`
- `summary.passed`, `summary.failed`, `summary.total` — integers

**Optional fields:**

- `timing.total_duration_seconds`, `timing.total_tokens` — populated from the task notification when available
- `implicit_claims`, `expectation_critique` — the grader's meta-observations

---

## benchmark.json

Output of `aggregate_benchmark.py`. One per iteration.

```json
{
  "skill_name": "modal-llm-inference",
  "iteration": 2,
  "generated_at": "2026-04-17T00:15:32Z",
  "configurations": ["with_skill", "without_skill"],
  "per_eval": [
    {
      "eval_id": 1,
      "with_skill": {
        "pass_rate": {"mean": 0.92, "stddev": 0.07, "min": 0.83, "max": 1.0},
        "time_seconds": {"mean": 24.1, "stddev": 2.3, "min": 21.5, "max": 27.8},
        "tokens": {"mean": 83200, "stddev": 4100, "min": 78500, "max": 89100},
        "n_runs": 3
      },
      "without_skill": {
        "pass_rate": {"mean": 0.42, "stddev": 0.14, "min": 0.33, "max": 0.58},
        "time_seconds": {"mean": 31.2, "stddev": 4.1, "min": 27.1, "max": 36.8},
        "tokens": {"mean": 94100, "stddev": 6300, "min": 87200, "max": 101400},
        "n_runs": 3
      },
      "delta": {
        "pass_rate": 0.50,
        "time_seconds": -7.1,
        "tokens": -10900
      }
    }
  ],
  "overall": {
    "with_skill": {"pass_rate": {"mean": 0.83, "stddev": 0.11}, "total_runs": 9},
    "without_skill": {"pass_rate": {"mean": 0.58, "stddev": 0.18}, "total_runs": 9},
    "delta": {"pass_rate": 0.25}
  }
}
```

---

## history.json

Tracks versions across iterations. Lives at workspace root.

```json
{
  "started_at": "2026-04-16T10:30:00Z",
  "skill_name": "modal-llm-inference",
  "current_best": "v2",
  "iterations": [
    {
      "version": "v0",
      "parent": null,
      "expectation_pass_rate": 0.65,
      "grading_result": "baseline",
      "is_current_best": false,
      "notes": "Pre-audit draft — contained a hallucinated GPU-price value"  <!-- noqa: audit -->
    },
    {
      "version": "v1",
      "parent": "v0",
      "expectation_pass_rate": 0.83,
      "grading_result": "won",
      "is_current_best": false,
      "notes": "Fixed pricing, scaledown_window rename, vllm serve entrypoint"
    },
    {
      "version": "v2",
      "parent": "v1",
      "expectation_pass_rate": 0.92,
      "grading_result": "won",
      "is_current_best": true,
      "notes": "Added tool-calling example and proxy-auth variant"
    }
  ]
}
```

`grading_result` is one of `"baseline"`, `"won"`, `"lost"`, `"tie"` — the comparator agent's verdict against the prior version.

---

## trigger_eval.json

The dataset used by `improve_description.py` (Anthropic's tool) or any description-tuning loop. Lives anywhere; pass the path via `--eval-set`.

```json
[
  {"query": "deploy qwen 2.5 to modal with vllm, want openai compat", "should_trigger": true},
  {"query": "write me a python function to compute factorial", "should_trigger": false},
  {"query": "our modal app is cold-starting slowly, can you set up snapshots", "should_trigger": true},
  {"query": "how do I set up a kubernetes deployment for my inference service", "should_trigger": false}
]
```

**Rules of thumb:**

- 20 queries minimum (aim for 10 positive + 10 near-miss negative)
- Make negatives *near-misses* — queries that share keywords or concepts with the skill but need something else. Obvious irrelevant queries don't test trigger selectivity.
- Include casual phrasing, typos, abbreviations — match how users actually type.
- Include concrete context (company names, filenames, column names) — generic queries don't trigger skills reliably regardless of description.

---

## Interoperability with Anthropic's skill-creator

**Input schemas (grading.json, evals.json, trigger_eval.json) are verified compatible** with Anthropic's skill-creator. We've tested that:

- Anthropic's `run_eval.py` output feeds directly into skill-forge's `aggregate_benchmark.py` without modification
- Anthropic's `aggregate_benchmark.py` reads the same directory layout skill-forge produces

**Output schemas (benchmark.json structure) differ by design.** Anthropic's aggregator emits a `run_summary` + `runs` shape optimized for their HTML viewer; skill-forge's emits a `per_eval` + `overall` shape optimized for our static HTML report. If you need Anthropic-format benchmark.json, run their aggregator; if you need ours, run ours. The underlying numbers are identical — only the serialization differs.

Neither tool owns the grading.json or evals.json schemas; both target the same input shape. If you see a drift between the two tools' expectations in practice, that's real drift — report it and we'll absorb the correction via ERRATA.
