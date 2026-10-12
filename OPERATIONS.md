# Operations

How this repository is run: the checks to run before pushing, the runbooks for the tasks that recur, and the local rule extensions that apply here on top of the carried fleet rules in [`GOVERNANCE.md`](./GOVERNANCE.md).

## Local Verification

Run the full gate set before pushing or opening a pull request. `ruff` alone covers neither `mypy --strict` nor `pyright`, and both are CI gates, so skipping them locally means finding a trivial type error only after a CI round trip.

```sh
scripts/setup                 # once: provision the uv-managed .venv
scripts/fix                   # apply ruff format and ruff check --fix
scripts/lint                  # verify: ruff format --check, ruff check, mypy --strict, pyright
.venv/bin/pytest              # the test suite with branch coverage, as CI measures it, from the .venv scripts/setup built
.venv/bin/pytest --cov-report=term-missing
                              # the same run, listing each uncovered line
```

`scripts/lint` mirrors the CI ruff and `mypy --strict` checks in the hub validate task's `Lint sources job`, and the `pyright` step of this repository's [validate hook](./.github/actions/validate/action.yml). The `--cov` selector and `-ra` live in `pyproject.toml`'s pytest `addopts`, and the `mypy` settings in its `[tool.mypy]` section, since the hub task runs both tools with no arguments of its own. The hub's `Unit test job` runs the suite once per leg in the HA test matrix, and `latest-stable` runs two legs. A local run exercises only the Home Assistant version installed in the `.venv`. A change that depends on Home Assistant behavior is therefore proven across the matrix by CI, not locally. The VS Code **Problems** pane should also be quiet for every file touched. `pylint` is IDE-driven only, configured in [`pyproject.toml`](./pyproject.toml) but installed by nothing here and not a CI gate.

**A `pre-commit` hook runs the four `scripts/lint` checks on every commit.** It is configured in [`.pre-commit-config.yaml`](./.pre-commit-config.yaml) and runs the tools from the `.venv`, so `scripts/setup` has to have run first. It also runs the fleet's diff-scoped prose gate and line-ending check. `hub-fetch-run.py` fetches both fresh from the hub's `main` branch, so a commit needs network access. `scripts/setup` installs `pre-commit` with `uv tool install` and enables the hook in the base clone. A linked worktree shares the base clone's hooks directory, so `scripts/setup` leaves the hook alone there. Each linked worktree still needs its own `.venv` for the hook to run. The light way to build one is `uv venv --python 3.14 && uv pip install -r requirements-test.txt`. Inside a container, `scripts/setup` installs `pre-commit` but not the hook. A checkout bind-mounted from the host keeps the host's `.git`, where a hook installed from the container would point at a container-only Python. Install the hook from the host side there, where the host needs its own `.venv` too. A clone that lives inside the container runs `pre-commit install` in the container instead. Run `pre-commit run --all-files` to run the gate by hand. A commit that adds a code comment on purpose sets `PROSE_ALLOW_COMMENTS=1`, the local counterpart of the `comments` pull request label. The hook runs neither `pytest` nor the doc lint set, so the commands above and below still have to pass before a push.

The hub validate task's `Lint sources job` runs `markdownlint` over all `*.md`, `cspell` over `README.md` and `HISTORY.md`, `actionlint`, `editorconfig-checker`, and `shellcheck` and `shfmt -d` over every tracked shell script, `scripts/*` included. Its repository gate also shellchecks each composite action's `run:` bodies and schema-checks its `action.yml`. Its prose gate runs only on a `pull_request` event, which this repository's push-triggered workflow never sends, so the `pre-commit` hook's prose gate is the one that runs here. **Run all eight locally rather than deferring a check to CI because a tool is not installed.** Where a CLI is not on `PATH`, run it through its official image:

```sh
docker run --rm -v "$PWD:/workdir" -w /workdir ghcr.io/streetsidesoftware/cspell:latest --no-progress --config cspell.json README.md HISTORY.md
docker run --rm -v "$PWD:/workdir" -w /workdir davidanson/markdownlint-cli2:latest '**/*.md'
docker run --rm -v "$PWD:/workdir" -w /workdir rhysd/actionlint:latest -color
docker run --rm -v "$PWD":/check --workdir /check mstruebing/editorconfig-checker:latest
docker run --rm -v "$PWD:/workdir" -w /workdir koalaman/shellcheck:latest scripts/*
docker run --rm -v "$PWD:/mnt" -w /mnt mvdan/shfmt:v3.14.1 -d scripts/*
uvx check-jsonschema --builtin-schema vendor.github-actions -- .github/actions/*/action.yml
```

