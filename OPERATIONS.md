# Operations

How this repository is run: the checks to run before pushing, the runbooks for the tasks that recur, and the local rule extensions that apply here on top of the carried fleet rules in [`GOVERNANCE.md`](./GOVERNANCE.md).

## Local Verification

Run the full gate set before pushing or opening a pull request. `ruff` alone covers neither `mypy --strict` nor `pyright`, and both are CI gates, so skipping them locally means finding a trivial type error only after a CI round trip.

```sh
scripts/setup                 # once: provision the uv-managed .venv
scripts/fix                   # apply ruff format and ruff check --fix
scripts/lint                  # verify: ruff format --check, ruff check, mypy --strict, pyright
.venv/bin/pytest -ra          # the test suite, from the .venv scripts/setup built
```

`scripts/lint` mirrors the CI `Ruff job`, `Mypy strict-typing job`, and `Pyright job`, and the `pytest` job runs the suite once per slot in the HA test matrix. A local run exercises only the Home Assistant version installed in the `.venv`, so a change that depends on Home Assistant behavior is proven across the matrix by CI, not locally. The VS Code **Problems** pane should also be quiet for every file touched. `pylint` is IDE-driven only, configured in [`pyproject.toml`](./pyproject.toml) but installed by nothing here and not a CI gate.

The `Docs lint job` in [`test-release-task.yml`](./.github/workflows/test-release-task.yml) runs `markdownlint` over all `*.md`, `cspell` over `README.md` and `HISTORY.md`, `actionlint`, `editorconfig-checker`, and `shellcheck` over `scripts/*`. **Run all five locally rather than deferring a check to CI because a tool is not installed.** Where a CLI is not on `PATH`, run it through its official image:

```sh
docker run --rm -v "$PWD:/workdir" -w /workdir ghcr.io/streetsidesoftware/cspell:latest --no-progress --config cspell.json README.md HISTORY.md
docker run --rm -v "$PWD:/workdir" -w /workdir davidanson/markdownlint-cli2:latest '**/*.md'
docker run --rm -v "$PWD:/workdir" -w /workdir rhysd/actionlint:latest -color
docker run --rm -v "$PWD":/check --workdir /check mstruebing/editorconfig-checker:latest
docker run --rm -v "$PWD:/workdir" -w /workdir koalaman/shellcheck:latest scripts/*
```

**What CI cannot exercise is the integration running inside Home Assistant.** `scripts/develop` boots a local Home Assistant against the gitignored `config/` directory with this integration loaded, on port 8123. A change to the config flow, entity naming, translations, or device registry behavior is worth a manual pass through the UI before merge, since the test harness mocks the parts a user sees. [`DEVCONTAINER.md`](./DEVCONTAINER.md) covers running and debugging it.

## Runbooks

### Add a Feature or Fix a Bug

Feature branch from `develop`, then code plus tests, then `scripts/fix`, `scripts/lint`, and `pytest`, then a pull request against `develop` with a descriptive title.

### Cut a Stable Release

Merge `develop -> main` with a merge commit, then dispatch the publisher on `main`:

```sh
gh workflow run publish-release.yml --ref main
```

The promotion merge publishes nothing by itself. Never dispatch a publish without explicit maintainer instruction.

### Cut a Prerelease

Dispatch the publisher on `develop` when a beta-tester build is wanted, with `gh workflow run publish-release.yml --ref develop`. NBGV versions it as `X.Y.Z-g<sha>` and the GitHub Release is marked a prerelease.

**Never manually create a GitHub release or a tag.** The pipeline owns this end to end.

### Raise the Minimum Home Assistant Version

Bumping the matrix `minimum` is intentional and rare. Do it in one pull request that also updates `hacs.json` `homeassistant` to match, the `requirements.txt` bootstrap pin (the same series, where a higher patch is fine), and any code that needs the newer API. Consider raising the base `major.minor` in [`version.json`](./version.json) in the same change, since dropping older Home Assistant versions breaks users still on them.

### Close an Issue From a Pull Request

**Put issue-closing keywords (`Closes #N`) in the `develop -> main` promotion pull request, not in the feature or `develop` one.** GitHub auto-closes an issue only from the pull request, or commit, that merges to the default branch, which is `main`. A `Closes #N` that merges only to `develop` never fires on promotion and leaves the issue open. Tag the promotion pull request's description, or close the issue by hand once the fix reaches `main`.

### Add a Dependabot Ecosystem

Edit [`.github/dependabot.yml`](./.github/dependabot.yml). Do not add `homeassistant` to it, since that package is explicitly ignored there and [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml) owns it.

