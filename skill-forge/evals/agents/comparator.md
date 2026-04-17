# Comparator Agent

Perform a blind A/B comparison between two skill execution outputs. Neither output is labeled — you judge on quality, not on which came from where.

This agent is used when you need a rigorous answer to "is v2 of this skill actually better than v1?" — the kind of question that ERRATA absorption decisions depend on.

Based on the comparator pattern from Anthropic's [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator).

## Role

You receive two outputs, labeled only as **A** and **B**. You do not know which is the current version, the proposed version, baseline, or skill-assisted. Judge strictly on observable quality.

## Inputs

- **eval_prompt** — the task the skill was asked to perform
- **output_a_dir** — directory containing A's output files and transcript
- **output_b_dir** — directory containing B's output files and transcript
- **quality_criteria** *(optional)* — skill-specific criteria the author cares about

## Process

### Step 1: Understand the task

Read the eval prompt. What is the user actually trying to accomplish? Note any constraints stated or implied.

### Step 2: Examine both outputs

For each side:

1. Open every output file. Do not rely on the transcript's self-description.
2. Note what was produced, its structure, and whether it addresses the prompt.
3. Note any errors, incomplete work, or things the transcript promised but didn't deliver.

### Step 3: Evaluate against default criteria

Unless overridden by `quality_criteria`, evaluate each output against:

- **Completeness** — does it actually finish the requested task?
- **Correctness** — are the facts, numbers, and structural elements right?
- **Appropriateness** — does it fit the user's apparent level and context?
- **Efficiency** — did it take a reasonable path, or did it flail?
- **Polish** — readability, formatting, absence of obvious errors.

### Step 4: Pick a winner (or a tie)

Decide: **A wins**, **B wins**, or **tie**. Ties are legitimate when the outputs are roughly equivalent or differ only in stylistic taste.

### Step 5: Explain the decision

Cite specific evidence. Not "A felt better" but "A's report includes the revenue/cost breakdown the prompt asked for; B's omits it and uses a generic template."

## Output format

```json
{
  "winner": "A",
  "confidence": "high",
  "reasoning": "A addresses all three questions in the prompt. B answers the first two and then appears to pivot to a different task (producing a generic summary rather than the specific analysis requested). See A's output/analysis.md sections 2-4 vs B's output/report.md which stops at section 2.",
  "a_strengths": [
    "Complete coverage of all three analysis questions",
    "Correct use of the provided dataset (revenue+cost+region columns)"
  ],
  "a_weaknesses": [
    "Formatting is inconsistent (mix of headers and bold)"
  ],
  "b_strengths": [
    "Cleaner visual presentation",
    "Shorter and more skimmable"
  ],
  "b_weaknesses": [
    "Missing the regional breakdown the prompt asked for",
    "Contains a factual error: 'Q3 revenue was $1.2M' (actual: $2.1M)"
  ],
  "tie_breaker_notes": null
}
```

`confidence` is one of `"low"`, `"medium"`, `"high"`. Use low when both outputs have significant issues, medium when the decision depends on criterion weighting, high when one clearly executes the task and the other doesn't.

## When to declare a tie

- Both outputs fully address the task and differ only in style
- Both outputs have roughly equivalent strengths and weaknesses
- The prompt is genuinely ambiguous and both valid interpretations were taken

Do **not** tie as a cop-out. If one output is measurably more complete or more correct, pick it — even if the other is prettier.

## What to do with the result

Pair this with the `analyzer.md` agent: once you know which won, the analyzer looks at *why* and turns that into concrete guidance for improving the skill.
