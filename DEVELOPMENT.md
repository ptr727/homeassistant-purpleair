# PurpleAir Integration for Home Assistant

## Development

The repo includes a VS Code devcontainer and helper scripts:

```sh
scripts/setup     # install dev requirements
scripts/develop   # boot Home Assistant against ./config with this integration loaded
scripts/fix       # apply ruff auto-fixes (format + check --fix)
scripts/lint      # verify-only: ruff format --check + ruff check + mypy --strict + pyright (mirrors CI)
pytest            # run the test suite (after pip install -r requirements-test.txt)
```

`scripts/lint` is the CI gate - it fails non-zero on any ruff, format, `mypy --strict`, or `pyright` violation so "green locally" matches "green on GitHub". When it fails on an auto-fixable issue, run `scripts/fix` and re-run lint.

If you also run tests in the `aiopurpleair/` workspace folder, use a separate virtual environment for that repo - it is managed with [uv][uv-link] and has its own lock:

```sh
cd aiopurpleair
uv sync --all-groups
uv run pytest
```

`scripts/setup` clones the `aiopurpleair/` folder (from [`ptr727/aiopurpleair`][aiopurpleair-repo-link], gitignored) and pip-installs it **editable** into the integration's dev environment, so local library edits flow into both `scripts/develop` and pytest without round-tripping through PyPI. It does not run the library's own `uv sync` unless you opt in with `RUN_AIOPURPLEAIR_SETUP=1`.

Each script is also wired up as a VS Code task in [.vscode/tasks.json](.vscode/tasks.json) - open **Command Palette -> Tasks: Run Task**, or use the shortcuts below:

| Script | VS Code task | Shortcut |
| --- | --- | --- |
| `scripts/setup` | **Setup: Install dev requirements** | Tasks: Run Task |
| `scripts/develop` | **Develop: Run Home Assistant** | Tasks: Run Task |
| `scripts/fix` | **Fix: ruff format + check --fix** | Tasks: Run Task |
| `scripts/lint` | **Lint: ruff + mypy + pyright (verify)** | `Ctrl+Shift+B` (default build task) |
| `pytest` | **Test: pytest** | Tasks: Run Test Task (default test) |

Additional useful tasks in the same file:

- **Test: pytest + branch coverage** - run CI-style branch coverage locally.

### Devcontainer Setup

The [`.devcontainer.json`](.devcontainer.json) bind-mounts host paths into the container so existing host credentials (the public half of your SSH signing key, plus GitHub CLI auth where the token is file-backed) work inside it without re-setup. The `gh` part is conditional. `gh auth login` always writes the per-host config (username, git protocol, etc.) to `~/.config/gh/hosts.yml`, but it stores the **token** in a credential store by default when one is available - Keychain on macOS, libsecret/Secret Service on Linux desktops - and only writes the token to the file when no store is found or you passed `--insecure-storage`. So on credential-store hosts, `~/.config/gh/hosts.yml` exists but has no `oauth_token` line; the bind-mount therefore carries no token, and container `gh` is unauthenticated until you opt into one of the trade-offs documented below.

| Host path | Mounted at | Purpose |
| --- | --- | --- |
| `~/.ssh/id_ed25519.pub` | `/home/vscode/.ssh/id_ed25519.pub` (read-only) | Public half of your SSH commit-signing key |
| `~/.config/git/allowed_signers` | `/home/vscode/.config/git/allowed_signers` (read-only) | Git config allowed signers |
| `~/.config/gh` | `/home/vscode/.config/gh` | GitHub CLI config and auth tokens - bind-mounted read-write so `gh auth login` / token refresh inside the container persists back to the host |

**All three paths must exist on the host before you reopen the folder in the devcontainer, otherwise the container build will fail with a bind-mount error.**

If you do not sign commits or use `gh` and don't want to set this up, delete the `"mounts"` block from [`.devcontainer.json`](.devcontainer.json) locally before opening, or simply don't use the devcontainer.

`.devcontainer.json` also runs an `onCreateCommand` that fixes `~/.ssh` ownership inside the container (Docker creates the bind-mount parent dir as `root:root 755`, which prevents writing `known_hosts`). `onCreateCommand` only runs at container *creation*, so contributors with an already-built container who pull a branch that introduces or changes that command must rebuild the container (VS Code typically prompts) or run the equivalent `chown`/`chmod` manually. Fresh-checkout contributors are unaffected.