## Backup and Recovery

The repository is the artifact, and GitHub holds the only copy that matters. Published GitHub Releases are what HACS installs from, so a bad release is superseded by the next dispatch rather than edited in place. The local `config/` directory is development state that `scripts/init-config` re-seeds, and deleting it loses nothing the repository needs, though see "Configuration Layout" for what it holds.

## Logs and Debugging

CI logs are the primary record: the PR gate in [`test-pull-request.yml`](./.github/workflows/test-pull-request.yml), the weekly retest and dispatches in [`publish-release.yml`](./.github/workflows/publish-release.yml), and the daily bump bot in [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml). Coverage uploads to Codecov.

Locally, `scripts/develop` runs Home Assistant with `--debug`, and the "Home Assistant (debug)" launch configuration in [`.vscode/launch.json`](./.vscode/launch.json) runs the same under the debugger. Integration diagnostics are downloadable from the device page in the Home Assistant UI, served by [`diagnostics.py`](./custom_components/purpleair/diagnostics.py).

## Tool Usage

- **Issue tracker and pull requests**: prefer the `gh` CLI, such as `gh pr view`, `gh pr list`, and `gh api repos/ptr727/homeassistant-purpleair/pulls/<N>/comments`.
- **Home Assistant core API reference**: when adding or changing entity behavior, check upstream conventions in `home-assistant/core`. The matrix `minimum` is pinned to 2026.8, the first release carrying the per-config-entry device lookup (`async_get_device_by_identifier`) the integration uses.
- **The client library**: the `aiopurpleair` client this integration depends on is maintained at [`ptr727/aiopurpleair`](https://github.com/ptr727/aiopurpleair) and published as `ptr727-aiopurpleair`. Client-side changes, such as a new endpoint or error code, belong there rather than here. `scripts/setup` clones its `develop` branch into the gitignored `./aiopurpleair` and installs it editable, so a library change can be exercised here before it is published.
- **The upstream core proposal was abandoned.** This integration is independent of the built-in Home Assistant PurpleAir integration, and the README's Credits section keeps the historical attribution. Do not mirror changes upstream.

## Configuration Layout

- **Bot identity.** The merge bot and the HA-version bump bot run as the `ptr727-codegen[bot]` App. Its repository secrets are `CODEGEN_APP_CLIENT_ID` (the App's Client ID) and `CODEGEN_APP_PRIVATE_KEY` (the App's private key, PEM contents), required in **both** the Actions and Dependabot secret stores, since a Dependabot-triggered run reads the Dependabot store. Workflows mint App tokens with `actions/create-github-app-token`, never a hard-coded value or a PAT.
- The App authors the squash-merges in [`merge-bot-pull-request.yml`](./.github/workflows/merge-bot-pull-request.yml), for Dependabot and HA-version bump pull requests, and authors the bump pull request itself in [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml). [`publish-release.yml`](./.github/workflows/publish-release.yml) uses the default `GITHUB_TOKEN` instead, since it fires no downstream workflow, so the release tag is created by `github-actions[bot]`.
- `CODECOV_TOKEN` is the Codecov upload token the pytest matrix uses, in both stores for the same reason.
- With no "Require approvals" on `develop` or `main`, bot pull requests auto-merge as soon as `Check pull request workflow status job` is green. If approvals are ever turned on, both `ptr727-codegen[bot]` and `dependabot[bot]` need to be on the bypass list. If a tag ruleset ever restricts tag creation, `github-actions[bot]` must be allowed to create release tags.
- **Local state on disk** is the `.venv`, the gitignored `config/` directory, and the gitignored `./aiopurpleair` checkout. **`config/` holds real credentials once the dev loop is used**: adding the PurpleAir integration stores its API key under `config/.storage/`, and so does any token given to the HACS install `scripts/setup` places there. Never commit, share, or copy `config/` as though it were secret-free.
- **The local `repo-config/` directory is a retired copy awaiting removal, not the authority.** The hub's `repo-config/configure.sh` and its payloads are the source for settings, rulesets, and labels, per [`AUDIT.md`](./AUDIT.md) section 4. Until the directory is deleted, do not run its `configure.sh` as the audit, since it predates the fleet's secret and label checks and passes a repository missing the Dependabot copy of `CODECOV_TOKEN`. [`WORKFLOW.md`](./WORKFLOW.md) and [`README.md`](./README.md) still describe the local copy and move with the deletion.

## Local Rule Extensions

Rules that apply in this repository on top of the carried fleet rules. Most are here because they are specific to this integration. The one that departs from a fleet default says so, and **where an extension here and a carried rule disagree, the extension wins in this repository**.

### Supported Platforms

Development is **Linux only**: native Linux, WSL2, or the devcontainer. This is the narrowing [`GOVERNANCE.md`](./GOVERNANCE.md) "Supported Development Platforms" describes, recorded here as that section requires. Home Assistant Core has POSIX-only dependencies and does not run natively on Windows, so a Windows-native environment can neither boot the integration with `scripts/develop` nor reliably run the Home Assistant test harness. The `scripts/*` dev loop and the `scripts/lint` gate assume a POSIX shell, and there is no "could not run `scripts/lint` on Windows" exception, since every supported environment has bash.

### Branching Facts

- **Mirror to `develop` any change that lands on `main` outside the feature, `develop`, `main` flow.** A reconciliation fix made to resolve a promotion conflict, or a security pull request that merges only to `main`, leaves `develop` behind on that content, and `develop` never back-merges to catch up. Before basing new work on `develop`, or diagnosing a defect from it, check `git diff origin/develop origin/main`. A non-empty content diff means `develop` is stale and the defect may already be fixed on `main`.

### Versioning Facts

The version is derived by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) (NBGV) from [`version.json`](./version.json) and git history, so nothing in the committed working tree carries the real version number.

