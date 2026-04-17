"""
Vendored behavioral-eval scripts from Anthropic's skill-creator.

Source:  https://github.com/anthropics/skills/tree/main/skills/skill-creator
License: Apache 2.0 (see ../../LICENSE-APACHE-ANTHROPIC.txt)

WHY THESE LIVE HERE
-------------------
These scripts shell out to `claude -p` (the Claude Code CLI) to execute
skills, evaluate trigger rates, and iteratively improve descriptions.
They're vendored rather than listed as a soft dependency because:

1. Anthropic's skill-creator evolves — silently relying on their in-tree
   scripts means skill-forge breaks when their structure changes. Vendoring
   pins a known-good version.
2. Users running skill-forge shouldn't need to install skill-creator just
   to run trigger-tuning.
3. We've made minor adaptations (relative imports so the vendor package is
   self-contained; see IMPROVEMENTS.md in this directory).

WHAT'S HERE
-----------
- utils.py                 — parse_skill_md() helper
- run_eval.py              — runs trigger queries against `claude -p`
- improve_description.py   — calls Claude to propose a better description
- run_loop.py              — eval + improve loop with train/test split
- generate_report.py       — HTML report from loop output

RUNTIME REQUIREMENTS
--------------------
These scripts require the `claude` CLI to be on PATH (Claude Code, v2.90+
recommended). Without it, the subprocess calls fail cleanly with an
instructive error message.

The rest of skill-forge runs with zero dependencies beyond Python's stdlib.
"""