The host-side setup below covers Linux, WSL, and macOS as a single common set of instructions plus a small per-OS deltas section. WSL hosts have a one-time prerequisite for Docker Desktop integration; enabling systemd is recommended but not strictly required - the Linux/WSL Deltas section documents a `~/.bashrc` fallback for shells where `systemctl --user` isn't available.

#### WSL Host Prep

Apply this configuration if you are running Linux distros from WSL on Windows.

Enable `Use the WSL 2 based engine` in Docker Desktop under Settings / General.\
Enable `Enable integration with my default WSL distro` and `Enable integration with additional distros` in Docker Desktop under Settings / Resources / WSL integration.

Recommended (but not strictly required - see the Linux/WSL Deltas `~/.bashrc` fallback below if you prefer not to enable systemd): edit `/etc/wsl.conf` and enable `systemd`, run from a WSL distro terminal:

```ini
[boot]
systemd = true
```

Then restart WSL from a Windows PowerShell terminal:

```shell
wsl --shutdown
```

#### Host Setup

Run on the host that will run the devcontainer.

```shell
# Configure git identity
git config --global user.name "[Your Name]"
git config --global user.email "[Your Email]"

# Create ~/.ssh/config file
mkdir -p ~/.ssh && chmod 700 ~/.ssh
touch ~/.ssh/config && chmod 600 ~/.ssh/config

# Generate a SSH signing key pair
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519

# Create allowed_signers file
SIGNER_LINE="$(git config --get user.email) namespaces=\"git\" $(cat ~/.ssh/id_ed25519.pub)"
mkdir -p ~/.config/git
touch ~/.config/git/allowed_signers
grep -qxF "$SIGNER_LINE" ~/.config/git/allowed_signers || echo "$SIGNER_LINE" >> ~/.config/git/allowed_signers

# Use SSH for git signing
git config --global gpg.format ssh
git config --global user.signingkey '~/.ssh/id_ed25519.pub'
git config --global gpg.ssh.allowedSignersFile '~/.config/git/allowed_signers'
git config --global commit.gpgsign true

# Login to GitHub
gh auth login

# Register SSH key with GitHub
gh auth refresh -h github.com -s admin:public_key,admin:ssh_signing_key
gh ssh-key add ~/.ssh/id_ed25519.pub --title "$(hostname) auth"
gh ssh-key add ~/.ssh/id_ed25519.pub --title "$(hostname) signing" --type signing
```

Edit `~/.ssh/config` so the agent caches the key on first use:

```ini
Host *
    AddKeysToAgent yes
    IdentityFile ~/.ssh/id_ed25519
```

##### Linux/WSL Deltas

Enable the user-level `ssh-agent` service so it's available across shells:

```shell
systemctl --user enable --now ssh-agent.socket
```

If `systemctl --user` isn't available in your shell (some minimal WSL distros), add this fallback to `~/.bashrc`:

```shell
# Reuse a shared ssh-agent if systemd's isn't available in this shell
SSH_AGENT_ENV="$HOME/.ssh/agent.env"
if [ -z "$SSH_AUTH_SOCK" ]; then
    if [ -r "$SSH_AGENT_ENV" ]; then
        . "$SSH_AGENT_ENV" >/dev/null
    fi
    if ! ssh-add -l >/dev/null 2>&1; then
        ssh-agent -s > "$SSH_AGENT_ENV"
        chmod 600 "$SSH_AGENT_ENV"
        . "$SSH_AGENT_ENV" >/dev/null
        ssh-add ~/.ssh/id_ed25519 >/dev/null 2>&1
    fi
fi
```

##### macOS Deltas

macOS uses launchd (not systemd) for `ssh-agent` and integrates SSH with the system Keychain. The `systemctl` line and the `~/.bashrc` agent fallback do not apply, and the SSH steps differ.

Use this `~/.ssh/config` instead of the common one - `UseKeychain yes` caches the passphrase in Keychain:

```ini
Host *
    AddKeysToAgent yes
    UseKeychain yes
    IdentityFile ~/.ssh/id_ed25519
```

Load the key into the agent once so the passphrase persists across reboots:

