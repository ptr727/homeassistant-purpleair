# Agent guide

Notes for AI coding agents working in this repo. Keep responses concise; prefer editing existing files over creating new ones; never narrate internal deliberation.

## What this is

A HACS-installable Home Assistant **custom integration** for PurpleAir air-quality sensors. Code lives in [custom_components/purpleair/](custom_components/purpleair/). Python 3.14 only, `mypy --strict`, ruff, [platinum quality scale][qs].

## Branches and merging

- Pipeline is `feature → develop → main`. Both `develop` and `main` are protected; everything lands via PR.
- **Feature → develop PRs squash-merge** (single commit on develop, PR title becomes the commit message; never rebase-merge).
- **Develop → main PRs merge-commit** (one merge commit on main per release, develop's tip becomes a second parent and stays in main's ancestry — see [Develop → Main Promotion](#develop--main-promotion) below for why).
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

- [.github/ha-test-versions.json](.github/ha-test-versions.json) drives the pytest matrix in [test-release-task.yml](.github/workflows/test-release-task.yml). Three slots:
  - `minimum` — hand-maintained. Backward-compat floor; must match `hacs.json`'s `homeassistant` field and the pin in `requirements.txt`.
  - `latest-stable` — bot-maintained. Highest pytest-hacc whose `homeassistant==` pin is a stable HA release.
  - `latest-beta` — bot-maintained. Highest pytest-hacc whose pin is a pre-release HA strictly newer than `latest-stable.ha`. `null` when no such beta exists on PyPI (typical right after a stable lands).
- **All three slots gate equally.** No `continue-on-error`, no `gating: false` field. A regression against any one — backward, current, or upcoming-beta — fails the PR. The integration is meant to keep up with HA betas; failures are real signal, not noise.
- The bot ([check-ha-version.yml](.github/workflows/check-ha-version.yml)) runs **daily at 06:00 UTC**. It walks pytest-hacc on PyPI newest-first to resolve both stable and beta candidates, then opens up to two PRs on **rolling** branches `ha-version-bump/stable` and `ha-version-bump/beta` — single PR per stream, force-pushed in place when a newer pin appears. Don't switch back to per-version branch names; the rolling form keeps a failing bump PR refreshed instead of accumulating one stale red PR per beta.
- Bumping the **minimum** is intentional and rare — do it in a regular PR that also updates `hacs.json` `homeassistant`, the `requirements.txt` pin, and any code that needs the new HA API. Consider raising the base `major.minor` in [version.json](version.json) at the same time, since it's a breaking change for users on older HA versions.
- **Don't** add `homeassistant` to Dependabot updates (it's explicitly ignored in [dependabot.yml](.github/dependabot.yml)) — `check-ha-version.yml` owns it.

## Release flow

[publish-release.yml](.github/workflows/publish-release.yml) drives both prereleases and stable releases off the same [build-release-task.yml](.github/workflows/build-release-task.yml). It triggers two ways:

- **Push to `develop`** — automatic prerelease, **but only when tests pass**. Merging any PR into `develop` (feature, bug fix, dependabot, HA-matrix bump) runs `test-release` (the same suite that gates PR merges); `create-release` requires `test-release.result == 'success'` exactly — never `'skipped'`/`'failure'`/`'cancelled'`. On green, [get-version-task.yml](.github/workflows/get-version-task.yml) computes an NBGV version like `0.1.5-g1a2b3c4`, stamps it into `manifest.json`, builds `purpleair.zip`, and creates a prerelease GitHub Release with auto-generated notes. A broken develop push must NOT ship a prerelease.
- **`workflow_dispatch` on `main`** — manual stable release. After merging `develop → main`, a maintainer runs `gh workflow run publish-release.yml --ref main`. The `gate` job rejects dispatches from any other ref. The same `test-release` suite runs first; `create-release` only proceeds on success. NBGV computes a clean version like `0.1.6` (no `-g{sha}` because `main` matches `publicReleaseRefSpec`), and the same build-release path produces a non-prerelease GitHub Release.

**Pushes to `main` are silent.** [publish-release.yml](.github/workflows/publish-release.yml) has no `push: [main]` trigger — Dependabot security PRs and `develop → main` promotions land without cutting a release. This is deliberate: HACS auto-pulls new GitHub Releases, so an automatic main release would force-update every user. Maintainers want main to *be ready* to cut a release on demand, not to ship one on every merge.

Bot-merged PRs (Dependabot, HA-version-bump) trigger the develop prerelease automatically — that's why [merge-bot-pull-request.yml](.github/workflows/merge-bot-pull-request.yml) authors its squash-merges with the App token (`GITHUB_TOKEN`-authored pushes are blocked from triggering downstream workflows by GitHub's recursion guard).

