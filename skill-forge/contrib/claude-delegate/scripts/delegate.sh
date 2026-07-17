#!/usr/bin/env bash
# delegate.sh — spawn a focused Claude sub-agent
#
# Usage:
#   delegate.sh "task" [--model sonnet] [--role /path/to/role.md] [--bg]
#
# Examples:
#   delegate.sh "Review src/auth.ts" --model haiku --role roles/reviewer.md
#   delegate.sh "Redesign the dashboard" --model fable --bg
#
# Requirements: claude CLI installed and authenticated.

set -euo pipefail

MODEL="sonnet"
ROLE_FILE=""
BACKGROUND=false
TASK=""
TOOLS="Read,Write,Edit,Bash"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --role) ROLE_FILE="$2"; shift 2 ;;
    --bg) BACKGROUND=true; shift ;;
    --tools) TOOLS="$2"; shift 2 ;;
    *) TASK="$1"; shift ;;
  esac
done

if [[ -z "$TASK" ]]; then
  echo "Usage: delegate.sh \"task\" [--model sonnet] [--role role.md] [--bg]"
  exit 1
fi

# Write task to temp file (avoids ARG_MAX)
TASK_FILE=$(mktemp /tmp/delegate-task-XXXXXX.txt)
echo "$TASK" > "$TASK_FILE"

# Build the command
CMD="ANTHROPIC_API_KEY= claude -p \"\$(cat '$TASK_FILE')\""
CMD="$CMD --model $MODEL"
CMD="$CMD --allowedTools $TOOLS"
CMD="$CMD --permission-mode acceptEdits"
CMD="$CMD --output-format json"

if [[ -n "$ROLE_FILE" && -f "$ROLE_FILE" ]]; then
  CMD="$CMD --system-prompt-file '$ROLE_FILE'"
fi

if $BACKGROUND; then
  SESSION="delegate-$(date +%s)"
  echo "Spawning background session: $SESSION"
  tmux new-session -d -s "$SESSION" "bash -c '$CMD'"
  echo "Monitor: tmux attach -t $SESSION"
  echo "Harvest: tmux capture-pane -t $SESSION -p -S -50"
else
  echo "Running: $MODEL — $TASK"
  eval "$CMD"
  rm -f "$TASK_FILE"
fi
