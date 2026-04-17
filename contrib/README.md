# contrib — community skills index

Skills in this directory aren't vendored — they're *indexed*. Each entry in [`index.md`](./index.md) points to a skill maintained in someone else's repo. Install them with `gh skill` the same way you'd install anything in this repo; you're just pointing at a different `OWNER/REPO` slug.

## Why an index and not a directory of vendored skills

- **Maintenance separation.** The author keeps full control. When they update, you update.
- **License clarity.** Each external skill brings its own license. We're not relicensing anything.
- **No silent drift.** If an indexed skill vanishes or gets taken over, it disappears from the index. It doesn't stay frozen here pretending to still work.

## Want your skill listed?

See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the submission rules. Short version: open a PR adding your entry to `index.md`, follow the existing template, and make sure `gh skill install` actually works against your published skill.