## Develop → Main Promotion

Use the **"Create a merge commit"** option on develop → main PRs. Repo rulesets are split: PRs into `develop` are squash-only (linear history); PRs into `main` are merge-commit only. Clicking "Create a merge commit" on a develop → main PR produces a merge commit on main whose second parent is develop's tip — so develop becomes a real ancestor of main, and the *next* develop → main PR has a clean merge base (no recurring conflicts, no behind-base churn).

This was a recurring pain point under the previous squash-only setup: each develop → main squash dropped develop's ancestry and required a per-cycle admin-bypass merge commit on develop to resync. With merge-commit on main, that resync is unnecessary — main's history shows one merge commit per release (a feature, not a defect: each promotion is visible as a single auditable node), and develop stays linear.

## PR review etiquette

This repo uses a review loop: local coding agent iteration + remote automated review. Treat this as a contract, regardless of which local agent authored the changes.

### Expected review loop

1. Push changes to the PR branch.
1. Request automated review.
1. Verify review activity against the **current PR head SHA** (not an older commit).
1. Triage findings.
1. Apply fixes or provide a rationale for decline.
1. Reply to comments/threads and resolve what was addressed.
1. Re-run the loop after every fix push until no actionable findings remain.

Do not assume auto-trigger happened. If no review appears, use the provider-specific runbook to request it explicitly and verify completion. Provider mechanics are intentionally kept out of this file; use [Copilot instructions](.github/copilot-instructions.md) for GitHub Copilot specifics.

`mergeStateStatus: CLEAN` only checks required statuses and may not block on bot review comments. Merge only after review on the latest head SHA is confirmed and actionable findings are closed.

### Triaging review comments

For each comment, classify before responding:

- **Bug** — wrong behavior, missing test coverage, or a real divergence between code and docs. Fix it. Reply with the fixing commit SHA when you're done.
- **Style/convention** — the comment cites AGENTS.md or a repo convention. Two cases:
  - The cited rule matches what the existing codebase already does → fix the offending code.
  - The cited rule contradicts what's already in the tree, or industry norm → **update AGENTS.md instead of the code**. The rule is wrong, not the code. Bouncing the same code across rounds is the symptom of a wrong rule. As a heuristic, three rounds on the same style category means the rule needs adjusting and the user needs to authorize it.
- **Architectural opinion** — the comment proposes a different design ("constrain this to disabled-by-default", "move this elsewhere", "add a runtime guardrail"). This is judgement, not a bug. Surface it to the user with a recommendation; don't apply unilaterally.

### Responding and resolution expectations

Reply inline with either the fixing commit SHA (for accepted issues) or a concise rationale (for declines). Resolve review threads only when addressed or intentionally declined with rationale. Issue-level comments have no resolution action — acknowledge with a reply if needed and move on.

After the final push on a PR, sweep old threads from earlier rounds whose code paths no longer exist; otherwise stale unresolved markers remain in the review UI.

### Escalating to the user

Bring the user in when:

