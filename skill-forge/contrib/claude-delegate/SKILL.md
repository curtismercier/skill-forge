---
name: claude-delegate
description: Delegate work to Claude models (fable, sonnet, haiku) via the official claude CLI. Spawn focused child agents for coding, review, architecture, or batch tasks. Use when you want a specialist sub-agent instead of doing everything yourself.
license: MIT
metadata:
  author: curtismercier / meetsoma
  version: "1.0.0"
  source-style: authored
  home-repo: curtismercier/skill-forge
  created: 2026-07-17
---

# claude-delegate — spawn focused Claude sub-agents

> **Living skill — update as delegation patterns evolve.** This skill captures what works today (July 2026). As we discover better patterns, batch strategies, or new CLI flags, update this file. It ships to other Soma instances, Freebuff, and any Claude-powered agent.

This skill teaches any Claude-powered agent how to delegate work to other Claude models via `claude -p`. Instead of doing everything in one session, spawn specialists.

**Harness-agnostic.** Works whether you bill through the Claude subscription (blank `ANTHROPIC_API_KEY`) or the API (set your key). The pattern is the same; only the billing path differs.

## When to use this

- You have 3+ related tasks that can run in parallel or sequence
- A task needs a different persona (UI designer, architect, auditor)
- You want a cheaper/faster model for mechanical work (haiku) and a smarter model for reasoning (fable)
- You're mentoring another agent and want to teach them this pattern

## The core pattern

```bash
claude -p "your task here" \
  --model fable \
  --system-prompt-file /tmp/role.txt \
  --allowedTools Read Write Edit Bash \
  --permission-mode acceptEdits \
  --output-format json
```

**Critical: use `--system-prompt-file`, not `--append-system-prompt`.** The inline flag hits the OS argument size limit (~128KB) for large roles. Write the role to a temp file instead.

## Decision tree

| Situation | Mode | Model |
|-----------|------|-------|
| Quick audit, grep, read-only | Sync | haiku |
| Code generation, implementation | Sync | sonnet |
| Architecture, UI design, deep reasoning | Sync/background | fable |
| Batch of 3+ tasks | Background | sonnet or fable |
| Free-tier (no subscription) | `soma -p` | deepseek-v4-flash-free |

## Creating a role file

A role is a markdown file that becomes the child's system prompt:

```markdown
# Code Reviewer

You are an expert code reviewer. For every file:
1. Check for bugs and security issues
2. Evaluate performance
3. Suggest improvements

## Rules
- Be specific. Cite file:line.
- Don't rewrite code — suggest changes.
```

Write it to a temp file and pass via `--system-prompt-file`:

```bash
cat > /tmp/reviewer-role.md << 'EOF'
# Code Reviewer
...
EOF

claude -p "Review src/auth.ts for security issues" \
  --model sonnet \
  --system-prompt-file /tmp/reviewer-role.md \
  --allowedTools Read Grep Glob \
  --output-format json
```

## Batch tasks

Instead of spawning 5 separate agents (paying ~40K tokens boot cost each), do all 5 in one call:

```bash
cat > /tmp/batch-tasks.md << 'EOF'
Do ALL of these in one session. Commit after each.

## Task 1: Fix login bug
Edit src/auth.ts — check for null user on line 42.

## Task 2: Add test
Create src/auth.test.ts — test the null user case.

## Task 3: Update docs
Edit docs/auth.md — document the fix.
EOF

claude -p "$(cat /tmp/batch-tasks.md)" \
  --model sonnet \
  --allowedTools Read Write Edit Bash \
  --output-format json
```

## Background mode (long-running tasks)

For tasks that take 5+ minutes, use tmux to run in background:

```bash
# Write role + task to temp files
cat > /tmp/role.txt << 'EOF'
# UI Designer
...
EOF
cat > /tmp/task.txt << 'EOF'
Redesign the dashboard with the new color palette.
EOF

# Spawn in tmux
tmux new-session -d -s design-task \
  "ANTHROPIC_API_KEY= claude -p \"\$(cat /tmp/task.txt)\" \
   --model fable \
   --system-prompt-file /tmp/role.txt \
   --allowedTools Read Write Edit Bash \
   --permission-mode acceptEdits"

# Monitor
tmux capture-pane -t design-task -p

# Harvest when done
tmux capture-pane -t design-task -p -S -50
```

## Post-delegation checklist

After every child completes:
1. Check git log — did they actually commit?
2. Run typecheck/tests — did they break anything?
3. Read their output — any MLR suggestions to fold into the role?
4. Kill the tmux session — `tmux kill-session -t design-task`

## Model costs (July 2026)

| Model | Input (per 1M) | Output (per 1M) | Best for |
|-------|---------------|-----------------|----------|
| fable | $10 | $50 | Architecture, deep reasoning |
| sonnet | $3 | $15 | Implementation, code gen |
| haiku | $0.80 | $4 | Quick audit, mechanical |
| opus | $15 | $75 | Critical review |

All draw from your Claude subscription — no extra API billing when `ANTHROPIC_API_KEY` is blanked.

## Related

- `references/claude-cli-flags.md` — full CLI reference
- `references/role-template.md` — detailed role template with frontmatter
- `scripts/delegate.sh` — ready-to-use delegation script
