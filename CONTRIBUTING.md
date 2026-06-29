# Contribution guidelines

Contributions are welcome - bug reports, fixes, feature proposals, and documentation improvements.

## Workflow

1. Fork the repo and branch from `develop` (releases are cut from `main`).
1. Make your change and update any affected documentation.
1. Apply auto-fixes with `scripts/fix` (runs `ruff format` + `ruff check --fix`).
1. Verify with `scripts/lint` (verify-only: `ruff format --check` + `ruff check` + `mypy --strict` + `pyright`). CI runs the same checks.
1. Run the test suite with `pytest` (install `requirements-test.txt` first).
1. Open a pull request against `develop` with a clear, descriptive title. CI runs on every branch push (not on `pull_request`); a fork PR's pushes do not run the base-repo check, so a maintainer re-runs the required check by landing your change on an in-repo branch before merge.

## PR titles and versioning

PR titles are descriptive and have no versioning effect - write a clear imperative subject summarizing the change. Feature -> develop PRs **squash-merge** (PR title becomes the single commit on develop). Develop -> main PRs **merge-commit** (one merge commit on main per release, preserving develop's history as a parent so the next promotion has a clean merge base). Both methods are pinned in branch rulesets - the PR UI will only offer the correct option for each target.

Versioning is handled by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning), which derives the SemVer string from [version.json](version.json) (base `major.minor`) plus the git commit-height since that base was last bumped. The patch component and any prerelease suffix are computed automatically; nothing in the working tree carries the version number, and commit messages aren't parsed.

### Release flow

- Merging a PR into `develop` does **not** publish - merges never publish. Releases are cut on demand by dispatching the publisher: `gh workflow run publish-release.yml --ref develop` cuts a prerelease (`0.2.5-g1a2b3c4`, the `-g{sha}` suffix marks it prerelease), and `--ref main` cuts a clean stable release (`0.2.6`). A dispatch publishes only when the full test suite passes on that ref.
- Promoting `develop -> main` (a normal merge-commit PR) does **not** auto-publish; the maintainer dispatches the stable release from `main` afterward.
- Dependabot PRs and HA-version-bump PRs auto-merge into `develop` after CI passes; merging them does **not** publish.
- A weekly scheduled run of [publish-release.yml](.github/workflows/publish-release.yml) **retests** the shipped `main` against the latest HA matrix and never publishes - a red run flags upstream HA drift breaking the released integration for a maintainer to act on.
- A scheduled bot ([check-ha-version.yml](.github/workflows/check-ha-version.yml)) keeps the HA test matrix current with PyPI. It runs **daily at 06:00 UTC** and opens a single bundled PR on the rolling branch `ha-version-bump/matrix` whenever a newer `pytest-homeassistant-custom-component` release on PyPI pins a stable HA release, an HA pre-release newer than the current stable, or both. Pinned versions live in [.github/ha-test-versions.json](.github/ha-test-versions.json) under three slots - `minimum` (hand-maintained backward-compat floor), `latest-stable`, and `latest-beta` (`null` when no upcoming beta exists). All three slots gate equally; a regression on any one fails the PR.

### Bumping the minimum HA version

The `minimum` entry in [.github/ha-test-versions.json](.github/ha-test-versions.json) is hand-maintained - bump it (and the matching `homeassistant` field in [hacs.json](hacs.json) and the pin in [requirements.txt](requirements.txt)) in a regular PR whenever you need to drop support for an older HA series. Bumping it is a breaking change for users on older HA versions, so consider raising the base `major.minor` in [version.json](version.json) at the same time.

## Reporting bugs

File issues on the [issue tracker](../../issues/new/choose). Good reports include:

- A quick summary and environment details (HA version, integration version).
- Steps to reproduce.
- What you expected vs. what actually happened.
- Relevant log snippets or diagnostics output.

## Coding style

Code is formatted and linted with [ruff](https://docs.astral.sh/ruff/) - configured in [.ruff.toml](.ruff.toml), and type-checked with `mypy --strict` and `pyright`. Use `scripts/fix` to auto-fix and `scripts/lint` to verify (CI only runs the latter).

## License

This project is licensed under the Apache License, Version 2.0 - see [LICENSE](LICENSE) and [NOTICE](NOTICE). By contributing, you agree that your contributions will be licensed under the same terms.
