# Modifications from upstream

Tracked modifications to the vendored `anthropic/skills/skill-creator` scripts.
**Minimal and surgical** — the goal is to keep these easy to rebase onto new upstream releases.

## File-level modifications

### `utils.py`, `run_eval.py`, `improve_description.py`, `run_loop.py`, `generate_report.py`

**Only change:** imports rewritten from `from scripts.X` → `from .X` so the vendor package is self-contained.

| Upstream | Our vendor |
|---|---|
| `from scripts.utils import parse_skill_md` | `from .utils import parse_skill_md` |
| `from scripts.run_eval import ...` | `from .run_eval import ...` |
| `from scripts.improve_description import ...` | `from .improve_description import ...` |
| `from scripts.generate_report import ...` | `from .generate_report import ...` |

No other edits. The code is Apache 2.0 (Anthropic PBC); originals live at
https://github.com/anthropics/skills/tree/main/skills/skill-creator/scripts

## Additive hardening in `run_loop_hardened.py`

A sibling module that wraps `run_loop()` with fixes for concrete gaps found
when dogfooding upstream. **The upstream scripts are not modified** — this
is a separate wrapper so rebases stay trivial.

| Gap | Upstream behavior | `run_loop_hardened` behavior |
|---|---|---|
| `claude` CLI missing | Raw `FileNotFoundError: 'claude'` mid-subprocess | Preflight-checks PATH with `shutil.which` and exits with a clear install-instruction message before any state is created |
| Silent worker failures | Worker exceptions become `triggered = False` — indistinguishable from a legitimate non-trigger | Tracks `errored` separately; if > `--max-error-rate` of runs fail, aborts iteration and reports infra vs. signal distinction |
| 1024-char retry is one-shot and unbounded-length on second failure | Retries once; second failure uses the too-long description anyway | Retries up to 3 times with exponentially tighter shorten prompts; refuses to emit over-budget descriptions — returns best-so-far instead |
| `main()` always exits 0 | CI can't distinguish "optimization made no progress" from "found a better description" | Exits 0 only when `best_description` differs from original AND improves score; exits 1 when no improvement; exits 2 on error |
| Ctrl+C leaves subprocess children | `KeyboardInterrupt` kills the Python process but running `claude -p` subprocesses continue briefly | Catches SIGINT, drains ProcessPoolExecutor, and prints best-so-far before exit |

Each improvement is gated by a CLI flag (`--preflight`, `--max-error-rate`,
`--strict-length`, etc.) and defaults to `on`. If you want upstream behavior
exactly, pass `--no-preflight --max-error-rate=1.0 --no-strict-length`.

## Rebase policy

When upstream releases updates:

1. Diff upstream against the original commit of these files (the SHA at the
   time of vendoring — preserved in the root ERRATA entry).
2. Apply the diff to our vendored copies.
3. Re-fix imports if upstream restructures them.
4. Run `python3 -m scripts.vendor.anthropic_skill_creator.run_eval --help`
   and `python3 -m scripts.vendor.anthropic_skill_creator.run_loop --help`
   to confirm CLI surface is intact.
5. If the improvements in `run_loop_hardened.py` are now upstream, remove
   them from there and log the removal in `ERRATA.md` as `absorbed`.
