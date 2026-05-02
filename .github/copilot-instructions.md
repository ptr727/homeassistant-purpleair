# Copilot instructions

Repository conventions for GitHub Copilot (and any other agent reading this file).

The **canonical guide is [AGENTS.md](../AGENTS.md)** at the repo root — read it first. It covers project layout, branch flow, code style, the release pipeline, and what NOT to touch (e.g. the placeholder `manifest.json` `version` and the HA test matrix). Treat AGENTS.md as the source of truth; this file just summarizes the commit/PR-title rules so the VS Code AI commit-message and PR-title generators get them without an extra fetch.

## Commit messages and pull request titles

PRs squash-merge, so the PR title becomes the single commit message on `develop` / `main`. Titles are descriptive and have no versioning effect — versioning is handled by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) reading [version.json](../version.json) and git history, not by parsing commit messages.

### Format

- Imperative subject summarizing the change, ≤ 72 characters, no trailing period. ("Add 24-hour PM2.5 average sensor", not "Added X" or "Adds X".)
- Optional body, blank-line separated, explaining *why* the change is being made when that's non-obvious. The diff shows *what*.

### Rules

- Don't write `update stuff`, `wip`, `Bump X from Y to Z`, or other vague titles.
- Don't add `Co-Authored-By:` lines unless the user explicitly asks.
- Don't include version numbers or "minor"/"patch" in the title — NBGV handles versioning.

### Examples

```text
Surface 24-hour PM2.5 average as a separate sensor
Skip empty PurpleAir API responses during polling
Drop support for Home Assistant < 2026.4
Bump aiopurpleair from 2025.08.1 to 2025.09.0
Clarify HACS install steps in README
```

## When in doubt

Read [AGENTS.md](../AGENTS.md) for the full picture (release flow, files you must not touch, code style, workflow YAML conventions). Don't restate this file's rules in commit bodies or PR descriptions — keep those focused on the change itself.
