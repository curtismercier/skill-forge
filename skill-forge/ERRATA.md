# ERRATA — skill-forge

Drift log for the skill-creation advice itself. Pattern from [jezweb/claude-skills](https://github.com/jezweb/claude-skills/blob/main/CLAUDE.md).

**Lifecycle:** `active` (drift found, correction here) → `absorbed` (folded into main docs) → `outdated` (the advice changed again).

Add new entries at the top.

---

## 2026-04-17 — Restructured as monorepo; skill-forge is now one skill among several

**Status:** `absorbed`
**Location:** Repo root → `curtismercier/skill-forge` (unchanged). skill-forge content → `skill-forge/` subdirectory. New peer: `modal-llm-inference/`. New supporting structure: `contrib/` (community index), `scripts/list_skills.py` (auto-generates README index from frontmatter).
**Drift:** Earlier drafts assumed a single-skill repo. `gh skill install curtismercier/skill-forge` would have worked only for skill-forge itself with no room to publish modal-llm-inference or future skills as siblings. Install commands in the README pointed at `git clone https://github.com/curtismercier/skill-forge.git ~/.claude/skills/skill-forge` which would have installed the *entire monorepo* under one skill directory — a mis-install that `gh skill` itself would catch, but the git-clone path would silently ruin.
**Correct value:** The repo now follows the canonical monorepo pattern used by `anthropics/skills` and `github/awesome-copilot`: each skill is a top-level subdirectory with its own `SKILL.md`, standard optional subdirs (`scripts/`, `references/`, etc.), and frontmatter metadata including `version`, `author`, `produced-by`, and `source-style`. The monorepo root holds a registry README auto-generated from each skill's frontmatter, a `CONTRIBUTING.md` covering both internal PRs and `contrib/` submissions, and licenses that apply to the whole tree. `gh skill install curtismercier/skill-forge <skill-name>` is the canonical install form; sparse-clone instructions are provided for the no-gh path. Per-skill version tags use `<skill-name>-v<version>` (e.g. `skill-forge-v1.0.0`, `modal-llm-inference-v0.3.1`).
**How to verify:** Root `README.md` shows the auto-generated skill index inside `<!-- SKILLS_INDEX -->` markers. `python3 scripts/list_skills.py` (at repo root) regenerates it. All four audit tools pass on both `skill-forge/` and `modal-llm-inference/` from their respective locations. The walkthrough's path references (`docs/10-walkthrough.md`) now use a `$SF` environment variable so they work regardless of where the user installs skill-forge.
**Why not separate repos:** Considered. Rejected because (a) cross-skill versioning in a single place keeps coherent releases sane, (b) the `ERRATA.md` pattern cross-references between skills often enough that directory-local is better than cross-repo, (c) `gh skill` handles multi-skill repos natively and the [agentskills.io spec](https://agentskills.io/specification) only requires the immediate parent dir to match `name:`, not the full path.

---

## 2026-04-17 — Vendored Anthropic's skill-creator execution scripts

**Status:** `absorbed`
**Location:** `scripts/vendor/anthropic_skill_creator/` (vendored files), `scripts/vendor/run_loop_hardened.py` (skill-forge wrapper), `LICENSE-APACHE-ANTHROPIC.txt` (root)
**Drift:** Earlier this release described skill-forge as "deliberately not reimplementing" Anthropic's `run_eval.py` / `run_loop.py` / `improve_description.py` — treating them as a soft dependency. In practice this meant users needed a separate install of skill-creator, and skill-forge would silently break when Anthropic restructured their tree.
**Correct value:** Vendored the five execution scripts (`utils.py`, `run_eval.py`, `improve_description.py`, `run_loop.py`, `generate_report.py`, ~1250 LOC total) under Apache 2.0 at `scripts/vendor/anthropic_skill_creator/`. Only modification to upstream: `from scripts.X` → `from .X` relative imports so the package is self-contained. Apache license text preserved at repo root. Added `scripts/vendor/run_loop_hardened.py` — a skill-forge wrapper around the vendored `run_loop()` that fixes five real gaps found when reading the upstream code: (1) raw `FileNotFoundError` when `claude` CLI is missing, (2) worker exceptions silently counted as non-triggers, (3) one-shot 1024-char retry emits over-budget descriptions on second failure, (4) `main()` always exits 0 regardless of outcome, (5) SIGINT leaves subprocess children. Each hardening is opt-outable; `--no-preflight --max-error-rate=1.0 --no-strict-length --exit-always-zero` reproduces upstream exactly.
**How to verify:** `python3 -m scripts.vendor.run_loop_hardened --help` shows the wrapper; exit code 2 with install hint when `claude` CLI is missing; all four skill-forge audits pass on the expanded 45-file tree.
**Rebase plan:** See `scripts/vendor/anthropic_skill_creator/IMPROVEMENTS.md` — diff upstream against our vendored copies, reapply our relative-import fix, re-test CLI surface. If our hardenings land upstream, remove them from `run_loop_hardened.py` and log as absorbed.

---

## 2026-04-17 — Absorbed skill-creator behavioral-eval patterns

**Status:** `absorbed`
**Location:** `evals/agents/`, `evals/schemas/`, `scripts/aggregate_benchmark.py`, `scripts/eval_viewer.py`, README
**Drift:** Anthropic's March 2026 skill-creator update added Eval/Improve/Benchmark modes with real behavioral testing infrastructure (grader/comparator/analyzer subagents, run_eval.py, run_loop.py, aggregate_benchmark.py, generate_review.py). skill-forge previously only shipped static-analysis tooling; users wanting behavioral eval had to switch tools entirely.
**Correct value:** skill-forge is now schema-compatible with Anthropic's skill-creator. The three agent prompts (grader, comparator, analyzer) were adapted (tier-aware, ERRATA-aware, not verbatim copies). `aggregate_benchmark.py` and `eval_viewer.py` were written fresh as stdlib-only ports that produce the same JSON outputs skill-creator consumes. Anthropic's `run_eval.py`/`run_loop.py`/`improve_description.py` are explicitly NOT reimplemented — they require `claude -p` CLI and benefit from Anthropic's active maintenance.
**How to verify:** run `aggregate_benchmark.py` on any directory produced by Anthropic's `run_eval.py`; output should be parseable by their `generate_review.py`. See `evals/schemas/schemas.md` for the contract.
**Absorbed in commit:** 2026-04-17. Full eval/ subtree added with attribution to `anthropics/skills` throughout.

---

## 2026-04-16 — Ecosystem shift: `gh skill` CLI + reframing of validation

**Status:** `absorbed`
**Location:** SKILL.md, README.md, docs/09-ecosystem.md, scripts/new_skill.py, scripts/validate_skill.py, scripts/staleness_check.py
**Drift:** On 2026-04-16, GitHub shipped `gh skill` as part of `gh` CLI v2.90.0+, materially changing the install story. Skill-forge's original install docs said "git clone to `~/.claude/skills/`" without mentioning `gh skill install`. Separately, an initial draft of this round referenced `agentskills.io` as "the open cross-vendor specification" — overstating what's actually a recently-surfaced proposed spec. The practical format authority is Anthropic's `anthropics/skills` repo; agentskills.io is worth watching but isn't yet the industry-adopted standard.
**Correct value:** Install docs present `gh skill install` as an equal-weight option (not primary, not absent), and explicitly state skill-forge does not depend on it. Ecosystem doc describes the three layers honestly: skill-forge (methodology) → `gh skill` (distribution, optional) → Anthropic's SKILL.md format (what clients parse). agentskills.io gets a brief mention as one of several ecosystem efforts, not as The Spec.
**How to verify:** compare current skill-forge framing against https://github.com/anthropics/skills (canonical format) and https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/ (gh skill launch).
**Absorbed in commit:** 2026-04-16 update pass. Added `docs/09-ecosystem.md`. Updated SKILL.md and README with three equal-weight install options. `new_skill.py` validates names and supports `--license`, `--compatibility` args. `validate_skill.py` delegates to `skills-ref` opportunistically with a `--no-delegate` flag. `staleness_check.py` docstring reframed as complementary to `gh skill update`.

---

## 2026-04-16 — skill-forge initial shipment

**Status:** `absorbed`
**Location:** all of skill-forge
**Drift:** no drift — this is the initial version. Captured as a starting reference point so future entries have context.
**Correct value:** n/a
**How to verify:** compare current advice against https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md and the jezweb/claude-skills patterns. Diff any material changes against this release.
**Next review:** when Anthropic ships a major revision of its skill-creator guidance, or when community patterns (awesome-claude-skills, etc.) show meaningful shift.

---

## Template for new entries

```markdown
## YYYY-MM-DD — <one-line summary>

**Status:** `active` | `absorbed` | `outdated`
**Location:** <files:lines in skill-forge>
**Drift:** <what skill-forge says, why it's no longer best practice>
**Correct value:** <what it should say>
**How to verify:** <specific URL or command>
**How to fix when absorbing:** <concrete edit>
```

## Signals that skill-forge advice has drifted

- Anthropic ships new skill format features (e.g. new frontmatter fields, changed install paths)
- New canonical repos emerge in the awesome-claude-skills ecosystem with patterns we should absorb
- The `gh_research.py` tool's GitHub API calls break (GitHub API versioning)
- Community feedback surfaces a failure mode not covered in anti-slop-heuristics.md

## Known limitations of this skill (not drift, just scope)

- Only supports the `.skill` zip format — doesn't help with Claude Code plugin format variants if those differ
- Doesn't auto-generate evals (Anthropic's skill-creator has a richer eval workflow; this one is intentionally simpler)
- `gh_research.py` can't search private repos unless `GITHUB_TOKEN` has access — no special handling for self-hosted Git