The composite-action shellcheck has no one-line form of its own. Run the hub's repository gate from a fresh hub checkout, `python3 <hub>/.github/actions/repo-gate/repo_gate.py --root . --check composite-actions`, which runs both halves the CI step runs.

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

Bumping the matrix `minimum` is intentional and rare. Do it in one pull request that updates every place carrying the minimum:

- The `minimum` slot in [`.github/ha-test-versions.json`](./.github/ha-test-versions.json). Set its `ha` to the new minimum. Set its `pytest-hacc` to the `pytest-homeassistant-custom-component` release that pins that `homeassistant==`.
- The `homeassistant` field in `hacs.json`.
- The Home Assistant version badge in the README.
- The version in "Tool Usage" below, and the API it names as the reason.
- The version in the header comment of the [`ha-test-matrix`](./.github/actions/ha-test-matrix/action.yml) action, and the API it names as the reason.
- Any code that needs the newer API.

Leave the `requirements.txt` `homeassistant==` pin alone, since it tracks `latest-stable` rather than the minimum. Consider raising the base `major.minor` in [`version.json`](./version.json) in the same change. Dropping older Home Assistant versions breaks users still on them.

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
- **Home Assistant core API reference**: when adding or changing entity behavior, check upstream conventions in `home-assistant/core`. The matrix `minimum` is pinned to 2026.10, the first release using the probatio flow-schema API (`probatio.Schema`) that the config flow builds its schemas with.
- **The client library**: the `aiopurpleair` client this integration depends on is maintained at [`ptr727/aiopurpleair`](https://github.com/ptr727/aiopurpleair) and published as `ptr727-aiopurpleair`. Client-side changes, such as a new endpoint or error code, belong there rather than here. `scripts/setup` clones its `develop` branch into the gitignored `./aiopurpleair` and installs it editable, so a library change can be exercised here before it is published.
- **The upstream core proposal was abandoned.** This integration is independent of the built-in Home Assistant PurpleAir integration, and the README's Credits section keeps the historical attribution. Do not mirror changes upstream.

## Configuration Layout

- **Bot identity.** The merge bot and the HA-version bump bot run as the `ptr727-codegen[bot]` App. Its repository secrets are `CODEGEN_APP_CLIENT_ID` (the App's Client ID) and `CODEGEN_APP_PRIVATE_KEY` (the App's private key, PEM contents), required in **both** the Actions and Dependabot secret stores, since a Dependabot-triggered run reads the Dependabot store. Workflows mint App tokens with `actions/create-github-app-token`, never a hard-coded value or a PAT.
- The App authors the squash-merges in [`merge-bot-pull-request.yml`](./.github/workflows/merge-bot-pull-request.yml), for Dependabot and HA-version bump pull requests, and authors the bump pull request itself in [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml). [`publish-release.yml`](./.github/workflows/publish-release.yml) uses the default `GITHUB_TOKEN` instead, since nothing downstream listens for its release tag, so the tag is created by `github-actions[bot]`. That token can still dispatch the publisher again for the `WORKFLOW.md` D4.8 supersede, because `workflow_dispatch` is exempt from its rule against triggering workflows.
- `CODECOV_TOKEN` is the Codecov upload token the pytest matrix uses, in both stores for the same reason.
- With no "Require approvals" on `develop` or `main`, bot pull requests auto-merge as soon as `Check pull request workflow status job` is green. If approvals are ever turned on, both `ptr727-codegen[bot]` and `dependabot[bot]` need to be on the bypass list. If a tag ruleset ever restricts tag creation, `github-actions[bot]` must be allowed to create release tags.
- **Local state on disk** is the `.venv`, the gitignored `config/` directory, and the gitignored `./aiopurpleair` checkout. **`config/` holds real credentials once the dev loop is used**: adding the PurpleAir integration stores its API key under `config/.storage/`, and so does any token given to the HACS install `scripts/setup` places there. Never commit, share, or copy `config/` as though it were secret-free.

## Local Rule Extensions

Rules that apply in this repository on top of the carried fleet rules. Most are here because they are specific to this integration. Each one that departs from a fleet default says so. **Where an extension here and a carried rule disagree, the extension wins in this repository**.

### Supported Platforms

Development is **Linux only**: native Linux, WSL2, or the devcontainer. This is the narrowing [`GOVERNANCE.md`](./GOVERNANCE.md) "Supported Development Platforms" describes, recorded here as that section requires. Home Assistant Core has POSIX-only dependencies and does not run natively on Windows, so a Windows-native environment can neither boot the integration with `scripts/develop` nor reliably run the Home Assistant test harness. The `scripts/*` dev loop and the `scripts/lint` gate assume a POSIX shell, and there is no "could not run `scripts/lint` on Windows" exception, since every supported environment has bash.

### Bash Dev Loop

The `scripts/*` dev loop (`setup`, `fix`, `lint`, `develop`, `init-config`) stays Bash. This departs from the fleet default in [`CODESTYLE.md`](./CODESTYLE.md) "Shell", which allows Bash only where a program cannot be Python. It is the Home Assistant integration-scaffold convention, which integration contributors already know. The devcontainer's `postCreateCommand` and the VS Code tasks also call these paths. The scripts otherwise meet the fleet's shell rules. Each opens with `set -Eeuo pipefail`, answers `-h` and `--help`, and refuses any other argument before doing work. The hub validate task's `Lint sources job` runs `shellcheck` and `shfmt -d` over them. A script outside this dev loop follows the fleet default.

### Branching Facts

- **Mirror to `develop` any change that lands on `main` outside the feature, `develop`, `main` flow.** A reconciliation fix made to resolve a promotion conflict, or a security pull request that merges only to `main`, leaves `develop` behind on that content, and `develop` never back-merges to catch up. Before basing new work on `develop`, or diagnosing a defect from it, check `git diff origin/develop origin/main`. A non-empty content diff means `develop` is stale and the defect may already be fixed on `main`.

### Versioning Facts

The version is derived by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning) (NBGV) from [`version.json`](./version.json) and git history, so nothing in the committed working tree carries the real version number.