```shell
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

##### `gh` Credential-Store Hosts

`gh auth login` uses a credential store by default when one is available - Keychain on macOS, libsecret/Secret Service on Linux desktops with the relevant daemon running. `--insecure-storage` is the opt-out that forces file storage. When the credential store is used, the token never lands in `~/.config/gh/hosts.yml`, and the devcontainer bind-mount therefore carries no `oauth_token`. (On Linux servers, WSL distros without a desktop session, and any host where you ran `gh auth login --insecure-storage`, the token IS in `hosts.yml` and container `gh` is pre-authenticated - skip this section.)

If your host's `gh` is in a credential store, container `gh` is unauthenticated until you pick one of these trade-offs:

- **Skip container `gh` entirely.** Run all `gh` invocations from the host (where the token stays in the credential store). Inside the container, `gh` will fail until you authenticate it. Pick this if you want the host's GitHub token to live only in the credential store.
- **Authenticate `gh` once inside the devcontainer.** No credential store in the container, so `gh auth login` writes the token to `~/.config/gh/hosts.yml` - the bind-mount target - meaning the token now also exists on your host as a plaintext bearer token (mode 600). This is materially weaker than the credential-store entry: anyone or anything with read access to that file gets immediate GitHub auth, with no passphrase or unlock step. Your credential-store token is unchanged, and the host's `gh` will still prefer the credential-store one.

```shell
# Inside the devcontainer (one-time, only if you chose the second option).
# Default scopes cover PR/issue work - `gh pr view`, `gh issue view`,
# `gh api repos/.../pulls/N/comments`, `gh run list`, etc.
gh auth login

# Optional: only if you also want to manage SSH keys with `gh ssh-key add`
# from the container, extend the token's scopes (note: `gh auth refresh`,
# not `gh auth login -s`, which would re-do the whole login flow).
# Most contributors don't need this; default scopes are fine.
gh auth refresh -h github.com -s admin:public_key,admin:ssh_signing_key
```

#### Verify Host Setup

Open a new terminal and verify configuration:

```shell
# Test paths
ls -la ~/.ssh
ls -la ~/.config/git
ls -la ~/.config/gh

# Show git config
git config --list --show-origin

# Test github SSH login
gh ssh-key list
ssh -T git@github.com

# SSH socket and key should be available via the agent
echo $SSH_AUTH_SOCK
ssh-add -l

# Confirm an ssh-agent process is running (any platform / any setup path)
ps aux | grep ssh-agent | grep -v grep

# Linux/WSL only, and only if you used the systemd path (skip if you used
# the ~/.bashrc fallback - that path doesn't register a systemd service):
systemctl --user status ssh-agent.socket
```

On credential-store hosts that haven't been authenticated inside the container yet, container `gh` will be unauthenticated - that's expected at this point. The in-container verify section below covers the post-container-auth check.

#### Open in Devcontainer

Connect to the host from VS Code, direct, over SSH, or over WSL, and clone the repo to the local filesystem.\
Open the directory, and then open the workspace in a devcontainer, **do not clone into a volume** as `${localEnv:HOME}` will not resolve and the container will fail to open.

Open a terminal in VS Code from the devcontainer, and test the configuration:

```shell
# Test paths
ls -la ~/.ssh
ls -la ~/.config/git
ls -la ~/.config/gh

# Show git config
git config --list --show-origin

# SSH socket and keys should be available via ssh-agent
echo $SSH_AUTH_SOCK
ssh-add -l

# Test GitHub SSH connectivity (does not need `gh`)
ssh -T git@github.com

# Test gh - only if container `gh` is authenticated. It is when the
# host stored the token in `~/.config/gh/hosts.yml` (Linux servers,
# minimal WSL, or any host where you ran `gh auth login
# --insecure-storage`); it isn't when the host's `gh` is using a
# credential store (Keychain on macOS, libsecret/Secret Service on
# Linux desktops - both the default when the store is available)
# unless you ran `gh auth login` once inside the container. Skip in
# the unauthenticated case - `gh auth status` will fail by design.
# `gh auth status` works with default scopes; `gh ssh-key list`
# requires the `admin:public_key` scope, only granted when you extend
# the token via `gh auth refresh -h github.com -s admin:public_key,admin:ssh_signing_key`.
gh auth status
```

[aiopurpleair-repo-link]: https://github.com/ptr727/aiopurpleair
[uv-link]: https://github.com/astral-sh/uv
