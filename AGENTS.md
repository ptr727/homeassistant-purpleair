# Agent guide

Notes for AI coding agents working in this repo. Keep responses concise; prefer editing existing files over creating new ones; never narrate internal deliberation.

## What this is

A HACS-installable Home Assistant **custom integration** for PurpleAir air-quality sensors. Code lives in [custom_components/purpleair/](custom_components/purpleair/). Python 3.14 only, `mypy --strict`, ruff, [platinum quality scale][qs].

## Branches and merging

- Pipeline is `feature → develop → main`. Both `develop` and `main` are protected; everything lands via PR.
- **Feature → develop PRs squash-merge** (single commit on develop, PR title becomes the commit message; never rebase-merge).
- **Develop → main PRs merge-commit** (one merge commit on main per release, develop's tip becomes a second parent and stays in main's ancestry — see [Develop → main promotion](#develop--main-promotion) below for why).
- Open feature PRs against `develop`. `develop → main` is how stable releases are cut.

## Commit messages and PR titles

PR titles are descriptive and have no versioning effect. NBGV computes the version from [version.json](version.json) plus the git commit-height since that base version was last bumped, so commit messages are not parsed and don't need a Conventional-Commits prefix. Write a clear imperative subject — that's it. Bodies are optional; use them when *why* is non-obvious. Don't add `Co-Authored-By:` lines for AI tools unless the user explicitly asks.

## Writing style

Use **US English spelling** in code comments, identifiers, commit messages, PR descriptions, and documentation: *behavior* (not behaviour), *color* (not colour), *favorite* (not favourite), *recognize* (not recognise), *organize* (not organise), *cancel/canceled* (not cancelled), and so on. Existing files predate this rule and may still contain British spellings — fix them when you happen to touch the surrounding lines, but a wholesale sweep isn't required.

**Headings** are title case with lowercase short bind words: a, an, the, and, but, or, of, in, on, at, to, by, for, from. Verbs (including *is/are/was*) and other content words are capitalized. Hyphenated compounds capitalize the second part unless it's a short preposition — *Built-in*, *EPA-Corrected*, *24-Hour*. Keep headings short; long qualifiers belong in the first sentence under the heading rather than in the heading itself.

**Markdown style** uses reference-style links with definitions at the bottom of the file (alphabetized) for shields, external URLs, and any URL referenced more than once — see [README.md](README.md) for the canonical layout. Single-use relative links to local repo files (e.g. `[.markdownlint-cli2.jsonc](.markdownlint-cli2.jsonc)`) are fine inline; that's the established convention in this file and [CONTRIBUTING.md](CONTRIBUTING.md). Write one logical paragraph per line — line-length isn't enforced (MD013 is disabled in `.markdownlint-cli2.jsonc`) and hard-wrapping mid-sentence makes diffs noisier than necessary. Code blocks, tables, and intentional `\` line breaks stay verbatim.

**Cross-reference scoping**: the fact that an upstream Home Assistant core PR exists is intentionally confined to the **Upstream Home Assistant PR** section in [README.md](README.md). Don't introduce or re-introduce mentions of it in other sections (Migration, lead block-quote, etc.) — describe the limitation in terms of what would resolve it ("until the built-in integration adopts schema v2") rather than the current upstream effort. The maintainer may abandon the PR, and scattered references would all need updating.

**Quantitative claims** in [README.md](README.md) (percentages, counts, timings) must be verified against current code or a reproducible measurement before being added or carried forward. When a claim depends on a source-side constant (`STATIC_DEVICE_FIELDS`, `UPDATE_INTERVAL`, the default-enabled entity set, etc.), put a one-line marker in the source comment that the README depends on this value, so a future refactor knows to update both.

## Versioning

The version is derived by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) from [version.json](version.json) and git history — nothing in the working tree carries the actual version number.

- [version.json](version.json) holds the base `major.minor` (currently `0.1`) and the `publicReleaseRefSpec` regex matching `^refs/heads/main$`. NBGV adds the commit height as the patch component, and on non-public refs (anything not matching `publicReleaseRefSpec`) appends a `-g{sha}` prerelease segment. So `main` produces clean SemVer like `0.1.5`; `develop` produces prereleases like `0.1.5-g1a2b3c4`.
- Bump `version.json`'s base `version` field manually only when cutting a new minor or major series (e.g. `0.1` → `0.2`). NBGV handles patch (height) automatically.
- The `version` field in [custom_components/purpleair/manifest.json](custom_components/purpleair/manifest.json) is a `0.0.0` placeholder. Do not edit it. [build-release-task.yml](.github/workflows/build-release-task.yml) overwrites it with the NBGV-computed version on the runner before zipping the released artifact, so the published HACS zip carries the real version while git stays clean.
- [hacs.json](hacs.json) has no `version` field; HACS reads the integration version from the manifest stamped at build time.
- The `homeassistant` field in `hacs.json` is the **minimum** required HA version (hand-maintained alongside the pin in [requirements.txt](requirements.txt) and the `minimum` entry in [.github/ha-test-versions.json](.github/ha-test-versions.json)).

## HA test matrix — DO NOT touch manually

- [.github/ha-test-versions.json](.github/ha-test-versions.json) drives the pytest matrix in [test-release-task.yml](.github/workflows/test-release-task.yml). Two pinned versions: `minimum` (hand-maintained) and `latest` (bot-maintained by [check-ha-version.yml](.github/workflows/check-ha-version.yml), which derives both `ha` and `pytest-hacc` from PyPI's latest `pytest-homeassistant-custom-component` release).
- Bumping the **minimum** is intentional and rare — do it in a regular PR that also updates `hacs.json` `homeassistant`, the `requirements.txt` pin, and any code that needs the new HA API. Consider raising the base `major.minor` in [version.json](version.json) at the same time, since it's a breaking change for users on older HA versions.
- **Don't** add `homeassistant` to Dependabot updates (it's explicitly ignored in [dependabot.yml](.github/dependabot.yml)) — `check-ha-version.yml` owns it.

## Release flow

[publish-release.yml](.github/workflows/publish-release.yml) drives both prereleases and stable releases off the same [build-release-task.yml](.github/workflows/build-release-task.yml). It triggers two ways:

- **Push to `develop`** — automatic prerelease. Merging any PR into `develop` (feature, bug fix, dependabot, HA-matrix bump) runs the workflow, which calls [get-version-task.yml](.github/workflows/get-version-task.yml) for an NBGV-computed version like `0.1.5-g1a2b3c4`, stamps that into `manifest.json`, builds `purpleair.zip`, and creates a prerelease GitHub Release with auto-generated notes. Beta testers always have the latest develop snapshot.
- **`workflow_dispatch` on `main`** — manual stable release. After merging `develop → main`, a maintainer runs `gh workflow run publish-release.yml --ref main`. The `gate` job rejects dispatches from any other ref. NBGV computes a clean version like `0.1.6` (no `-g{sha}` because `main` matches `publicReleaseRefSpec`), and the same build-release path produces a non-prerelease GitHub Release.

Bot-merged PRs (Dependabot, HA-version-bump) trigger the develop prerelease automatically — that's why [merge-bot-pull-request.yml](.github/workflows/merge-bot-pull-request.yml) authors its squash-merges with the App token (`GITHUB_TOKEN`-authored pushes are blocked from triggering downstream workflows by GitHub's recursion guard).

## Develop → main promotion

Use the **"Create a merge commit"** option on develop → main PRs. Repo rulesets are split: PRs into `develop` are squash-only (linear history); PRs into `main` are merge-commit only. Clicking "Create a merge commit" on a develop → main PR produces a merge commit on main whose second parent is develop's tip — so develop becomes a real ancestor of main, and the *next* develop → main PR has a clean merge base (no recurring conflicts, no behind-base churn).

This was a recurring pain point under the previous squash-only setup: each develop → main squash dropped develop's ancestry and required a per-cycle admin-bypass merge commit on develop to resync. With merge-commit on main, that resync is unnecessary — main's history shows one merge commit per release (a feature, not a defect: each promotion is visible as a single auditable node), and develop stays linear.

## PR review etiquette

Branch protection's `copilot_code_review` rule reviews on push, but `mergeStateStatus: CLEAN` only waits on *required* checks; Copilot's `COMMENTED` reviews don't block. Before merging a PR, explicitly verify Copilot has reviewed the *current* head SHA, not an earlier one:

```sh
PR_HEAD=$(gh pr view <N> --json headRefOid --jq '.headRefOid')
gh pr view <N> --json reviews --jq \
  '.reviews[] | select(.author.login=="copilot-pull-request-reviewer") | .commit.oid' \
  | grep -q "$PR_HEAD"
```

When that grep matches, read the comments submitted at-or-after that review's `submittedAt`:

```sh
LATEST=$(gh pr view <N> --json reviews --jq \
  '[.reviews[] | select(.author.login=="copilot-pull-request-reviewer")] | last | .submittedAt')
gh api repos/<owner>/<repo>/pulls/<N>/comments --jq \
  "[.[] | select(.created_at >= \"$LATEST\")]"
```

Zero comments at or after the latest review's timestamp is the explicit sign-off. Any earlier check is a race against an in-progress review and can ship bugs that landed in the last review pass (it has).

## Code style

- Run `scripts/fix` to auto-fix (ruff format + ruff check --fix); `scripts/lint` to verify (matches CI: ruff format --check + ruff check + mypy --strict).
- Tests: `pytest -ra` after `pip install -r requirements-test.txt`.
- **Comments**: only when the *why* is non-obvious — hidden constraint, subtle invariant, workaround. Don't explain *what* the code does. No multi-paragraph docstrings; one-line comment max.
- **Don't add backward-compat shims, `# removed` markers, or rename-to-`_` for unused vars** — just delete.
- **Don't add error handling for impossible cases** — trust internal code; only validate at boundaries.

### Linter cleanliness — fix what you see in the IDE

**Before committing, the VS Code Problems pane should be quiet for the files you touched.** That means:

- **CI-gated**: `ruff format`, `ruff check`, `mypy --strict`, hassfest TRANSLATIONS/REQUIREMENTS validation. Run `scripts/lint`.
- **IDE-driven**: `pylint` (configured via `[tool.pylint."MESSAGES CONTROL"]` in [pyproject.toml](pyproject.toml)), `markdownlint` (configured via [.markdownlint-cli2.jsonc](.markdownlint-cli2.jsonc), used by the `davidanson.vscode-markdownlint` extension), `actionlint`, `shellcheck`, `yamllint`.

**For Python linters**, false positives are common — HA's `dataclass(kw_only=True)` confuses pylint's argument resolution, pytest fixtures look like unused arguments, etc. Prefer to **disable recurring false positives project-wide in the linter's config file** (with a comment explaining why), rather than scattering inline suppressions. Avoid unjustified `# noqa` or `# pylint: disable=...` annotations; if an inline suppression is truly needed, keep it narrow and explain why.

**For markdown**, what counts as a real warning is whatever the davidanson extension shows in the IDE — not what some external CLI tool reports. The repo config disables MD013 (line-length) because long prose lines are intentional here. Other rules stay on; fix the source when one fires.

Verifying locally:

```sh
scripts/lint                                              # CI gate
pylint custom_components/ tests/                          # 10/10 expected
markdownlint-cli2 README.md AGENTS.md HISTORY.md \
    CONTRIBUTING.md                                       # 0 errors expected
actionlint .github/workflows/*.yml                        # silent expected
shellcheck scripts/*                                      # silent expected
yamllint .github/workflows/                               # silent expected
```

## Workflow YAML conventions

- Pin actions to a SHA with a trailing `# vX.Y.Z` comment, e.g. `uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2`. Dependabot bumps these.
- Step names end in `step`, job names end in `job`.
- Top-level workflows have a `concurrency:` block keyed on `${{ github.workflow }}-${{ github.ref }}`.
- Shell scripts start with `set -euo pipefail`.
- After editing any workflow, validate with `actionlint .github/workflows/*.yml` (preinstalled in the devcontainer; see "Linters available in the devcontainer" below).

### Gotchas (each one bit us at least once)

- **Multi-line `if` conditions use `if: >-` (folded scalar), not `if: |` (literal).** The folded form joins lines with single spaces; literal preserves newlines, which the GitHub expression parser handles oddly.
- **Boolean inputs differ between `workflow_call` and `workflow_dispatch`.** `workflow_call` delivers them as actual booleans; `workflow_dispatch` delivers them as the *strings* `"true"`/`"false"`. Any `if:` consuming a boolean input must compare against both forms — `if: ${{ inputs.foo == true || inputs.foo == 'true' }}`. A bare `if: ${{ inputs.foo }}` reads `"false"` as truthy on the dispatch path.
- **Mirror inputs across both triggers** when a workflow supports `workflow_call` *and* `workflow_dispatch`. An input declared only on one side is `null` on the other and the if-condition silently misbehaves.
- **Job-level `permissions:` in a reusable workflow are validated against the caller's permissions before the `if:` condition runs.** A `release` job with `permissions: contents: write` and `if: ${{ inputs.publish }}` will still cause `startup_failure` on a caller that doesn't grant `contents: write`, even though the job would have been skipped. Either declare permissions at the call site, or omit the inner block and inherit.
- **Allowlist `success` and `skipped` explicitly when chaining jobs across optional dependencies** — `!= 'failure'` lets `cancelled` through (timeout, runner failure, manual cancel). Use `(needs.X.result == 'success' || needs.X.result == 'skipped')`.
- **`actions/upload-artifact` accepts duplicate names from sibling reusable-workflow invocations within the same parent run** (we hit this with two `purpleair-zip` uploads). It's undocumented behavior — don't rely on it. Gate the duplicate path with an input flag instead.

## Bot identity and secrets

- App: `ptr727-codegen[bot]`. Repo secrets:
  - `CODEGEN_APP_CLIENT_ID` — the App's Client ID.
  - `CODEGEN_APP_PRIVATE_KEY` — the App's private key (PEM contents).
- The App authors squash-merges in [merge-bot-pull-request.yml](.github/workflows/merge-bot-pull-request.yml) (Dependabot PRs, HA-version-bump PRs) and authors the HA-version-bump PR itself in [check-ha-version.yml](.github/workflows/check-ha-version.yml). It is *not* used by [publish-release.yml](.github/workflows/publish-release.yml) — that path uses the default `GITHUB_TOKEN` because it doesn't need to fire a downstream workflow.
- With no "Require approvals" on `develop`/`main`, bot PRs auto-merge as soon as `check-workflow-status` is green. If approvals get turned on, both `ptr727-codegen[bot]` and `dependabot[bot]` need to be on the bypass list. If a tag ruleset restricts pushing, ensure `github-actions[bot]` is allowed to create release tags (publish-release uses `softprops/action-gh-release` under `GITHUB_TOKEN`, so the tag is created by `github-actions[bot]`).
- Generate tokens with `actions/create-github-app-token` — never hard-code or use a PAT.

## Common tasks

- **Add a feature / fix a bug**: feature branch from `develop` → code + tests → `scripts/fix` → `scripts/lint` → `pytest` → PR against `develop` with a descriptive title.
- **Add a Dependabot config / new ecosystem**: edit [.github/dependabot.yml](.github/dependabot.yml).
- **Cut a stable release**: merge `develop → main`, then `gh workflow run publish-release.yml --ref main`.
- **Don't manually create GitHub releases.** The pipeline owns this end-to-end.

## Devcontainer

[.devcontainer.json](.devcontainer.json) bind-mounts host SSH signing key, `~/.config/git/allowed_signers`, and `~/.config/gh` so commits inside the container are SSH-signed and `gh` is pre-authenticated. See [README.md](README.md#devcontainer-setup).

## Linters available in the devcontainer

The devcontainer ships these CLIs out of the box. Use them locally before pushing — CI runs `ruff` + `mypy --strict` + `pytest`, but actionlint/shellcheck/yamllint/markdownlint are not yet wired into CI, so local runs are the only gate.

| Tool                | What it lints                                                                          | Quick command                             |
| ------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------- |
| `actionlint`        | GitHub Actions workflow YAML (also runs shellcheck on `run:` blocks)                   | `actionlint .github/workflows/*.yml`      |
| `shellcheck`        | Standalone shell scripts (e.g. anything under [scripts/](scripts/))                    | `shellcheck scripts/*`                    |
| `yamllint`          | Generic YAML structure / formatting                                                    | `yamllint .github/workflows/`             |
| `markdownlint-cli2` | Markdown (`CONTRIBUTING.md`, `README.md`, `AGENTS.md`, etc.) — same engine as VS Code  | `markdownlint-cli2 '**/*.md'`             |
| `pylint`            | Python (IDE-driven; not CI-gated)                                                      | `pylint custom_components/ tests/`        |
| `ruff`              | Python lint + format (CI-required)                                                     | `scripts/fix` (auto-fix) / `scripts/lint` |
| `mypy --strict`     | Python type checking (CI-required)                                                     | `scripts/lint`                            |

Installation:

- `shellcheck`, `yamllint`, `ffmpeg`, `libturbojpeg0`, `libpcap-dev` — `apt-packages` feature in [.devcontainer.json](.devcontainer.json).
- Node.js LTS — `node:2` feature in [.devcontainer.json](.devcontainer.json), needed for `markdownlint-cli2`.
- `markdownlint-cli2` — pinned `npm install -g` step in [scripts/setup](scripts/setup) (mirrors how `actionlint` and HACS are installed). Pin lives in `MARKDOWNLINT_VERSION` at the top of that block.
- `actionlint` — SHA256-pinned tarball download in [scripts/setup](scripts/setup).
- `pylint` is configured via `[tool.pylint."MESSAGES CONTROL"]` in [pyproject.toml](pyproject.toml); the disable list is annotated with why each rule is silenced.
- The matching VS Code extensions (`arahata.linter-actionlint`, `timonwong.shellcheck`, `davidanson.vscode-markdownlint`, `ms-python.python`) are recommended in [the workspace file][workspace-link], so opening a file gets inline diagnostics.

## Tooling pointers

- **Issue tracker / PRs**: prefer `gh` CLI — `gh pr view`, `gh pr list`, `gh api repos/.../pulls/N/comments`. Pre-authenticated via the `~/.config/gh` bind mount (see [README.md](README.md#devcontainer-setup)).
- **HA core API reference**: when adding/modifying entity behavior, check upstream conventions in `home-assistant/core` (e.g., entity registry semantics changed in 2026.4 — that's why `minimum` is pinned there).
- **Upstream PR for shared work**: [home-assistant/core#140901][ha-core-pr-link] tracks the upstream version of this integration; mirror functional changes there when relevant.

[workspace-link]: homeassistant-purpleair.code-workspace
[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale
[ha-core-pr-link]: https://github.com/home-assistant/core/pull/140901
