# skill-forge

> A meta-skill for building Claude skills, plus the skills it produces.

This repo is both a **skill** and a **skill registry**. The [`skill-forge/`](./skill-forge) directory contains the authoritative meta-skill — the one that teaches Claude how to build other skills. Everything else in the repo is either a skill produced *by* skill-forge (published here as working examples and standalone tools) or a curated index of community-authored skills you might want to install alongside.

## Skills in this repo

<!-- SKILLS_INDEX -->
| Skill | Version | Install | Description |
|-------|---------|---------|-------------|
| [`modal-llm-inference`](./modal-llm-inference/) | `0.3.1` | `gh skill install curtismercier/skill-forge modal-llm-inference` | Deploy and run OpenAI-compatible LLM inference on Modal.com using vLLM. Covers serverless GPU deployment of open-weight… |
| [`skill-forge`](./skill-forge/) | `1.0.0` | `gh skill install curtismercier/skill-forge skill-forge` | Build a Claude skill from scratch — scoped to the actual task, not over-engineered. Use whenever the person asks you to… |
<!-- /SKILLS_INDEX -->

This table is generated from each skill's `SKILL.md` frontmatter by [`scripts/list_skills.py`](./scripts/list_skills.py) — don't edit it by hand. To regenerate:

```bash
python3 scripts/list_skills.py --update
```

## Quick install

```bash
# Needs gh CLI v2.90+
gh skill install curtismercier/skill-forge                     # interactive picker
gh skill install curtismercier/skill-forge skill-forge         # the meta-skill
gh skill install curtismercier/skill-forge modal-llm-inference # one specific skill
```

Works across [six supported hosts](https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/) — Claude Code, Copilot, Cursor, Codex, Gemini CLI, Antigravity. Pass `--agent <host>` to target a specific one; default is whichever host is active.

## What lives where

```
skill-forge/                       THIS REPO
├── README.md                      you are here
├── CONTRIBUTING.md                submission guide for contrib/
├── LICENSE                        MIT (this repo's code)
├── LICENSE-APACHE-ANTHROPIC.txt   Apache 2.0 (vendored Anthropic scripts)
│
├── skill-forge/                   ★ the meta-skill
│   ├── SKILL.md
│   ├── README.md
│   ├── docs/                      including the 10-walkthrough
│   ├── scripts/                   audit, validate, package + vendored Anthropic tooling
│   ├── evals/                     grader, comparator, analyzer agents + schemas
│   └── ...
│
├── modal-llm-inference/           produced by skill-forge
│   ├── SKILL.md
│   └── ...
│
├── contrib/                       curated index of community skills
│   ├── README.md                  submission rules
│   └── index.md                   external skills worth knowing about
│
└── scripts/                       repo-level utilities (not a skill)
    └── list_skills.py             regenerates the index above from frontmatter
```

## Contributing

- **Want your skill listed in `contrib/index.md`?** Read [`CONTRIBUTING.md`](./CONTRIBUTING.md). Indexed skills stay in their authors' own repos — we don't vendor them, we just link.
- **Want to propose changes to skill-forge itself?** File an issue describing what you hit, then PR. The `ERRATA.md` in each skill's directory is the right place to log drift you've caught but haven't fully resolved yet.

## License

- **This repo's own code** (including `skill-forge/` and `modal-llm-inference/`): MIT — see [`LICENSE`](./LICENSE).
- **Vendored Anthropic scripts** at `skill-forge/scripts/vendor/anthropic_skill_creator/`: Apache 2.0 — see [`LICENSE-APACHE-ANTHROPIC.txt`](./LICENSE-APACHE-ANTHROPIC.txt). Originals at [`anthropics/skills`](https://github.com/anthropics/skills).

If you install via `gh skill`, the tool writes tracking metadata (repo, ref, tree SHA) into the `SKILL.md` frontmatter on install — that's [how gh skill handles provenance](https://github.blog/changelog/2026-04-16-manage-agent-skills-with-github-cli/), not something we added.
