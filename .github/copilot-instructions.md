# Copilot instructions

Repository conventions for GitHub Copilot (and any other agent reading this file).

The **canonical guide is [AGENTS.md](../AGENTS.md)** at the repo root — read it first. It covers project layout, branch flow, code style, the release pipeline, and what NOT to touch (e.g. `manifest.json` `version`, the HA test matrix). Treat AGENTS.md as the source of truth; this file just summarizes the commit/PR-title rules so the VS Code AI commit-message and PR-title generators get them without an extra fetch.

## Commit messages and pull request titles

PRs squash-merge, so the PR title becomes the single commit message on `develop` / `main`. A required CI check blocks merge on non-conformant titles. Versioning is automated by release-please reading the title.

### Format

```text
<type>(<optional scope>): <imperative summary, lowercase, no trailing period>

[optional body, wrapped at 72 chars, blank-line separated, explains *why*]

[optional BREAKING CHANGE: ... footer]
```

### Allowed types and their effect on the next release

- `feat:` → minor bump (new user-visible capability)
- `fix:` / `perf:` → patch bump (bug fixes, perf wins)
- `<type>!:` or `BREAKING CHANGE:` footer → major bump (`feat!:`, `fix!:`, `refactor!:`, etc.; `!` on any type signals a breaking change per Conventional Commits)
- `chore:` / `docs:` / `refactor:` / `test:` / `build:` / `ci:` / `revert:` → no release

If you're unsure whether the change should ship as a release, prefer `chore:`. Dependency bumps use `chore(deps): ...`.

### Rules

- Subject ≤ 72 characters, lowercase first word, **no trailing period**.
- Imperative mood: "add X" not "added X" / "adds X".
- Use `(scope)` when it narrows usefully: `(coordinator)`, `(sensor)`, `(workflows)`, `(deps)`, `(docs)`.
- Don't put bump magnitude in the title ("minor", "patch") — the type carries that.
- Don't write `update stuff`, `wip`, `Bump X from Y to Z`, or other vague titles — the lint will reject them.
- Don't add `Co-Authored-By:` lines unless the user explicitly asks.

### Examples

```text
feat: surface 24-hour PM2.5 average as a separate sensor
fix(coordinator): skip empty PurpleAir API responses during polling
feat!: drop support for Home Assistant < 2026.4
chore(deps): bump aiopurpleair from 2025.08.1 to 2025.09.0
docs: clarify HACS install steps in README
```

## When in doubt

Read [AGENTS.md](../AGENTS.md) for the full picture (release flow, files you must not touch, code style, workflow YAML conventions). Don't restate this file's rules in commit bodies or PR descriptions — keep those focused on the change itself.
