# Claude CLI Flags Reference

Key flags for `claude -p` delegation. Full reference: `claude --help` or [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code/cli-reference).

## Essential flags

| Flag | What it does |
|------|-------------|
| `-p "task"` | Non-interactive print mode — runs task and exits |
| `--model <alias>` | Model: fable, sonnet, opus, haiku, or full ID |
| `--system-prompt-file <path>` | Replace system prompt with file contents. **Use this, not --append-system-prompt.** |
| `--append-system-prompt "text"` | Append to default prompt. Avoid — hits ARG_MAX for large roles. |
| `--allowedTools <list>` | Tools the child can use: Read, Write, Edit, Bash, Glob, Grep, WebSearch, WebFetch |
| `--permission-mode acceptEdits` | Auto-accept edit permissions. Required for unattended children. |
| `--output-format json` | Machine-readable output (parse the `result` field) |

## Budget + safety

| Flag | What it does |
|------|-------------|
| `--max-turns N` | Cap agent turns. Prevents runaway children. |
| `--max-budget-usd N` | Dollar cap. Print mode only. |
| `ANTHROPIC_API_KEY= ` (prefix) | Blank the API key so billing draws from subscription, not extra-usage. Critical. |

## Performance

| Flag | What it does |
|------|-------------|
| `--exclude-dynamic-system-prompt-sections` | Moves cwd/env to first user message. Better prompt-cache reuse across delegations. |
| `--bare` | Skip hooks, skills, plugins, MCP. Faster startup for scripted calls. |

## Background mode (tmux)

For long-running tasks, wrap in tmux:

```bash
ANTHROPIC_API_KEY= claude -p "task" \
  --model sonnet \
  --system-prompt-file /tmp/role.txt \
  --allowedTools Read Write Edit Bash \
  --permission-mode acceptEdits
```

The `ANTHROPIC_API_KEY=` prefix is essential — without it, `claude -p` bills extra-usage instead of the subscription.

## Avoiding ARG_MAX

Never pass large prompts inline. Always use files:

```bash
# WRONG — may hit OS argument size limit
claude -p "$LONG_TASK" --append-system-prompt "$HUGE_ROLE_PROMPT"

# RIGHT — no limit
claude -p "$(cat /tmp/task.txt)" --system-prompt-file /tmp/role.txt
```