- **Genuine design trade-off** surfaces (fail-open vs fail-closed, narrow vs broad refactor scope, "should we add a guardrail or trust the docstring"). Triage, recommend, ask.
- **Repeated friction** across rounds without convergence — that's the AGENTS.md-needs-updating signal. Stop, summarize the pattern, and let the user authorize the rule change.
- **Architectural redesign** is requested rather than a strict bug fix. Surface with a recommendation; never apply unilaterally.

Anti-pattern: don't keep flipping the code on the same style point. Flip the rule once and stick to the rule.

## Code style

- Run `scripts/fix` to auto-fix (ruff format + ruff check --fix); `scripts/lint` to verify (matches CI: ruff format --check + ruff check + mypy --strict + pyright).
- **Always run `scripts/lint` before pushing or opening a PR** — running ruff in isolation does NOT cover `mypy --strict` or `pyright`, both of which are CI gates. Skipping them locally means catching trivial type errors only after a CI round-trip (e.g. an inline `lambda` without annotations passed into a typed `dict.get(default=…)` will fail mypy strict but pass ruff; a `Final[str] = "x"` constant used as a TypedDict key will pass mypy but fail pyright). One command, no exceptions.
- **Pyright config** lives in [pyrightconfig.json](pyrightconfig.json): basic mode + `reportUnnecessaryComparison` and `reportIncompatibleVariableOverride` escalated to errors. Pyright is the engine behind VS Code's Pylance, so running it from CI keeps the in-editor and CI signals aligned. When pyright complains about HA framework typing warts (e.g. `DataUpdateCoordinator.data` typed as the generic `_DataT` but `None` until first refresh; `Entity.*` declared as `cached_property` while `CoordinatorEntity` re-declares them as plain `@property`), prefer a narrow `# pyright: ignore[<rule>]` with a why-comment over disabling the rule. For high-volume false positives in a single test file, a per-file `# pyright: <rule>=false` directive at the top with a rationale comment is acceptable — see [tests/components/purpleair/test_config_flow.py](tests/components/purpleair/test_config_flow.py).
- Tests: `pytest -ra` after `pip install -r requirements-test.txt`.
- **Inline `#` comments**: keep tight and local. One line is preferred, but multi-line is allowed when needed to document non-obvious implementation constraints, local trade-offs, or coupling that future edits could easily break. Keep this rationale next to the affected block so reviewers and maintainers see it at edit-time. Don't explain *what* the code does; well-named identifiers handle that. Don't reference the current task ("added for X", "used by Y"); that belongs in PR descriptions.
- **Docstrings (`"""..."""`)**: follow PEP 257 and focus primarily on behavior contracts (what callers/tests can rely on), public semantics, and edge-case expectations. A short one-liner is fine for trivial functions and tests with self-documenting names. For non-trivial behavior — non-obvious test scenarios, contracts a test pins, edge cases callers must know about, design trade-offs that are load-bearing for future maintainers — write a one-line summary, blank line, then a details paragraph. Multi-paragraph docstrings are fine when the behavior contract earns it (see [`PurpleAirSensorEntityDescription.hardware_gate`](custom_components/purpleair/sensor.py)). Use inline comments for implementation-local rationale; don't force local mechanics into docstrings when locality is clearer. Design notes belong **in the code**: docstrings or inline comments live next to the code they describe and stay in sync with it. They do NOT belong in [HISTORY.md](HISTORY.md) — that file is end-user release notes (what changed, what to expect after upgrade), not a design log.
- **Don't add backward-compat shims, `# removed` markers, or rename-to-`_` for unused vars** — just delete.
- **Don't add error handling for impossible cases** — trust internal code; only validate at boundaries.
- **Constants for repeated dict keys.** When the same string literal appears as a dict key in more than one place (e.g. `flow["handler"]`, `result["type"]`, `flow["context"]`), promote it to a named constant — Copilot will flag duplicates otherwise. Reuse HA's canonical constants where they exist (`SOURCE_REAUTH` from `homeassistant.config_entries`, etc.); otherwise add to the local const module. Production constants live in [custom_components/purpleair/const.py](custom_components/purpleair/const.py); test-only constants in [tests/components/purpleair/const.py](tests/components/purpleair/const.py).
- **`Final` annotation form.** Always declare module-level constants with `Final` — never plain assignment. Two valid shapes:
  - `FOO: Final[<type>] = <value>` — when the type is **broader** than the value, e.g. `API_KEY: Final[str] = "abcde12345"`, `INDEX: Final[int] = 5`, `THRESHOLD: Final[timedelta] = timedelta(...)`. This is the form to use for production constants and test fixtures with concrete types broader than their values.
  - `FOO: Final = "<value>"` — bare, **only** when the constant is used as a TypedDict key and pyright's structural match needs the literal narrow preserved (e.g. `context={CONF_SOURCE: CONF_SOURCE_USER}` against HA's `ConfigFlowContext`). `Final[str]` widens to plain `str` and breaks that match. Document the bare-form choice with a block comment so future cleanup doesn't "fix" it back to `Final[str]`.
  - **Never** `FOO: Final[Literal["x"]] = "x"` — ruff PYI064 flags this as redundant; bare `Final` is the correct idiom.
