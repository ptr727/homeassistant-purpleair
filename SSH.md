# SSH Agent Configuration

## Configure persistent SSH agent (Proxmox / Debian / Ubuntu)

Sets up a single, systemd-managed `ssh-agent` per user session, available to all
shells automatically. Works identically on Proxmox hosts and WSL distros (Debian,
Ubuntu).

### 1. Enable systemd in WSL (skip on Proxmox / native Linux)

In each WSL distro, ensure `/etc/wsl.conf` enables systemd:

```shell
sudo tee -a /etc/wsl.conf > /dev/null <<'EOF'
[boot]
systemd=true
EOF
```

If `/etc/wsl.conf` already has a `[boot]` section, edit it manually instead to
avoid duplicate sections.

From a **Windows PowerShell** prompt, shut down all WSL distros so the change
takes effect:

```powershell
wsl --shutdown
```

Reopen the distro and confirm systemd is PID 1:

```shell
ps -p 1 -o comm=
# should print: systemd
```

### 2. Enable the user-level ssh-agent service

```shell
systemctl --user enable --now ssh-agent.socket
```

Verify:

```shell
systemctl --user status ssh-agent.socket
echo $SSH_AUTH_SOCK
# should print: /run/user/<uid>/openssh_agent
```

### 3. Tell SSH to use the systemd socket and auto-add keys

Add to `~/.ssh/config` (create the file if it doesn't exist, mode `600`):

```shell
mkdir -p ~/.ssh && chmod 700 ~/.ssh
touch ~/.ssh/config && chmod 600 ~/.ssh/config
```

Append:

```ssh-config
Host *
    AddKeysToAgent yes
    IdentityFile ~/.ssh/id_ed25519
```

`AddKeysToAgent yes` causes the first SSH operation in a session to load the key
(prompting for the passphrase if any) and cache it for the agent's lifetime.

### 4. Defensive `.bashrc` snippet (safety net)

Add to `~/.bashrc`. Harmless when systemd is managing the agent; useful as a
fallback in shells that don't inherit `SSH_AUTH_SOCK`.

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

Reload:

```shell
source ~/.bashrc
```

### 5. Verify

Open a fresh shell and confirm:

```shell
ps aux | grep ssh-agent | grep -v grep
# should show exactly one ssh-agent process per user

echo $SSH_AUTH_SOCK
ssh-add -l
# lists your loaded key(s)
```

If you previously had agent sprawl, kill the orphans first:

```shell
pkill ssh-agent
```

Then close all shells, open a fresh one, and re-verify.
