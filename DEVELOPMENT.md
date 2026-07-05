# PurpleAir Integration for Home Assistant

## Development

Development runs inside the VS Code **devcontainer** (or a Linux/WSL2 host - Home Assistant Core doesn't run on Windows natively). Open the repo in the devcontainer; `scripts/setup` runs automatically and installs everything into a uv-managed `.venv`.

### Dev loop

```sh
scripts/setup     # provision the uv .venv: HA + test deps + editable aiopurpleair
scripts/develop   # boot Home Assistant against ./config with this integration loaded
scripts/fix       # apply ruff auto-fixes (format + check --fix)
scripts/lint      # verify-only: ruff format --check + ruff check + mypy --strict + pyright (mirrors CI)
pytest            # run the test suite (in the .venv, after scripts/setup)
```

`scripts/lint` is the CI gate - it fails non-zero on any ruff, format, `mypy --strict`, or `pyright` violation so "green locally" matches "green on GitHub". When it fails on an auto-fixable issue, run `scripts/fix` and re-run lint.

`scripts/setup` clones the `aiopurpleair/` folder (from [`ptr727/aiopurpleair`][aiopurpleair-repo-link], gitignored) and installs it **editable** via `uv pip install`, so local library edits flow into both `scripts/develop` and pytest without round-tripping through PyPI. It does not run the library's own [uv][uv-link] setup unless you set `RUN_AIOPURPLEAIR_SETUP=1`; to run the library's own suite, `cd aiopurpleair && uv sync --all-groups && uv run pytest`.

Each script is wired as a VS Code task in [.vscode/tasks.json](.vscode/tasks.json) (**Command Palette -> Tasks: Run Task**):

| Script | VS Code task | Shortcut |
| --- | --- | --- |
| `scripts/setup` | **Setup: Install dev requirements** | Tasks: Run Task |
| `scripts/develop` | **Develop: Run Home Assistant** | Tasks: Run Task |
| `scripts/fix` | **Fix: ruff format + check --fix** | Tasks: Run Task |
| `scripts/lint` | **Lint: ruff + mypy + pyright (verify)** | `Ctrl+Shift+B` (default build task) |
| `pytest` | **Test: pytest** | Tasks: Run Test Task (default) |

### Run and debug Home Assistant

- **Run:** `scripts/develop` (or the **Develop: Run Home Assistant** task) boots HA against `./config` with the integration loaded. Open the forwarded port **8123** for the web UI.
- **Debug:** press **F5** (**Home Assistant (debug)** in [.vscode/launch.json](.vscode/launch.json)) to run HA under the debugger - breakpoints in `custom_components/purpleair/` hit, `PYTHONPATH` and the editable `ptr727-aiopurpleair` are preserved, and `./config` is created on first run.

### Devcontainer and host prerequisites

[`.devcontainer.json`](.devcontainer.json) provisions Python 3.14, uv, Node, and the linters (via features), runs `scripts/setup`, and forwards port 8123. Commits are **SSH-signed** using your host's `ssh-agent` (VS Code forwards the socket into the container) plus the bind-mounted public signing key and `allowed_signers`; `gh` uses the mounted host config.

Set up on the **host** before opening the devcontainer:

- **Git identity and SSH commit signing** - see GitHub's [Telling Git about your SSH key][gh-ssh-signing] and [About commit signature verification][gh-sig-verify].
- A running **`ssh-agent` with your signing key loaded**, so VS Code can forward it into the container - see VS Code's [Sharing Git credentials with your container][vscode-share-creds].
- On **WSL**, Docker Desktop's [WSL integration][docker-wsl] enabled.
- These host paths must exist (they are bind-mounted, and a missing path fails the container build): `~/.ssh/id_ed25519.pub`, `~/.config/git/allowed_signers`, `~/.config/gh`.

If you don't sign commits or don't want the mounts, remove the `mounts` block from `.devcontainer.json` locally, or work on a plain Linux/WSL2 host instead.

[aiopurpleair-repo-link]: https://github.com/ptr727/aiopurpleair
[docker-wsl]: https://docs.docker.com/desktop/wsl/
[gh-sig-verify]: https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification
[gh-ssh-signing]: https://docs.github.com/en/authentication/managing-commit-signature-verification/telling-git-about-your-signing-key
[uv-link]: https://github.com/astral-sh/uv
[vscode-share-creds]: https://code.visualstudio.com/remote/advancedcontainers/sharing-git-credentials
