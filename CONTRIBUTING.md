# Contribution guidelines

Contributions are welcome — bug reports, fixes, feature proposals, and documentation improvements.

## Workflow

1. Fork the repo and branch from `develop` (releases are cut from `main`).
2. Make your change and update any affected documentation.
3. Apply auto-fixes with `scripts/fix` (runs `ruff format` + `ruff check --fix`).
4. Verify with `scripts/lint` (verify-only: `ruff format --check` + `ruff check` + `mypy --strict`). CI runs the same checks.
5. Run the test suite with `pytest` (install `requirements-test.txt` first).
6. Open a pull request against `develop` with a Conventional Commit-style title (see below).

For upstream-relevant functional changes, please also raise them on [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) so the fix lands in Home Assistant core and benefits all users.

## PR titles and versioning

Releases are automated by [release-please](https://github.com/googleapis/release-please) reading PR titles. PRs are squash-merged, so the PR title becomes the commit message and is the only thing release-please sees. Titles must follow [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix             | Effect on next release             | Example                                           |
| ------------------ | ---------------------------------- | ------------------------------------------------- |
| `feat:`            | Minor bump (`0.x.0`)               | `feat: add support for outdoor sensors`           |
| `fix:` / `perf:`   | Patch bump (`0.0.x`)               | `fix: handle empty PurpleAir API response`        |
| `<type>!:` / `BREAKING CHANGE:` footer | Major bump (`x.0.0`) | `feat!: drop support for HA < 2026.4`           |
| `chore:` / `docs:` / `refactor:` / `test:` / `build:` / `ci:` / `revert:` | No release | `chore: bump dev requirements`         |

Per Conventional Commits, `!` after **any** type marks a breaking change and forces a major bump — `feat!:`, `fix!:`, `refactor!:`, etc. all qualify.

A required CI check (`pr-title-lint`) blocks merge if the title isn't Conventional. Repository merge method is locked to **squash-only** so the PR title is preserved as the single commit on `develop` / `main`.

### Release flow

- Merging a `feat:`/`fix:` PR into `develop` causes the release-please bot to open or update a release PR titled `chore(develop): release X.Y.Z-beta.N`. When that PR auto-merges (after CI passes), tag `X.Y.Z-beta.N` is pushed and a prerelease GitHub release is published.
- Promoting `develop` → `main` (a normal PR) opens a stable release PR `chore(main): release X.Y.Z`, which on auto-merge tags `X.Y.Z` and publishes the stable release.
- Dependabot PRs are titled `chore(deps): …` and auto-merge into `develop` without triggering a release; they ride along in the next `feat:`/`fix:` release.
- A scheduled bot (`check-ha-version.yml`) opens a `fix: bump Home Assistant test matrix to …` PR weekly when `pytest-homeassistant-custom-component` pins a newer HA version. The bumped HA version is in [.github/ha-test-versions.json](.github/ha-test-versions.json).

### Bumping the minimum HA version

The `minimum` entry in [.github/ha-test-versions.json](.github/ha-test-versions.json) is hand-maintained — bump it (and the matching `homeassistant` field in [hacs.json](hacs.json) and the pin in [requirements.txt](requirements.txt)) in a regular PR titled `feat!: raise minimum Home Assistant version to YYYY.M.N` whenever you need to drop support for an older HA series.

## Reporting bugs

File issues on the [issue tracker](../../issues/new/choose). Good reports include:

- A quick summary and environment details (HA version, integration version).
- Steps to reproduce.
- What you expected vs. what actually happened.
- Relevant log snippets or diagnostics output.

## Coding style

Code is formatted and linted with [ruff](https://docs.astral.sh/ruff/) — configured in [.ruff.toml](.ruff.toml), and type-checked with `mypy --strict`. Use `scripts/fix` to auto-fix and `scripts/lint` to verify (CI only runs the latter).

## License

This project is licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). By contributing, you agree that your contributions will be licensed under the same terms.
