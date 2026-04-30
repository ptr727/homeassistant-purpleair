# Agent guide

Notes for AI coding agents working in this repo. Keep responses concise; prefer editing existing files over creating new ones; never narrate internal deliberation.

## What this is

A HACS-installable Home Assistant **custom integration** for PurpleAir air-quality sensors. Code lives in [custom_components/purpleair/](custom_components/purpleair/). Python 3.14 only, `mypy --strict`, ruff, [platinum quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

## Branches and merging

- Pipeline is `feature → develop → main`. Both `develop` and `main` are protected; everything lands via PR.
- **Squash-only merges.** PR title becomes the commit message. Never use merge commits or rebase merges — release-please parses the squashed PR title.
- Open feature PRs against `develop`. `develop → main` is how stable releases are cut.

## Commit messages and PR titles (enforced)

PR titles drive versioning via [release-please](https://github.com/googleapis/release-please). PRs squash-merge, so the PR title becomes the single commit message on `develop` / `main`. [test-pull-request.yml](.github/workflows/test-pull-request.yml) has a required `pr-title-lint` job that blocks merge on non-conformant titles. Tag protection means the release App is the only writer for SemVer-shaped tags, so non-conformant titles can't accidentally produce a release.

### Format

    <type>(<optional scope>): <imperative summary, lowercase, no trailing period>

    [optional body, wrapped at 72 chars, blank-line separated]

    [optional BREAKING CHANGE: ... footer]

### Types and bump effect

| Prefix                                  | Bump on next release | Use for                                 |
| --------------------------------------- | -------------------- | --------------------------------------- |
| `<type>!:` or `BREAKING CHANGE:` footer | major                | API/behaviour breaks for end users      |
| `feat:`                                 | minor                | New user-visible capability             |
| `fix:` / `perf:`                        | patch                | Bug fixes, perf wins                    |
| `chore:`                                | none                 | Dep bumps, internal cleanup, tooling    |
| `docs:`                                 | none                 | Doc-only changes                        |
| `refactor:`                             | none                 | Restructuring without behaviour change  |
| `test:`                                 | none                 | Test-only changes                       |
| `build:` / `ci:`                        | none                 | Build system / CI config                |
| `revert:`                               | none                 | Reverting a previous commit (use `git revert`-style PR title) |

Per Conventional Commits, `!` after any type marks a breaking change and forces a major bump — `feat!:`, `fix!:`, `refactor!:`, etc. are all valid.

### Rules

- Subject ≤ 72 characters, lowercase first word, **no trailing period**.
- Use the imperative mood ("add X", not "added X" or "adds X").
- Use `(scope)` when narrowing helps: `(coordinator)`, `(sensor)`, `(workflows)`, `(deps)` for dep bumps, `(docs)` for docs.
- Body explains **why**, not what. The diff shows what.
- Bump magnitude flows from the **type**, so don't say "minor" / "patch" in the title — pick the right type instead.
- For Dependabot-shaped PRs, use `chore(deps): ...` so they don't trigger a release. A maintainer may retitle a security update to `fix(deps): ...` before merge if it should ship a patch.
- If you're unsure whether to release, prefer `chore:`.

### Examples

    feat: surface 24-hour PM2.5 average as a separate sensor
    fix(coordinator): skip empty PurpleAir API responses during polling
    feat!: drop support for Home Assistant < 2026.4
    chore(deps): bump aiopurpleair from 2025.08.1 to 2025.09.0
    docs: clarify HACS install steps in README
    ci: pin actionlint to v1.7.7

### What NOT to do

- Don't manually bump `version` in `manifest.json` — release-please owns that.
- Don't open a PR titled `update stuff`, `wip`, or `Bump X from Y to Z` (Dependabot's default; configure `commit-message.prefix: "chore"` in `dependabot.yml` to avoid this).
- Don't add `Co-Authored-By:` lines for AI tools unless the user explicitly asks.

## Versioning — DO NOT touch manually

- The `version` field in [custom_components/purpleair/manifest.json](custom_components/purpleair/manifest.json) is owned by **release-please**. Do not bump it in feature PRs — release-please opens its own PR that does that, and merging your PR with a manual bump will desync `.release-please-manifest.json` and `.release-please-manifest-develop.json`.
- [hacs.json](hacs.json) has no `version` field; HACS reads the integration version from `manifest.json`. Don't add one.
- The `homeassistant` field in `hacs.json` is the **minimum** required HA version (hand-maintained alongside the pin in [requirements.txt](requirements.txt) and the `minimum` entry in [.github/ha-test-versions.json](.github/ha-test-versions.json)).

## HA test matrix — DO NOT touch manually

- [.github/ha-test-versions.json](.github/ha-test-versions.json) drives the pytest matrix in [test-release-task.yml](.github/workflows/test-release-task.yml). Two pinned versions: `minimum` (hand-maintained) and `latest` (bot-maintained by [check-ha-version.yml](.github/workflows/check-ha-version.yml), which derives both `ha` and `pytest-hacc` from PyPI's latest `pytest-homeassistant-custom-component` release).
- Bumping the **minimum** is intentional and rare — do it in a `feat!:` PR that also updates `hacs.json` `homeassistant`, the `requirements.txt` pin, and any code that needs the new HA API.
- **Don't** add `homeassistant` to Dependabot updates (it's explicitly ignored in [dependabot.yml](.github/dependabot.yml)) — `check-ha-version.yml` owns it.

## Release flow (so you understand what to expect)

1. Your `feat:`/`fix:` PR squash-merges into `develop` → push triggers [release-please.yml](.github/workflows/release-please.yml).
2. The bot (App `ptr727-codegen[bot]`) opens a release PR titled `chore(develop): release X.Y.Z-beta.N` that bumps `manifest.json` and `.release-please-manifest-develop.json`.
3. [merge-bot-pull-request.yml](.github/workflows/merge-bot-pull-request.yml) auto-merges the release PR once CI passes. **The merge runs under the App token** (not GITHUB_TOKEN) so the resulting push triggers release-please.yml again — without that, GitHub's recursion guard would suppress the trigger and no tag would ever be pushed.
4. release-please.yml's second run pushes tag `X.Y.Z-beta.N` and creates the GitHub Release with auto-generated notes. The tag push triggers [publish-release.yml](.github/workflows/publish-release.yml) → [build-release-task.yml](.github/workflows/build-release-task.yml), which builds `purpleair.zip` and uploads it as an asset to the just-created release.
5. To ship stable, open `develop → main` PR. Same loop produces `chore(main): release X.Y.Z` with no `-beta` suffix.

## Code style

- Run `scripts/fix` to auto-fix (ruff format + ruff check --fix); `scripts/lint` to verify (matches CI: ruff format --check + ruff check + mypy --strict).
- Tests: `pytest -ra` after `pip install -r requirements-test.txt`.
- **Comments**: only when the *why* is non-obvious — hidden constraint, subtle invariant, workaround. Don't explain *what* the code does. No multi-paragraph docstrings; one-line comment max.
- **Don't add backwards-compat shims, `# removed` markers, or rename-to-`_` for unused vars** — just delete.
- **Don't add error handling for impossible cases** — trust internal code; only validate at boundaries.

## Workflow YAML conventions

- Pin actions to a SHA with a trailing `# vX.Y.Z` comment, e.g. `uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2`. Dependabot bumps these.
- Step names end in `step`, job names end in `job`.
- Top-level workflows have a `concurrency:` block keyed on `${{ github.workflow }}-${{ github.ref }}`.
- Shell scripts start with `set -euo pipefail`.
- After editing any workflow, validate with `actionlint .github/workflows/*.yml` (preinstalled in the devcontainer; see "Linters available in the devcontainer" below).

## Bot identity and secrets

- App: `ptr727-codegen[bot]`. Repo secrets:
  - `CODEGEN_APP_CLIENT_ID` — the App's Client ID (Settings → Developer settings → GitHub Apps → your App → "Client ID").
  - `CODEGEN_APP_PRIVATE_KEY` — the App's private key (PEM contents).
- With no "Require approvals" on `develop`/`main`, bot PRs auto-merge as soon as `check-workflow-status` is green — no branch-protection bypass needed. If approvals get turned on, both `ptr727-codegen[bot]` and `dependabot[bot]` need to be on the bypass list. If a tag ruleset restricts pushing, `ptr727-codegen[bot]` needs to be on the tag-bypass list (release-please pushes the release tag directly after the release PR merges).
- Generate tokens with `actions/create-github-app-token` — never hard-code or use a PAT.
- Bot PRs are auto-merged by [merge-bot-pull-request.yml](.github/workflows/merge-bot-pull-request.yml) which has guarded jobs for: Dependabot (skips semver-major), release-please (branch prefix `release-please--branches--`), and HA-version bumps (branch prefix `ha-version-bump/`).

## Common tasks

- **Add a feature**: feature branch from `develop` → code + tests → `scripts/fix` → `scripts/lint` → `pytest` → PR titled `feat: …` against `develop`.
- **Fix a bug**: same as above with `fix: …` title.
- **Add a Dependabot config / new ecosystem**: edit [.github/dependabot.yml](.github/dependabot.yml); ensure `commit-message.prefix: "chore"` (else PR-title lint fails).
- **Investigate a failing release-please run**: check that `.release-please-manifest*.json` versions match the latest published tag for that branch. Off-by-one means manual seeding is needed.
- **Don't manually create GitHub releases.** The pipeline owns this end-to-end.

## Devcontainer

[.devcontainer.json](.devcontainer.json) bind-mounts host SSH signing key, `~/.config/git/allowed_signers`, and `~/.config/gh` so commits inside the container are SSH-signed and `gh` is pre-authenticated. See [README.md](README.md#devcontainer-host-prerequisites).

## Linters available in the devcontainer

The devcontainer ships these CLIs out of the box. Use them locally before pushing — CI runs `ruff` + `mypy --strict` + `pytest`, but actionlint/shellcheck/yamllint/markdownlint are not yet wired into CI, so local runs are the only gate.

| Tool          | What it lints                                     | Quick command                                      |
| ------------- | ------------------------------------------------- | -------------------------------------------------- |
| `actionlint`  | GitHub Actions workflow YAML (also runs shellcheck on `run:` blocks if shellcheck is on PATH, which it is here) | `actionlint .github/workflows/*.yml` |
| `shellcheck`  | Standalone shell scripts (e.g. anything under [scripts/](scripts/)) | `shellcheck scripts/*`                       |
| `yamllint`    | Generic YAML structure / formatting              | `yamllint .github/workflows/`                      |
| `markdownlint` | Markdown (CONTRIBUTING.md, README.md, AGENTS.md, etc.) | Use the VS Code "markdownlint" extension; CLI: `npx markdownlint-cli2 '**/*.md'` |
| `ruff`        | Python lint + format (CI-required)               | `scripts/fix` (auto-fix) / `scripts/lint` (verify) |
| `mypy --strict` | Python type checking (CI-required)             | `scripts/lint`                                     |

Installation lives in [.devcontainer.json](.devcontainer.json) (apt-packages: `shellcheck`, `yamllint`) and [scripts/setup](scripts/setup) (`actionlint` pinned with per-arch SHA256 verification, mirroring the go2rtc / HACS install pattern). The matching VS Code extensions (`arahata.linter-actionlint`, `timonwong.shellcheck`, `davidanson.vscode-markdownlint`) are recommended in [homeassistant-purpleair.code-workspace](homeassistant-purpleair.code-workspace), so opening a file gets inline diagnostics.

## Tooling pointers

- **Issue tracker / PRs**: prefer `gh` CLI — `gh pr view`, `gh pr list`, `gh api repos/.../pulls/N/comments`. Pre-authenticated via the `~/.config/gh` bind mount (see [README.md](README.md#devcontainer-host-prerequisites)).
- **HA core API reference**: when adding/modifying entity behaviour, check upstream conventions in `home-assistant/core` (e.g., entity registry semantics changed in 2026.4 — that's why `minimum` is pinned there).
- **Upstream PR for shared work**: [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) tracks the upstream version of this integration; mirror functional changes there when relevant.