- **Codebase-wide consistency over local micro-improvements.** Before adopting a reviewer-suggested pattern change in one file, sweep the codebase for the same construct. If an established convention already exists at multiple sites, match it; only adopt the new form if you migrate every site in the same PR. Same rule applies to your own refactors — don't leave one file's pattern diverging from its siblings. A "better" idiom in one spot that creates a third style alongside two existing ones is worse than the local imperfection.

### Linter cleanliness — fix what you see in the IDE

**Before committing, the VS Code Problems pane should be quiet for the files you touched.** That means:

- **CI-gated**: `ruff format`, `ruff check`, `mypy --strict`, `pyright` (basic mode + extra rules; see [pyrightconfig.json](pyrightconfig.json)), hassfest TRANSLATIONS/REQUIREMENTS validation. Run `scripts/lint`.
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

[.devcontainer.json](.devcontainer.json) bind-mounts the host SSH signing key's *public half* (`~/.ssh/id_ed25519.pub`), `~/.config/git/allowed_signers`, and `~/.config/gh` so commits inside the container are SSH-signed (signing happens via the forwarded `ssh-agent` socket — the private key never enters the container) and, *when the host's `gh` token is file-backed*, `gh` is pre-authenticated. `gh auth login` uses a credential store by default when one is available — Keychain on macOS, libsecret/Secret Service on Linux desktops — and `--insecure-storage` is the opt-out that forces file storage. On credential-store hosts, `~/.config/gh/hosts.yml` carries no `oauth_token`, so container `gh` is unauthenticated until you opt into one of the trade-offs documented in [README.md](README.md#devcontainer-setup).

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

- **Issue tracker / PRs**: prefer `gh` CLI — `gh pr view`, `gh pr list`, `gh api repos/.../pulls/N/comments`. Pre-authenticated via the `~/.config/gh` bind mount when the host's `gh` token is file-backed; on credential-store hosts (macOS Keychain, Linux libsecret) the contributor chose either to authenticate `gh` once inside the container or to skip container `gh` entirely — see [README.md](README.md#devcontainer-setup) for which.
- **HA core API reference**: when adding/modifying entity behavior, check upstream conventions in `home-assistant/core` (e.g., entity registry semantics changed in 2026.4 — that's why `minimum` is pinned there).
- **Upstream PR for shared work**: [home-assistant/core#140901][ha-core-pr-link] tracks the upstream version of this integration; mirror functional changes there when relevant.

[workspace-link]: homeassistant-purpleair.code-workspace
[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale
[ha-core-pr-link]: https://github.com/home-assistant/core/pull/140901