- [`version.json`](./version.json) holds the base `major.minor`, the `publicReleaseRefSpec` regex matching `^refs/heads/main$`, and a `versionHeightOffset` so the first release of a series is `.0`. NBGV adds the adjusted commit height as the patch component, and on any ref not matching `publicReleaseRefSpec` appends a `-g{sha}` prerelease segment. So `main` produces clean SemVer such as `X.Y.Z`, and `develop` produces prereleases such as `X.Y.Z-g{sha}`.
- Bump the base `version` field by hand only when opening a new major or minor series. NBGV handles the patch.
- The `version` in [`manifest.json`](./custom_components/purpleair/manifest.json) is an all-zero placeholder. **Do not edit it.** [`build-release-task.yml`](./.github/workflows/build-release-task.yml) overwrites it with the NBGV-computed version on the runner before zipping the release artifact, so the published HACS zip carries the real version while git stays clean.
- [`hacs.json`](./hacs.json) has no `version` field, since HACS reads the version from the stamped manifest. Its `homeassistant` field is the **minimum** supported Home Assistant version, hand-maintained alongside the `requirements.txt` pin and the matrix `minimum`.

### HA Test Matrix

- [`.github/ha-test-versions.json`](./.github/ha-test-versions.json) drives the pytest matrix in [`test-release-task.yml`](./.github/workflows/test-release-task.yml) through three slots. `minimum` is hand-maintained and must match `hacs.json`'s `homeassistant`. The `requirements.txt` `homeassistant==` pin is only a bootstrap install and may pin a higher patch in the same series, since the matrix job reinstalls `homeassistant==<minimum>` so the actual gate holds. `latest-stable` is bot-maintained, the highest `pytest-homeassistant-custom-component` whose `homeassistant==` pin is a stable release. `latest-beta` is bot-maintained, the highest whose pin is a pre-release strictly newer than `latest-stable`, and it is `null` when no such beta exists.
- **All three slots gate equally.** There is no `continue-on-error` and no `gating: false` field, so a regression against any of them fails the pull request. The integration is meant to keep up with Home Assistant betas, and a failure is real signal rather than noise.
- The bump bot, [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml), runs **daily at 06:00 UTC**. It walks `pytest-homeassistant-custom-component` on PyPI in PEP 440 descending order, capped at ten versions, to resolve both candidates, then opens **one bundled pull request** on the rolling branch `ha-version-bump/matrix` covering whichever slots changed. Bundling is deliberate: an earlier two-PR design let a beta-clear pull request auto-merge before the matching stable bump, leaving `develop` with a stale stable slot and a null beta until the second landed.

### Release Flow

[`publish-release.yml`](./.github/workflows/publish-release.yml) is **dispatch-only**, and **merges never publish**. This departs from the fleet default in [`GOVERNANCE.md`](./GOVERNANCE.md) "Release Model", where an allowlisted bot's code-affecting merge to `main` auto-publishes, and in this repository the local rule wins: no merge publishes, the bot's included. HACS is a pull model that auto-pulls every new GitHub Release, so an automatic release on merge would force-update every user. The maintainer keeps both branches ready to release and ships on demand.