- [`version.json`](./version.json) holds the base `major.minor`, the `publicReleaseRefSpec` regex matching `^refs/heads/main$`, and a `versionHeightOffset` so the first release of a series is `.0`. NBGV adds the adjusted commit height as the patch component, and on any ref not matching `publicReleaseRefSpec` appends a `-g{sha}` prerelease segment. So `main` produces clean SemVer such as `X.Y.Z`, and `develop` produces prereleases such as `X.Y.Z-g{sha}`.
- Bump the base `version` field by hand only when opening a new major or minor series. NBGV handles the patch.
- The `version` in [`manifest.json`](./custom_components/purpleair/manifest.json) is an all-zero placeholder. **Do not edit it.** The [`build-release-asset`](./.github/actions/build-release-asset/action.yml) hook, which the hub's release task runs, overwrites it on the runner with the NBGV-computed version before zipping. The published HACS zip therefore carries the real version while git stays clean.
- [`manifest.json`](./custom_components/purpleair/manifest.json) declares `ptr727-aiopurpleair` as a **minimum** (`>=`), not an exact pin. HA installs the newest release the minimum allows whenever the library is missing. That happens on a new install, and on every Core update of a Docker-based install, since the update replaces the container and library. Otherwise HA leaves an installed library alone while it satisfies the minimum. A venv install therefore moves forward only when the minimum rises above what it has. [`requirements-test.txt`](./requirements-test.txt) pins the exact version CI tests, and Dependabot bumps only that pin. Two pytest legs install the manifest's minimum over that pin, one on the `minimum` Home Assistant and one on `latest-stable`. Both run `mypy --strict` and the tests against the oldest allowed release. The `latest-stable` one covers a venv install that keeps upgrading Home Assistant. The tests mock the API client without a spec, so only the type check catches a call to a method or keyword the minimum lacks. `tests/components/purpleair/test_manifest.py` fails when the tested pin falls outside the manifest's requirement. Raise the manifest minimum by hand when the integration starts depending on a newer library release.
- [`hacs.json`](./hacs.json) has no `version` field, since HACS reads the version from the stamped manifest. Its `homeassistant` field is the **minimum** supported Home Assistant version, hand-maintained alongside the matrix `minimum`.

