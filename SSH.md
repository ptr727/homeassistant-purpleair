# SSH Agent Configuration

## 1. Enable systemd in WSL (skip on Proxmox / native Linux)

In each WSL distro, ensure `/etc/wsl.conf` enables systemd. This block is safe to
re-run — it only modifies the file if needed.

```shell
sudo python3 <<'EOF'
import configparser
import os

path = "/etc/wsl.conf"
cfg = configparser.ConfigParser()
cfg.optionxform = str  # preserve key case
if os.path.exists(path):
    cfg.read(path)

changed = False
if not cfg.has_section("boot"):
    cfg.add_section("boot")
    changed = True
if cfg.get("boot", "systemd", fallback=None) != "true":
    cfg.set("boot", "systemd", "true")
    changed = True

if changed:
    with open(path, "w") as f:
        cfg.write(f)
    print(f"Updated {path}")
else:
    print(f"{path} already configured")
EOF
```

Verify:

```shell
cat /etc/wsl.conf
```

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
