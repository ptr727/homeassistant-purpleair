# Agent guide

Notes for AI coding agents working in this repo. Keep responses concise; prefer editing existing files over creating new ones; never narrate internal deliberation.

## What this is

A HACS-installable Home Assistant **custom integration** for PurpleAir air-quality sensors. Code lives in [custom_components/purpleair/](custom_components/purpleair/). Python 3.14 only, `mypy --strict`, ruff, [platinum quality scale][qs].

## Branches and merging

- Pipeline is `feature → develop → main`. Both `develop` and `main` are protected; everything lands via PR.
- **Feature → develop PRs squash-merge** (single commit on develop, PR title becomes the commit message; never rebase-merge).
- **Develop → main PRs merge-commit** (one merge commit on main per release, develop's tip becomes a second parent and stays in main's ancestry — see [Develop → Main Promotion](#develop--main-promotion) below for why).
- Open feature PRs against `develop`. `develop → main` is how stable releases are cut.

## Git and Commit Rules

- **Default to staging, not committing.** Stage changes with `git add` and leave `git commit` to the developer unless the developer has explicitly authorized the agent to commit for the current ask ("commit this", "open a PR", etc.). Authorization is scope-bound - it covers the commits needed for that specific task, not a blanket commit license for the rest of the session.
- **All commits must be cryptographically signed (SSH or GPG).** Branch protection enforces this on both branches; unsigned commits are rejected on push. Signing depends on environment configuration - `git config commit.gpgsign true`, a configured `user.signingkey`, and a working signing agent (loaded `ssh-agent` for SSH, or `gpg-agent` for GPG). If signing is not configured in the environment, **do not commit** - surface the missing config to the developer and stop at `git add`. Verify before any agent-authored commit (`git config --get commit.gpgsign && ssh-add -L` or the GPG equivalent). **Signing must be live before the *first* commit, not retrofitted.** Turning on `Require signed commits` against a branch that already has unsigned commits forces a rewrite of that entire history to re-sign it - changing every commit SHA and making whoever does the rewrite the committer and signer of every commit (a rebase preserves the `author` field but not the original signatures; you cannot sign another contributor's commits for them). During new-repo setup, never create commits until signing is verified.
- **Never force push.** Do not run `git push --force` or `git push --force-with-lease` under any circumstances. Force pushing rewrites shared history and can cause data loss.
- **Never run destructive git commands** (`git reset --hard`, `git checkout .`, `git restore .`, `git clean -f`) without explicit developer instruction.

## Pull Request Title and Commit Message Conventions

### Format

- Imperative subject summarizing the change, <=72 characters, no trailing period. ("Add 24-hour PM2.5 average sensor", not "Added X" or "Adds X".)
- Optional body, blank-line separated, explaining *why* the change is being made when that's non-obvious. The diff shows *what*.

### Rules

- Don't write `update stuff`, `wip`, or other vague titles. (Dependabot's default `Bump X from Y to Z` titles are fine - keep them.)
- Don't add `Co-Authored-By:` lines unless the developer explicitly asks.
- Don't put release-bump magnitude in the title - no "minor", "patch", "release v0.2.0", etc. Nerdbank.GitVersioning computes the next release version from `version.json` + git history. Dependency versions in dependency-bump titles are fine and expected.
- Use US English spelling and match the existing heading style of the file you're editing: title case with lowercase short bind words (a, an, the, and, but, or, of, in, on, at, to, by, for, from); hyphenated compounds capitalize both parts unless the second is a short preposition (*Built-in*, *EPA-Corrected*, *24-Hour*).

### Examples

```text
Surface 24-hour PM2.5 average as a separate sensor
Skip empty PurpleAir API responses during polling
Drop support for Home Assistant < 2026.4
Bump aiopurpleair from 2025.08.1 to 2025.09.0
Clarify HACS install steps in README
```

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
  - `minimum` — hand-maintained. Backward-compat floor; must match `hacs.json`'s `homeassistant` field (the user-facing minimum). `requirements.txt`'s `homeassistant==X` pin is a dev/CI bootstrap install and may pin a *higher* patch in the same series as a convenience; the matrix's pytest job overrides it with `pip install --upgrade homeassistant==<minimum>` so the actual gate is enforced regardless of the bootstrap version.
  - `latest-stable` — bot-maintained. Highest pytest-hacc whose `homeassistant==` pin is a stable HA release.
  - `latest-beta` — bot-maintained. Highest pytest-hacc whose pin is a pre-release HA strictly newer than `latest-stable.ha`. `null` when no such beta exists on PyPI (typical right after a stable lands).
- **All three slots gate equally.** No `continue-on-error`, no `gating: false` field. A regression against any one — backward, current, or upcoming-beta — fails the PR. The integration is meant to keep up with HA betas; failures are real signal, not noise.
- The bot ([check-ha-version.yml](.github/workflows/check-ha-version.yml)) runs **daily at 06:00 UTC**. It walks pytest-hacc on PyPI in PEP-440 descending order (highest version first, capped at 10 versions; not upload-time ordering) to resolve both stable and beta candidates, then opens **one bundled PR** on the rolling branch `ha-version-bump/matrix` covering whichever slots changed — at most one bot PR open at a time. Bundling is intentional: an earlier two-PR design had a race where a beta-clear PR could auto-merge before the corresponding stable bump, leaving develop with stale stable + null beta until the second PR landed. Don't split this back into per-slot branches.
- Bumping the **minimum** is intentional and rare — do it in a regular PR that also updates `hacs.json` `homeassistant` (must match), the `requirements.txt` bootstrap pin (typically to the same series; a higher patch within that series is fine), and any code that needs the new HA API. Consider raising the base `major.minor` in [version.json](version.json) at the same time, since it's a breaking change for users on older HA versions.
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

## PR Review Etiquette

> **Mandatory in every derived repo.** This entire "PR Review Etiquette" section is the provider-agnostic review-loop *contract* and must be carried **verbatim** into every repo derived from this template, alongside the [`.github/copilot-instructions.md`](./.github/copilot-instructions.md) "GitHub Copilot Review Runbook" that implements it. Without both in-repo, an agent working in the derived repo has no pointer to the reliable Copilot mechanics and falls back to ad-hoc (and known-broken) behavior.

The repo runs a review loop on every PR: local agent iteration plus remote automated review (GitHub Copilot is the configured reviewer). Treat this as a contract regardless of which local agent authored the changes.

### Merge Gate (read this first)

**Do not merge - and do not enable auto-merge - unless ALL of these hold:**

1. Required status checks are green (`mergeStateStatus: CLEAN`), **and**
2. A Copilot review is confirmed on the **current head SHA** (not an earlier push), **and**
3. **Every** Copilot finding on that head SHA is closed out - all review threads resolved, **and** any issue-level Copilot comments (which have no resolve action) triaged and replied to - so zero outstanding findings remain, **and**
4. The maintainer has given **explicit** permission to merge.

`mergeStateStatus: CLEAN` reflects **only** required statuses - it never reflects open bot review comments, so `CLEAN` alone is **never** sufficient to merge. A green/`CLEAN` PR with an unresolved Copilot finding fails this gate; treat it as "not mergeable" no matter what the merge-state field says. The agent never merges on its own (consistent with "default to staging"; merging is maintainer-authorized).

**Merging is not releasing.** A merge to a release branch does **not** by itself publish; publishing is a separate step in the repo's release pipeline (a scheduled run or a manual dispatch), not an automatic consequence of merging. Never describe a merge as cutting a release, and never trigger a publish without explicit maintainer instruction.

### Expected Review Loop

1. Push changes to the PR branch.
2. Re-request a review for the **current head SHA**. Auto-trigger is unreliable, so request it explicitly via the `requestReviews` GraphQL mutation (now reliable end-to-end - see the runbook); the UI is only a fallback.
3. Wait for review activity on that head. A completed review that raises **no findings** is a valid terminal outcome for that head - proceed; do not re-trigger it or treat the absence of comments as a missing review.
4. Triage findings.
5. Apply fixes or write a rationale for declines.
6. Reply to each thread and resolve what was addressed.
7. Re-run the loop after every fix push until no actionable findings remain.

Drive the loop to green - review confirmed on the latest head SHA and every actionable finding closed - then stop and apply the **Merge Gate** above: all four preconditions must hold, and `mergeStateStatus: CLEAN` alone never satisfies it.

For provider-specific mechanics (how to request review, query review state, post replies, resolve threads), see the **GitHub Copilot Review Runbook** in [.github/copilot-instructions.md](./.github/copilot-instructions.md). This file owns the contract; that file owns the mechanics.

### Triaging Review Comments

For each comment, classify before responding:

- **Bug** - wrong behavior, missing test coverage, or a real divergence between code and docs. Fix it. Reply with the fixing commit SHA when done.
- **Style/convention** - the comment cites a rule from this file or a language-specific style guide. Two cases:
  - The cited rule matches what the existing codebase already does -> fix the offending code.
  - The cited rule contradicts what's in the tree, or industry norm -> **update the rule instead of the code**. The rule is wrong, not the code. Bouncing the same code across rounds is the symptom of a wrong rule. Heuristic: three rounds on the same style category means the rule needs adjusting and the user should authorize the rule change.
- **Architectural opinion** - the comment proposes a different design ("constrain this to disabled-by-default", "move it elsewhere", "add a runtime guardrail"). This is judgment, not a bug. Surface it to the user with a recommendation; don't apply unilaterally.

### Responding and Resolution Expectations

Reply inline with either the fixing commit SHA (for accepted issues) or a concise rationale (for declines). Resolve review threads when addressed or intentionally declined with rationale. Issue-level comments (those at `repos/.../issues/<N>/comments` rather than tied to a specific line) have no resolution action - acknowledge with a reply if needed and move on.

After the final push on a PR, sweep older threads from earlier rounds whose code paths no longer exist; otherwise stale unresolved markers remain in the review UI.

### Escalating to the User

Bring the user in when:

- **Genuine design trade-off** surfaces (fail-open vs fail-closed, narrow vs broad refactor scope, "should we add a guardrail or trust the docstring"). Triage, recommend, ask.
- **Repeated friction** across rounds without convergence - that's the rule-needs-updating signal. Stop, summarize the pattern, and let the user authorize the rule change.
- **Architectural redesign** is requested rather than a bug fix. Surface with a recommendation; never apply unilaterally.

Anti-pattern: don't keep flipping the code on the same style point. Flip the rule once and stick to the rule.

## Reviewing CI / Release-Train Changes

When reviewing a PR that touches [.github/workflows/](.github/workflows/) or [.github/ha-test-versions.json](.github/ha-test-versions.json), check the change against these load-bearing invariants. Each one is intentional and was reached after a real failure mode; flag any drift.

- **All test matrix slots gate equally.** [.github/ha-test-versions.json](.github/ha-test-versions.json) has three slots - `minimum` (backward compat), `latest-stable`, `latest-beta` - consumed by [test-release-task.yml](.github/workflows/test-release-task.yml). None of them carries `continue-on-error` or a `gating: false` field. Reject PRs that add either; reject schema changes that drop or rename a slot. The `latest-beta` slot can legitimately be `null` (when no HA pre-release is newer than `latest-stable`), but never `continue-on-error`.
- **Develop publishes prereleases only on green.** [publish-release.yml](.github/workflows/publish-release.yml)'s `create-release` requires `needs.test-release.result == 'success'` exactly - not `'skipped'`/`'failure'`/`'cancelled'`. Reject PRs that loosen this back to `!= 'failure'` or re-allow the `'skipped'` path on develop pushes.
- **Main never auto-publishes.** [publish-release.yml](.github/workflows/publish-release.yml) has no `push: [main]` trigger, only `workflow_dispatch` from main. Reject any PR that adds a `push: [main]` (or `push: [main, develop]`) trigger to publish-release. HACS auto-pulls new releases, so auto-publishing on main would force-update every user.
- **HA-version-bump bot uses one rolling branch and runs daily.** [check-ha-version.yml](.github/workflows/check-ha-version.yml) opens a single bundled PR on `ha-version-bump/matrix` (no version embedded, both slots in one PR) and runs on `cron: "0 6 * * *"`. Reject PRs that split this back into per-slot branches - that re-introduces a real race where a beta-clear PR could auto-merge before the corresponding stable bump. Reject PRs that switch to per-version branch names (accumulates stale red PRs) or drop the cron back to weekly.
- **Beta failures do not silently merge.** With merge-bot configured to `gh pr merge --auto`, a failing test-release on a bot PR keeps the PR open, and develop's pin lags upstream until a human ports the integration. That's the intended outcome - don't suggest "just skip the beta slot for now" or "make it advisory."

If a reviewer argues for relaxing any of these, escalate to the maintainer rather than implementing - these are explicit user decisions, not lint rules.

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
- **IDE-driven**: `pylint` (configured via `[tool.pylint."MESSAGES CONTROL"]` in [pyproject.toml](pyproject.toml)), `markdownlint` (configured via [.markdownlint-cli2.jsonc](.markdownlint-cli2.jsonc), used by the `davidanson.vscode-markdownlint` extension), `actionlint`, `shellcheck`.

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

The devcontainer ships these CLIs out of the box. Use them locally before pushing — CI runs `ruff` + `mypy --strict` + `pytest`, but actionlint/shellcheck/markdownlint are not yet wired into CI, so local runs are the only gate.

| Tool                | What it lints                                                                          | Quick command                             |
| ------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------- |
| `actionlint`        | GitHub Actions workflow YAML (also runs shellcheck on `run:` blocks)                   | `actionlint .github/workflows/*.yml`      |
| `shellcheck`        | Standalone shell scripts (e.g. anything under [scripts/](scripts/))                    | `shellcheck scripts/*`                    |
| `markdownlint-cli2` | Markdown (`CONTRIBUTING.md`, `README.md`, `AGENTS.md`, etc.) — same engine as VS Code  | `markdownlint-cli2 '**/*.md'`             |
| `pylint`            | Python (IDE-driven; not CI-gated)                                                      | `pylint custom_components/ tests/`        |
| `ruff`              | Python lint + format (CI-required)                                                     | `scripts/fix` (auto-fix) / `scripts/lint` |
| `mypy --strict`     | Python type checking (CI-required)                                                     | `scripts/lint`                            |

Installation:

- `shellcheck`, `ffmpeg`, `libturbojpeg0`, `libpcap-dev` — `apt-packages` feature in [.devcontainer.json](.devcontainer.json).
- Node.js LTS — `node:2` feature in [.devcontainer.json](.devcontainer.json), needed for `markdownlint-cli2`.
- `markdownlint-cli2` — pinned `npm install -g` step in [scripts/setup](scripts/setup) (mirrors how `actionlint` and HACS are installed). Pin lives in `MARKDOWNLINT_VERSION` at the top of that block.
- `actionlint` — SHA256-pinned tarball download in [scripts/setup](scripts/setup).
- `pylint` is configured via `[tool.pylint."MESSAGES CONTROL"]` in [pyproject.toml](pyproject.toml); the disable list is annotated with why each rule is silenced.
- The matching VS Code extensions (`arahata.linter-actionlint`, `timonwong.shellcheck`, `davidanson.vscode-markdownlint`, `ms-python.python`) are recommended in [the workspace file][workspace-link], so opening a file gets inline diagnostics.

## Tooling pointers

- **Issue tracker / PRs**: prefer `gh` CLI — `gh pr view`, `gh pr list`, `gh api repos/.../pulls/N/comments`. Pre-authenticated via the `~/.config/gh` bind mount when the host's `gh` token is file-backed; on credential-store hosts (macOS Keychain, Linux libsecret) the contributor chose either to authenticate `gh` once inside the container or to skip container `gh` entirely — see [README.md](README.md#devcontainer-setup) for which.
- **HA core API reference**: when adding/modifying entity behavior, check upstream conventions in `home-assistant/core` (e.g., entity registry semantics changed in 2026.4 — that's why `minimum` is pinned there).
- **Upstream PR for shared work**: [home-assistant/core#140901][ha-core-pr-link] tracks the upstream version of this integration; mirror functional changes there when relevant.

## Template Adaptations

This repo is derived from [ptr727/ProjectTemplate](https://github.com/ptr727/ProjectTemplate) and carries its shared artifacts verbatim (the [PR Review Etiquette](#pr-review-etiquette), [Git and Commit Rules](#git-and-commit-rules), and [Pull Request Title and Commit Message Conventions](#pull-request-title-and-commit-message-conventions) sections; `.github/copilot-instructions.md`; `.markdownlint-cli2.jsonc`; `.editorconfig`; `.gitattributes`; `CODESTYLE.md`; and the orchestration-layer merge-bot workflow). The deviations below are intentional and repo-specific.

- **HACS zip-deploy publish model (shared model for future HACS repos).** This is a HACS-distributed Home Assistant integration, not a .NET/PyPI/Docker library, so the release path is bespoke and is the **reference model future HACS-derived repos follow** rather than the template's generic publisher:
  - [publish-release.yml](.github/workflows/publish-release.yml) keeps a `push: [develop]` trigger for automatic prereleases (HACS beta testers consume develop's GitHub prereleases directly) plus a `workflow_dispatch` from `main` for stable releases. There is no weekly schedule and no `PUBLISH_ON_MERGE` variable - the develop-push prerelease *is* the continuous-release model this repo wants. `main` deliberately never auto-publishes (HACS auto-pulls every release, so a main auto-release would force-update every user). The `concurrency` group is global and ref-independent with `cancel-in-progress: false`, matching the template's publish-serialization rule: queue, never cancel a half-pushed release.
  - [get-version-task.yml](.github/workflows/get-version-task.yml) has **no `ref` input and no branch matrix** - it versions the caller's checkout directly. The publisher builds one branch per trigger (develop on push, main on dispatch), never both branches in one matrix run, so the template's `ref`-threading is unnecessary here. It exposes `SemVer2`/`Tag`/`Prerelease` outputs tailored to the manifest-stamping flow.
  - The release artifact is a single HACS `purpleair.zip` whose `manifest.json` `version` is stamped with the NBGV-computed version at build time ([build-release-task.yml](.github/workflows/build-release-task.yml)). The committed `manifest.json` `version` stays a `0.0.0` placeholder. This **version-injection-into-a-zip** shape is the HACS model; it does not use the template's generic `release-asset-<branch>-<target>` glob handoff because the HACS consumer reads the integration version from the stamped manifest inside the zip, not from a release asset name. Future HACS repos reuse this zip-deploy + manifest-injection pattern.
- **Build-layer workflows are repo-owned.** [build-release-task.yml](.github/workflows/build-release-task.yml), [test-release-task.yml](.github/workflows/test-release-task.yml), [test-pull-request.yml](.github/workflows/test-pull-request.yml), [build-datebadge-task.yml](.github/workflows/build-datebadge-task.yml), and [check-ha-version.yml](.github/workflows/check-ha-version.yml) implement the HA-specific build, test matrix, and version-bump bot. They are not carried from the template's build layer; their invariants are documented under [HA test matrix](#ha-test-matrix--do-not-touch-manually) and [Reviewing CI / Release-Train Changes](#reviewing-ci--release-train-changes).
- **`merge-ha-version-bump` is this repo's upstream-version equivalent.** The template's merge-bot ships `merge-upstream-version` for repos that track an upstream release via `check-upstream-version-task.yml`. This repo instead tracks HA versions via [check-ha-version.yml](.github/workflows/check-ha-version.yml), which opens its bundled bump PR on the rolling `ha-version-bump/matrix` branch; the merge-bot's `merge-ha-version-bump` job auto-merges that PR. It follows the same opened/reopened-only, base-ref-matched merge model as the template's bot jobs.

[workspace-link]: homeassistant-purpleair.code-workspace
[qs]: https://developers.home-assistant.io/docs/core/integration-quality-scale
[ha-core-pr-link]: https://github.com/home-assistant/core/pull/140901
