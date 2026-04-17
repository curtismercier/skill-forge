# Walkthrough: building a real skill with skill-forge

This is a start-to-finish walkthrough. No hand-waving, no "imagine you have an eval set" — every command is runnable, every output block is real, and the end state is a skill you could ship.

**Goal:** build a Tier 2 skill called `git-cleanup` that helps Claude safely prune merged branches and stale tags from a git repo. Real use case, small enough to finish in one sitting, touches every major skill-forge tool.

**Time budget:** 30-45 minutes reading + running, first time. Ten minutes once you know the loop.

**What you need:**

- Python 3.10+ (stdlib only; no pip installs)
- git on PATH
- For the behavioral eval parts (optional): `claude` CLI v2.90+ on PATH
- **skill-forge installed**. Two paths:
  - Via `gh skill`: `gh skill install curtismercier/skill-forge skill-forge` — lands in your agent host's skills dir. This walkthrough assumes `~/.claude/skills/skill-forge/` (Claude Code's path); substitute yours.
  - Via sparse clone: see [the skill's README install section](../README.md#install). The walkthrough assumes the resulting directory is at `~/skills/skill-forge/`.

Throughout this doc, `$SF` refers to wherever skill-forge ended up. Set it once and use it everywhere:

```bash
# Pick one:
export SF=~/.claude/skills/skill-forge       # gh skill install target (Claude Code)
# or
export SF=~/skills/skill-forge               # sparse-clone target
```

---

## Stage 0 — Decide the tier

Before writing anything, open `docs/02-planning.md` and walk the decision tree. For `git-cleanup`:

- Does it need runnable helpers? **Yes** — the safety checks (is this branch really merged? does this tag point to a commit that's in main?) are easier to script than to prompt for every time.
- Does the underlying thing drift fast? **No** — git's command surface is stable across years. No upstream API that changes monthly.
- Multi-stage or sub-skills? **No** — one job, one skill.

Tier 2. Scripts + references, no ERRATA, no verification playbook.

This five-minute planning step is what keeps skills from growing into bloated Tier 3 cathedrals for what should be a 400-line Tier 2 workshop. If you skip it, you'll overbuild.

---

## Stage 1 — Scaffold

```bash
cd ~
python3 $SF/scripts/new_skill.py git-cleanup --tier 2
```

Expected output:

```
Scaffolded tier-2 skill at ./git-cleanup
  SKILL.md
  scripts/
  references/
  evals/evals.json (placeholder)
Next: edit SKILL.md, then run scripts/validate_skill.py
```

What you got:

```
git-cleanup/
├── SKILL.md              frontmatter + placeholder body
├── scripts/              empty
├── references/           empty
└── evals/
    └── evals.json        empty eval set with the right shape
```

Open `SKILL.md`. The frontmatter is pre-filled with `name: git-cleanup` and a placeholder description. The body is a template with section headers for you to fill.

---

## Stage 2 — Write the description *first*

The description is the hardest-working 1024 characters in your skill. Claude decides whether to invoke the skill based on it alone, before ever reading the body. **Write it before you write anything else**, and write it pushy — Claude over-indexes on undertriggering, so a description that sounds slightly too eager is usually right.

Bad (won't trigger on casual queries):

> Helps users manage git branches and tags.

Better (pushy, specific, intent-focused):

> Safely delete merged git branches and stale tags. Use this skill whenever the user mentions cleaning up a repo, pruning branches, deleting tags, removing stale references, or anything about "tidying" git history. Also triggers for phrases like "my branch list is a mess", "too many branches", "can you nuke the old feature branches", or any mention of `git branch -d` / `git branch -D` / `git tag -d`. The skill adds safety checks (merged-into-main verification, remote-tracking reconciliation) that bare git commands don't.

Save it. This will iterate — see Stage 7 — but the structural features (imperative voice, specific trigger phrases, explicit mention of adjacent queries that should still trigger) are non-negotiable. See `references/description-tuning.md` for the full pattern.

---

## Stage 3 — Draft the body, then prune

A first-draft SKILL.md for this skill looks like:

```markdown
# git-cleanup

A skill for safely deleting merged branches and stale tags.

## When to use

Whenever the user wants to clean up their git repo's branch list or tag list.
Default to a preview (dry-run) before any destructive command — the user has to
see what will be deleted before it gets deleted.

## Approach

1. Use `scripts/audit_branches.py` to list candidates for deletion.
2. Show the list to the user. Annotate why each candidate was selected
   (merged into main? deleted on remote? older than 30 days?).
3. Wait for explicit confirmation.
4. Delete with `scripts/prune.py --confirm`.

## Safety checks (non-negotiable)

- Never delete a branch that isn't merged into `main` (or `master`, `develop`).
- Never delete a tag pointing at a commit not reachable from `main`.
- Never run `git branch -D` (force delete) without the user typing the literal
  word "force" in the conversation. `-d` (safe delete) only.

## References

- `references/git-cleanup-patterns.md` — common scenarios and edge cases.
```

Two things to notice:

1. **No all-caps MUSTs.** "Non-negotiable" is load-bearing wording but it's not shouting. The reasoning (`"without the user typing the literal word 'force'"`) does the work.
2. **The body points at scripts and references.** That's progressive disclosure — Claude reads the body, then only pulls in the reference file if the situation calls for it.

Now write the two scripts:

```python
# scripts/audit_branches.py
"""List branches that are candidates for deletion (merged + not-current)."""
import subprocess, sys

def merged_branches(base="main"):
    result = subprocess.run(
        ["git", "branch", "--merged", base, "--format=%(refname:short)"],
        capture_output=True, text=True, check=True,
    )
    return [b.strip() for b in result.stdout.splitlines() if b.strip() and b.strip() != base]

if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "main"
    for b in merged_branches(base):
        print(b)
```

```python
# scripts/prune.py
"""Delete branches listed on stdin, with --confirm required."""
import argparse, subprocess, sys

p = argparse.ArgumentParser()
p.add_argument("--confirm", action="store_true")
args = p.parse_args()

if not args.confirm:
    print("Refusing without --confirm", file=sys.stderr)
    sys.exit(2)

for line in sys.stdin:
    branch = line.strip()
    if not branch:
        continue
    subprocess.run(["git", "branch", "-d", branch], check=False)
```

And the reference:

```markdown
<!-- references/git-cleanup-patterns.md -->
# Common scenarios

## "Too many feature branches"

Run `audit_branches.py`. If the list is over 50, batch by author.

## "Delete all tags older than 1.0"

Tags need separate treatment. Use `git tag -l` + `git log --format=%ct`
to filter by date. Do NOT use `git tag -d` without running
`git describe --contains` first to check reachability.

## "It says branch is merged but I don't trust it"

`git branch --merged main` only checks merge commits. A squashed-merge
branch shows as unmerged. Use `git log main --pretty=format:%s` and
grep for the squashed commit's message first.
```

Done. About 100 lines total.

---

## Stage 4 — Run the four audits

This is the static-analysis pass. Four tools, four concerns, runs in under a second total:

```bash
cd ~/git-cleanup
python3 $SF/scripts/validate_skill.py .
python3 $SF/scripts/security_scan.py .
python3 $SF/scripts/audit_skill.py .
python3 $SF/scripts/staleness_check.py .
```

What each one does and what it catches:

### `validate_skill.py` — structural

Checks: frontmatter is well-formed, `name` matches directory, `description` is under 1024 chars, all Python files parse, required files exist. Exit 0 on pass. You should see:

```
Validation passed for /Users/you/git-cleanup
```

### `security_scan.py` — secrets and dangerous patterns

Looks for hardcoded tokens (12 patterns — AWS keys, GitHub PATs, OpenAI keys, Slack webhooks, etc.), `eval()` with non-literal arguments, `subprocess` with `shell=True` on user input, `os.system()`. Honors `# noqa: security` on the same line when you *know* you want that pattern.

For `git-cleanup` the expected output is:

```
Security scan: /Users/you/git-cleanup
  0 block · 0 warn · 0 info
  ✓ No security issues found.
```

### `audit_skill.py` — anti-slop

The one that catches content rot. It looks for ten failure modes drawn from real drafts:

1. Suspiciously round numbers (pricing that ends in `.00` or `.50`)
2. Specific known-hallucinated values (like `$3.50/hr H200` — a real bug we caught in the Modal skill) <!-- noqa: audit -->
3. Stale version pins (`vllm>=0.6.0` when 0.19 has been out for months)
4. Slop attributions ("As an AI language model," "I cannot help with," etc.) <!-- noqa: audit -->
5. Non-existent model IDs (`gpt-5-turbo-instruct`, `claude-sonnet-4.7-mini-ultra`)
6. Placeholder boilerplate left in production (`# TODO`, `FIXME`, `<YOUR_KEY_HERE>`)
7. Fabricated URLs (domain lookup + path shape heuristics)
8. Inconsistent command names (skill references `foo.py` but ships `foo_v2.py`)
9. Markdown structure smells (headers out of order, duplicate H1s)
10. Empty-promise phrases ("seamlessly integrates", "simply")

You'll see:

```
Audit of /Users/you/git-cleanup
  0 flag · 0 warn · 0 info
  ✓ No issues found.
```

### `staleness_check.py` — review age + dependencies

Reads `last_reviewed` from frontmatter, calculates age. Checks any `dependencies:` entries in frontmatter against the relevant package registries (PyPI, npm, RubyGems) to flag pins that have aged out. For this skill there are no external dependencies, so:

```
  [review] ✓ FRESH
    0 days since last_reviewed (2026-04-17); 180 days until next review.
  ✓ All good.
```

---

## Stage 5 — Test the scripts yourself

Before handing this to an agent, run the scripts yourself against a real repo. This is the "dogfood against external code" principle — if you only test against the skill's own directory, you'll miss edge cases that matter.

```bash
cd /some/real/git/repo
python3 ~/git-cleanup/scripts/audit_branches.py main

# Expected: list of merged branches (empty if you're on a fresh clone)
```

```bash
# Dry-run the pruner (no --confirm)
echo "test-branch" | python3 ~/git-cleanup/scripts/prune.py
# Expected: "Refusing without --confirm" to stderr, exit 2
```

Real testing catches real bugs. In the Modal-skill case, dogfooding against an existing production skill surfaced two regex false-positives in `audit_skill.py` that self-testing had missed.

---

## Stage 6 — Write the trigger eval set

This is the part most people skip and it's the part that makes the difference. You need 10-20 queries that probe whether Claude actually invokes your skill at the right times.

Edit `evals/evals.json`:

```json
{
  "skill_name": "git-cleanup",
  "evals": [
    {"query": "my branch list is getting unwieldy, can you help me prune it", "should_trigger": true},
    {"query": "I've got like 40 feature branches from the last year, clean this mess up", "should_trigger": true},
    {"query": "delete all branches that have been merged into main", "should_trigger": true},
    {"query": "remove the v0.1-rc tags, they're stale", "should_trigger": true},
    {"query": "can you nuke the old release branches", "should_trigger": true},
    {"query": "git branch -d feature/auth", "should_trigger": true},
    {"query": "my gitignore is a mess, fix it", "should_trigger": false},
    {"query": "create a new feature branch for the auth work", "should_trigger": false},
    {"query": "undo my last commit", "should_trigger": false},
    {"query": "show me the commit history of feat/billing", "should_trigger": false},
    {"query": "set up branch protection rules", "should_trigger": false},
    {"query": "rebase this branch onto main", "should_trigger": false}
  ]
}
```

Rules of thumb for the negatives: they need to be **near-misses**. "Write me a fibonacci function" as a negative test for a git skill tells you nothing. "Rebase this branch onto main" tests whether your description is *discriminating* — it mentions a branch, it's git-related, but it's a different job. Getting that right is the whole point.

---

## Stage 7 — Run the behavioral eval (requires `claude` CLI)

If you have Claude Code installed, run the trigger-tuning loop:

```bash
cd $SF
python3 -m scripts.vendor.run_loop_hardened \
    --eval-set ~/git-cleanup/evals/evals.json \
    --skill-path ~/git-cleanup \
    --model claude-sonnet-4 \
    --max-iterations 5 \
    --verbose
```

This will:

1. **Preflight check** — verifies `claude` is on PATH. If missing, exits cleanly with install hint (not `FileNotFoundError` mid-run).
2. **Split your eval set** — 60% train, 40% test, stratified by `should_trigger`.
3. **Run each train query 3 times** against the current description, measuring trigger rate.
4. **Propose an improved description** if the current one failed any queries.
5. **Re-evaluate** with the improved description on the held-out test set.
6. **Iterate up to 5 times**, keeping the best-performing description by test score.
7. **Write results.json** with the full history.

Expected output (abbreviated):

```
[preflight] claude CLI: /usr/local/bin/claude
Split: 7 train, 5 test (holdout=0.4)

============================================================
Iteration 1/5
Description: Safely delete merged git branches and stale tags...
============================================================
Train: 5/7 correct, precision=100% recall=71% accuracy=71% (84.2s)
  [PASS] rate=3/3 expected=True:  my branch list is getting unwieldy...
  [FAIL] rate=1/3 expected=True:  git branch -d feature/auth
  ...

Improving description...
Proposed (12.3s): Safely delete merged git branches and stale tags. Use this skill whenever the user mentions cleaning up a repo, pruning branches, deleting tags... triggers on direct git-branch / git-tag commands with -d flag...

============================================================
Iteration 2/5
============================================================
Train: 7/7 correct, precision=100% recall=100% accuracy=100% (82.1s)
Test : 5/5 correct, precision=100% recall=100% accuracy=100%

All train queries passed on iteration 2!
```

The wrapper exits `0` on improvement, `1` on no-improvement, `2` on error — so you can wire this into CI.

**If you don't have `claude` installed,** skip this stage. The skill will still work; you just won't have empirical data on trigger accuracy. The static audits (Stage 4) are enough to ship on.

---

## Stage 8 — The benchmark (optional, for rigorous A/B)

If you want hard numbers on "does this skill actually help Claude do the task," the behavioral benchmark runs two configurations — with-skill and without-skill — and compares. This needs either Anthropic's `run_eval.py` (vendored at `scripts/vendor/anthropic_skill_creator/run_eval.py`) or a hand-rolled runner.

After you have a directory of `grading.json` files produced by those runs, the aggregation and viewer are skill-forge's job:

```bash
python3 $SF/scripts/aggregate_benchmark.py \
    ~/git-cleanup-workspace/iteration-1 \
    --skill-name git-cleanup --iteration 1

# → writes benchmark.json

python3 $SF/scripts/eval_viewer.py \
    ~/git-cleanup-workspace/iteration-1 \
    --out ~/git-cleanup-workspace/iteration-1/report.html \
    --skill-name git-cleanup

# → writes a self-contained HTML report, no server needed
```

Open `report.html` in any browser. You get the overall pass-rate delta, per-eval breakdown with stddev, and per-run drill-down with timing and token counts. See `README.md#benchmarks` for example screenshots.

---

## Stage 9 — Package and ship

```bash
python3 $SF/scripts/package_skill.py ~/git-cleanup --out ~/dist

# → ~/dist/git-cleanup.skill (a zip archive that validates on install)
```

That `.skill` file is what you distribute. Users install it with `gh skill install curtismercier/git-cleanup` (if you push to GitHub) or `claude skills install ./git-cleanup.skill` (local file).

---

## What you just did

You built a Tier 2 skill, ran it through four static audits, wrote a trigger eval set with 12 near-miss queries, optionally ran the behavioral eval and trigger-tuning loop, rendered results to HTML, and packaged for distribution.

**The pieces that matter most:**

- **Stage 0 (tier selection)** — skipping this is how skills become bloated.
- **Stage 2 (description first)** — the frontmatter description is load-bearing. Five of six Anthropic internal skills improved their trigger rate after running this loop.
- **Stage 4 (the four audits)** — catches what human review misses: stale pins, hallucinated pricing, slop attributions, deprecated APIs.
- **Stage 6 (near-miss negatives)** — obvious negative examples teach the description nothing. Adjacent ones sharpen it.

**The pieces you can skip first time through:**

- Stage 5 (manual script testing) — if your scripts are trivial
- Stage 7 (trigger tuning) — if you don't have `claude` CLI yet
- Stage 8 (benchmark) — only worth doing when you have two skill versions to compare

---

## What to read next

- `docs/00-verification-playbook.md` — when a later agent audits this skill, what do they check?
- `docs/03-research-phase.md` — the source-first research pattern for skills that target external APIs (what you'd need if `git-cleanup` were actually `modal-deploy` and the SDK changed monthly).
- `docs/05-anti-slop.md` — pointer to the full 10-heuristic reference.
- `references/description-tuning.md` — the pushy pattern, with before/after examples from real skills.
- `evals/README.md` — how the eval tooling interops with Anthropic's skill-creator.

---

## A note on when this walkthrough lies to you

If you copy this walkthrough and the outputs don't match, check:

1. **Python version** — some f-string features in the scripts require 3.10+.
2. **skill-forge version** — these outputs are from commit `2c1109f` (the initial v1.0.0 release). Later versions may add fields or tighten defaults.
3. **git state** — `audit_branches.py` silently returns empty if you're on a branch with no merged children. That's the script being correct, not broken.
4. **`claude` CLI version** — Stage 7 requires v2.90+ for the `--include-partial-messages` flag. Older versions fall back to post-hoc detection which is slower but works.

When skill-forge's own behavior drifts from this doc, that's what `ERRATA.md` is for. Log it there; update this walkthrough on the next release.
