# Community skills index

Curated list of skills maintained elsewhere that work well alongside the skills in this repo. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) to get yours listed.

**Last reviewed:** 2026-04-17

---

<!-- CONTRIB_INDEX_START -->

_No entries yet. This list opens when the first PR lands. If you're thinking "mine should be the first one," open a PR — see [../CONTRIBUTING.md](../CONTRIBUTING.md)._

<!-- CONTRIB_INDEX_END -->

---

## Template for new entries

Copy this block, fill it in, place it in alphabetical order inside the `CONTRIB_INDEX_START`/`CONTRIB_INDEX_END` markers:

```markdown
### skill-name

- **Repo:** [`owner/repo`](https://github.com/owner/repo)
- **Author:** [@author](https://github.com/author)
- **Version:** `v0.1.0`
- **Install:** `gh skill install owner/repo skill-name`
- **Compatibility:** (optional — note Claude Code-only, requires CLI X, etc.)

One-line description of what the skill does and when to use it, verbatim from the SKILL.md `description` field or tighter. Keep under 200 chars.
```

## Not sure your skill is a good fit?

The bar is pragmatic, not ideological:

- **Real use case.** Something you built because you actually needed it, not demo-ware.
- **Tested install.** `gh skill install` against your repo completes cleanly, and the resulting skill triggers on the kinds of queries your description promises.
- **Reasonable description.** See [`../skill-forge/references/description-tuning.md`](../skill-forge/references/description-tuning.md) — a description that's specific, pushy, and names real trigger phrases, not "a skill for X."
- **Honest scope.** If it only works in Claude Code, say so. If it only handles one dialect of whatever it claims, say so.

No gatekeeping beyond that. If it's real, useful, and accurately described, we'll list it.