### HA Test Matrix

- [`.github/ha-test-versions.json`](./.github/ha-test-versions.json) drives the pytest matrix through three slots. The [`ha-test-matrix`](./.github/actions/ha-test-matrix/action.yml) action reads it at run time, and the `Read HA test matrix job` in [`test-pull-request.yml`](./.github/workflows/test-pull-request.yml) and [`publish-release.yml`](./.github/workflows/publish-release.yml) passes the legs to the hub `validate-task.yml` as its `test-matrix` input. The hub's `Unit test job` runs one leg per entry on the Python 3.14 the callers name in `python-versions`. It installs `requirements*.txt` into `.venv`, calls the [`install-test-deps`](./.github/actions/install-test-deps/action.yml) hook with the leg, and then runs pytest without re-syncing. `minimum` is hand-maintained and must match `hacs.json`'s `homeassistant`. The `requirements.txt` `homeassistant==` pin is the development and bootstrap install. It tracks `latest-stable`, and [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml) rewrites it with that slot. The hub's type check and the validate hook's pyright install it, so they check against `latest-stable` rather than the minimum. The hook reinstalls each leg's own slot's `homeassistant==` and `pytest-homeassistant-custom-component==`, so the gate on every slot holds. `latest-stable` is bot-maintained, the highest `pytest-homeassistant-custom-component` whose `homeassistant==` pin is a stable release. `latest-beta` is bot-maintained, the highest whose pin is a pre-release strictly newer than `latest-stable`. It is `null` when no such beta exists.
- Each matrix leg also carries an `aiopurpleair` field, set to `minimum` or `pin`. A `minimum` leg replaces the `requirements-test.txt` pin of `ptr727-aiopurpleair` with the `>=` minimum from `manifest.json`. It then runs `mypy --strict` against that minimum before the tests. A `pin` leg keeps the pin. The `minimum` slot runs the minimum library, and `latest-beta` runs the pin. `latest-stable` runs twice, once per library, and its second leg is labeled `latest-stable-min-lib`. That leg tests a venv install, which keeps an old library while it upgrades Home Assistant. The hook runs that type check, since the leg's environment exists only inside the hub's `Unit test job`. On the `minimum` slot's leg it also runs against the minimum Home Assistant, which the hub's own type check does not. A typing failure there but not on `latest-stable-min-lib` points at the minimum Home Assistant.
- **All three slots gate equally.** There is no `continue-on-error` and no `gating: false` field, so a regression against any of them fails the pull request. The integration is meant to keep up with Home Assistant betas, and a failure is real signal rather than noise.
- The bump bot, [`check-ha-version.yml`](./.github/workflows/check-ha-version.yml), runs **daily at 06:00 UTC**. It walks `pytest-homeassistant-custom-component` on PyPI in PEP 440 descending order, capped at ten versions, to resolve both candidates, then opens **one bundled pull request** on the rolling branch `ha-version-bump/matrix` covering whichever slots changed. Bundling is deliberate: an earlier two-PR design let a beta-clear pull request auto-merge before the matching stable bump, leaving `develop` with a stale stable slot and a null beta until the second landed.

### Release Flow

[`publish-release.yml`](./.github/workflows/publish-release.yml) is **dispatch-only**, and **merges never publish**. This departs from the fleet default in [`GOVERNANCE.md`](./GOVERNANCE.md) "Release Model", where an allowlisted bot's code-affecting merge to `main` auto-publishes, and in this repository the local rule wins: no merge publishes, the bot's included. HACS is a pull model that auto-pulls every new GitHub Release, so an automatic release on merge would force-update every user. The maintainer keeps both branches ready to release and ships on demand.

