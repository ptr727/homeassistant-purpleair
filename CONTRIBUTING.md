# Contribution guidelines

Contributions are welcome — bug reports, fixes, feature proposals, and documentation improvements.

## Workflow

1. Fork the repo and branch from `develop` (releases are cut from `main`).
2. Make your change and update any affected documentation.
3. Lint your code with `scripts/lint` (runs `ruff format` + `ruff check --fix`).
4. Run the test suite with `pytest` (install `requirements-test.txt` first).
5. Open a pull request against `develop`.

For upstream-relevant functional changes, please also raise them on [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) so the fix lands in Home Assistant core and benefits all users.

## Reporting bugs

File issues on the [issue tracker](../../issues/new/choose). Good reports include:

- A quick summary and environment details (HA version, integration version).
- Steps to reproduce.
- What you expected vs. what actually happened.
- Relevant log snippets or diagnostics output.

## Coding style

Code is formatted and linted with [ruff](https://docs.astral.sh/ruff/) — configured in [.ruff.toml](.ruff.toml). `scripts/lint` runs both format and check passes.

## License

This project is licensed under the Apache License, Version 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE). By contributing, you agree that your contributions will be licensed under the same terms.
