# Contribution guidelines

Contributions are welcome — bug reports, fixes, feature proposals, and
documentation improvements.

## Workflow

1. Fork the repo and branch from `develop` (releases are cut from `main`).
1. Make your change and update any affected documentation.
1. Apply auto-fixes with `scripts/fix` (runs `ruff format` + `ruff check --fix`).
1. Verify with `scripts/lint` (verify-only: `ruff format --check` + `ruff check` + `mypy --strict`). CI runs the same checks.
1. Run the test suite with `pytest` (install `requirements-test.txt` first).
1. Open a pull request against `develop` with a clear, descriptive title.

For upstream-relevant functional changes, please also raise them on [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) so the fix lands in Home Assistant core and benefits all users.

## PR titles and versioning

PR titles are descriptive and have no versioning effect — write a clear imperative subject summarizing the change. The repository's merge method is locked to **squash-only**, so the PR title becomes the single commit message on `develop` / `main`.

Versioning is handled by [Nerdbank.GitVersioning](https://github.com/dotnet/Nerdbank.GitVersioning), which derives the SemVer string from [version.json](version.json) (base `major.minor`) plus the git commit-height since that base was last bumped. The patch component and any prerelease suffix are computed automatically; nothing in the working tree carries the version number, and commit messages aren't parsed.

### Release flow

- Merging a PR into `develop` automatically publishes a prerelease GitHub Release with a version like `0.1.5-g1a2b3c4` (the `-g{sha}` suffix marks it as a prerelease). Beta testers always have the latest develop snapshot.
- Promoting `develop → main` (a normal PR) does **not** auto-publish. A maintainer cuts the stable release manually with `gh workflow run publish-release.yml --ref main`, which produces a clean release like `0.1.6`.
- Dependabot PRs and HA-version-bump PRs auto-merge into `develop` after CI passes; their merge produces a fresh prerelease with no maintainer action.
- A scheduled bot ([check-ha-version.yml](.github/workflows/check-ha-version.yml)) opens a "Bump Home Assistant test matrix to …" PR weekly when `pytest-homeassistant-custom-component` pins a newer HA version. The bumped HA version lives in [.github/ha-test-versions.json](.github/ha-test-versions.json).

### Bumping the minimum HA version

The `minimum` entry in [.github/ha-test-versions.json](.github/ha-test-versions.json) is hand-maintained — bump it (and the matching `homeassistant` field in [hacs.json](hacs.json) and the pin in [requirements.txt](requirements.txt)) in a regular PR whenever you need to drop support for an older HA series. Bumping it is a breaking change for users on older HA versions, so consider raising the base `major.minor` in [version.json](version.json) at the same time.

## Reporting bugs

File issues on the [issue tracker](../../issues/new/choose). Good reports
include:

- A quick summary and environment details (HA version, integration version).
- Steps to reproduce.
- What you expected vs. what actually happened.
- Relevant log snippets or diagnostics output.

## Coding style

Code is formatted and linted with [ruff](https://docs.astral.sh/ruff/) —
configured in [.ruff.toml](.ruff.toml), and type-checked with `mypy --strict`.
Use `scripts/fix` to auto-fix and `scripts/lint` to verify (CI only runs the
latter).

## License

This project is licensed under the Apache License, Version 2.0 — see
[LICENSE](LICENSE) and [NOTICE](NOTICE). By contributing, you agree that your
contributions will be licensed under the same terms.
