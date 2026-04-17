# Contributing

Two kinds of contributions here, with different paths.

## Contributing to skill-forge itself (or any skill in this repo)

The code and skills *in* this repo (under `skill-forge/`, `modal-llm-inference/`, and any future Curtis-authored skills) are maintained here directly. Contribute the normal way:

1. Open an issue describing what you hit or what you want to change. For drift (a skill references a deprecated API, pricing is stale, etc.) link the source that proves it.
2. Fork, branch, PR against `main`.
3. Before the PR lands, the skill's own audits must pass:
   ```bash
   cd skill-forge   # or whichever skill you touched
   python3 scripts/validate_skill.py .
   python3 scripts/audit_skill.py .
   python3 scripts/security_scan.py .
   python3 scripts/staleness_check.py .
   ```
4. If you're changing behavior rather than just fixing drift, add an entry to that skill's `ERRATA.md` with status `active` before the change, then move it to `absorbed` when the docs catch up. This is how drift history stays legible across versions.

Per-skill versioning uses a `version:` field in the SKILL.md frontmatter. Bump on any change that users would notice:

- Patch (`1.0.0` → `1.0.1`) — doc fixes, clarifications, no behavior change
- Minor (`1.0.0` → `1.1.0`) — new capability added, backward compatible
- Major (`1.0.0` → `2.0.0`) — rewrite, reorganization, or breaking workflow change

When you bump, add a git tag of the form `<skill-name>-v<version>` — e.g. `skill-forge-v1.1.0`, `modal-llm-inference-v0.4.0`. This lets users pin installs with `gh skill install curtismercier/skill-forge skill-forge@v1.1.0`.

## Getting your own skill listed in `contrib/`

If you've authored a skill and want it indexed in [`contrib/index.md`](./contrib/index.md), the deal is straightforward:

- **Your skill stays in your repo.** We link to it — we don't vendor it.
- **It must be installable.** The `gh skill install <your-org>/<your-repo> <skill-name>` command must work.
- **It must have a real description.** Not "a skill for X" — the kind of pushy, specific description [skill-forge's description-tuning reference](./skill-forge/references/description-tuning.md) argues for. If we can tell at a glance whether it'll trigger for the right queries, that's the bar.
- **It must not duplicate or contradict a skill already in this repo.** If your skill overlaps with one of ours, that's fine, but the entry should name the difference clearly.

### How to submit

Open a PR that adds your skill to `contrib/index.md` following the existing template. Include:

| Field | Required? | Notes |
|-------|-----------|-------|
| Name | Yes | Must match the `name:` in your SKILL.md |
| Repo | Yes | `owner/repo` slug on GitHub |
| One-line description | Yes | Verbatim copy of your SKILL.md `description:` field, or tighter |
| Author | Yes | Your GitHub handle |
| Install command | Yes | The exact `gh skill install` invocation |
| Version | Recommended | Current release tag |
| Compatibility notes | Optional | If your skill has unusual dependencies (Claude Code only, requires specific CLI, etc.) |

We review PRs looking for: accurate description, working install, no redundancy with existing entries, nothing that encourages harm. If your skill is solid and the entry is accurate, we'll merge it. We're not gatekeeping on taste beyond that.

### What we'll remove

Entries that stop working, that redirect to spam, that change drastically from what was indexed, or that turn out to contain prompt injection or malware get pulled. We'll attempt to contact the author first when removal is because the repo went stale rather than because it turned hostile.

## Questions

Open an issue. Tag it `question` if you're not sure whether it belongs as an issue or a PR.