- A `workflow_dispatch` on `main` cuts a **stable** release, and on `develop` a **prerelease**. The `plan` job, the hub's `publish-plan-task.yml`, refuses a dispatch from any other ref. The `validate` job, the same hub validate task with the same inputs that gate pull requests, runs first, and `publish` proceeds only on `needs.validate.result == 'success'`. NBGV computes the version, and the hub's release task runs this repository's `build-release-asset` hook to stamp it into `manifest.json` and build `purpleair.zip`. The release carries that one zip, plus the `README.md` and `LICENSE` the hub task attaches to every release.
- **A bot's workflow push during a publish supersedes it.** `GITHUB_TOKEN` cannot tag a commit whose workflow files differ from the branch head. Where only the codegen App or Dependabot pushed since the dispatch, the hub task dispatches the publisher again on that branch and cancels the run. The new run retests and publishes the newer head. Any other push fails the run. This keeps the dispatch-only rule, since only a maintainer dispatch starts the release, and neither bot writes to `custom_components/`, so the zip's code is unchanged. `WORKFLOW.md` D4.8 lists three gaps in that hand-off, so confirm the release appeared.
- **The weekly schedule retests `main` and never publishes.** A Monday cron runs `validate` against the shipped `main`, and `publish` is gated on `github.event_name == 'workflow_dispatch'`, so the schedule stops after testing. The hub plan reports `publish=true` for a schedule, its Docker-refresh case, so that event gate is what keeps the retest from shipping, and `validate` runs on any successful plan rather than on that output. It catches upstream Home Assistant drift breaking the released integration, the publisher-side complement to the bump bot, which retests `develop`.
- **Each ref serializes on its own.** The publisher's concurrency group is ref-scoped with `cancel-in-progress: false`, per `WORKFLOW.md` D7.1. A `main` and a `develop` dispatch build different tags and branch-scoped artifacts, so they run side by side. GitHub keeps one pending run per group and a newer one replaces it, so the schedule's retest takes a per-run group and never replaces a pending dispatch.
- **This is the HACS zip-deploy model**, and it is the reference for any future HACS repository. The committed `manifest.json` keeps the placeholder version, the version is injected into the zip at build time, and the release carries that one zip rather than a per-target asset set, because the HACS consumer reads the version from the manifest inside the zip rather than from an asset name.

### Release-Train Invariants

When reviewing a pull request that touches [`.github/workflows/`](./.github/workflows/) or [`.github/ha-test-versions.json`](./.github/ha-test-versions.json), check the change against these invariants. Each one is intentional and was reached after a real failure mode, so flag any drift, and escalate to the maintainer rather than implementing a relaxation, since these are explicit maintainer decisions rather than lint rules.

- **All test matrix slots gate equally.** Reject a change that adds `continue-on-error` or a `gating: false` field to any slot, or that drops or renames a slot. `latest-beta` may legitimately be `null`, but it never becomes advisory.
- **Publishing requires a green suite.** `publish` requires `needs.validate.result == 'success'` exactly. Reject a change that loosens it to `!= 'failure'` or re-allows `'skipped'`.
- **Merges never publish.** Reject any `push` trigger on the publisher, for `develop`, `main`, or both. `publish` stays gated on `github.event_name == 'workflow_dispatch'`, so the schedule retests but never ships.
- **The bump bot uses one rolling branch and runs daily.** Reject a change that splits it back into per-slot branches, which re-introduces the beta-clear race, that switches to per-version branch names, which accumulate stale red pull requests, or that drops the cron back to weekly.
- **Beta failures do not silently merge.** A failing `validate` on a bot pull request keeps it open, and `develop`'s pin lags upstream until a human ports the integration. That is the intended outcome, so do not suggest skipping or demoting the beta slot.
- **Dependabot auto-merges every tier, and the required checks are the gate rather than the bump magnitude.** The merge bot enables auto-merge on every Dependabot pull request, semver-major included, and a bump that breaks a covered path reds the required checks and stays open. Reject a change that re-introduces an `update-type` or `version-update:semver-major` filter on the merge step.
- **The merge bot carries an `ha-version-bump/` rule.** The hub's `merge-bot-task.yml` auto-merges App pull requests only for its built-in branch pairs. So [`merge-bot-pull-request.yml`](./.github/workflows/merge-bot-pull-request.yml) passes a `rules` entry for an `ha-version-bump/` head into `develop`, which covers the bundled bump pull request. Reject a change that drops it, since that pull request would then get a warning annotation instead of auto-merge.

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