- A `workflow_dispatch` on `main` cuts a **stable** release, and on `develop` a **prerelease**. The `gate` job refuses a dispatch from any other ref. The `test-release` suite, the same one that gates pull requests, runs first, and `create-release` proceeds only on `needs.test-release.result == 'success'`. NBGV computes the version, the build stamps it into `manifest.json`, and the artifact is a single `purpleair.zip` attached to the release.
- **The weekly schedule retests `main` and never publishes.** A Monday cron runs `test-release` against the shipped `main`, and `create-release` is gated on `github.event_name == 'workflow_dispatch'`, so the schedule stops after testing. It catches upstream Home Assistant drift breaking the released integration, the publisher-side complement to the bump bot, which retests `develop`.
- **This is the HACS zip-deploy model**, and it is the reference for any future HACS repository. The committed `manifest.json` keeps the placeholder version, the version is injected into the zip at build time, and the release carries that one zip rather than a per-target asset set, because the HACS consumer reads the version from the manifest inside the zip rather than from an asset name.

### Release-Train Invariants

When reviewing a pull request that touches [`.github/workflows/`](./.github/workflows/) or [`.github/ha-test-versions.json`](./.github/ha-test-versions.json), check the change against these invariants. Each one is intentional and was reached after a real failure mode, so flag any drift, and escalate to the maintainer rather than implementing a relaxation, since these are explicit maintainer decisions rather than lint rules.

- **All test matrix slots gate equally.** Reject a change that adds `continue-on-error` or a `gating: false` field to any slot, or that drops or renames a slot. `latest-beta` may legitimately be `null`, but it never becomes advisory.
- **Publishing requires a green suite.** `create-release` requires `needs.test-release.result == 'success'` exactly. Reject a change that loosens it to `!= 'failure'` or re-allows `'skipped'`.
- **Merges never publish.** Reject any `push` trigger on the publisher, for `develop`, `main`, or both. `create-release` stays gated on `github.event_name == 'workflow_dispatch'`, so the schedule retests but never ships.
- **The bump bot uses one rolling branch and runs daily.** Reject a change that splits it back into per-slot branches, which re-introduces the beta-clear race, that switches to per-version branch names, which accumulate stale red pull requests, or that drops the cron back to weekly.
- **Beta failures do not silently merge.** A failing `test-release` on a bot pull request keeps it open, and `develop`'s pin lags upstream until a human ports the integration. That is the intended outcome, so do not suggest skipping or demoting the beta slot.
- **Dependabot auto-merges every tier, and the required checks are the gate rather than the bump magnitude.** The merge bot enables auto-merge on every Dependabot pull request, semver-major included, and a bump that breaks a covered path reds the required checks and stays open. Reject a change that re-introduces an `update-type` or `version-update:semver-major` filter on the merge step.
- **`merge-ha-version-bump` is this repository's upstream-version merge job.** It auto-merges the bundled bump pull request from `ha-version-bump/matrix`, on the same opened and reopened, base-ref-matched model as the Dependabot job.

### Workflow Gotchas

Each of these bit this repository at least once. Multi-line `if:` conditions and boolean inputs across `workflow_call` and `workflow_dispatch` are covered by [`GOVERNANCE.md`](./GOVERNANCE.md) "Workflow YAML Conventions" and are not restated here.

- **Job-level `permissions:` in a reusable workflow are validated against the caller before the job's `if:` runs**, so a skipped job with `contents: write` still causes a `startup_failure` on a caller that grants less. Declare permissions at the call site, or omit the inner block and inherit.
- **`actions/upload-artifact` accepts duplicate names from sibling reusable-workflow invocations in the same run.** That is undocumented behavior, so gate the duplicate path with an input flag rather than relying on it.

### Documentation Rules

- **The abandoned upstream core pull request is mentioned only in the README's Credits section.** Describe a limitation in terms of what would resolve it, such as "until the built-in integration adopts schema v2", rather than by pointing at the abandoned pull request, since scattered references would each need updating.
- **Quantitative claims in [`README.md`](./README.md)**, such as percentages, counts, and timings, are verified against current code or a reproducible measurement before being added or carried forward. Where a claim depends on a source constant, such as `STATIC_DEVICE_FIELDS`, `UPDATE_INTERVAL`, or the default-enabled entity set, add a one-line comment at that constant saying the README depends on it, so a refactor updates both.

### Commit Message Examples

[`GOVERNANCE.md`](./GOVERNANCE.md) "Pull Request Title and Commit Message Conventions" carries the rules. These are worked examples in this repository's own subject matter.

```text
Surface 24-hour PM2.5 average as a separate sensor
Skip empty PurpleAir API responses during polling
Drop support for Home Assistant < 2026.4
Bump ptr727-aiopurpleair from X.Y.Z to X.Y.(Z+1)
Clarify HACS install steps in README
```
