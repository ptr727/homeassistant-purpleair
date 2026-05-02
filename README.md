# PurpleAir Integration for Home Assistant

A Home Assistant [custom integration][ha-custom-integration-link] for [PurpleAir][purpleair-link] air-quality sensors.

> **Not the built-in PurpleAir integration.** This custom integration shares the `purpleair` domain with the core built-in one. When loaded, Home Assistant's loader picks the custom version over the built-in and migrates existing config entries forward — the upgrade is automatic and preserves entity IDs and history. **The downgrade is not:** if you later remove this custom integration, the built-in cannot read the migrated v2 entries. See [Migration][migration-link] below for details. In the **Add Integration** picker this appears as **"PurpleAir (custom)"** to distinguish it from the built-in **"PurpleAir"**.

## Build and Distribution

### Build Status

[![Build Status][buildstatus-shield]][actions-link]\
[![Last Build][lastbuild-shield]][actions-link]\
[![Last Commit][lastcommit-shield]][commits-link]\
[![Coverage][coverage-shield]][coverage-link]

### Releases

[![Release Version][releaseversion-shield]][releases-link]\
[![Pre-Release Version][prereleaseversion-shield]][releases-link]\
[![HACS Default][hacs-shield]][hacs-link]\
[![Quality Scale][qualityscale-shield]][qualityscale-link]\
[![Home Assistant][haversion-shield]][haversion-link]\
[![License][license-shield]][license-link]

### Release Notes

Release highlights — see [Release History](./HISTORY.md) for details.

**Version 0.1**:

- Private sensor support via per-sensor read keys (free API points when querying your own sensors).
- Subentry layout — one subentry per sensor; automatic v1 → v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
- Cost-aware field selection — only fields backing enabled entities are requested, and static device-info fields are fetched once per day.
- Quality-aware availability — entities go unavailable on `confidence < 50`, `channel_state == 0` ("No PM"), or a stale `last_seen`.
- Account-level **Remaining points** and **Consumption rate** diagnostic sensors (disabled by default), backed by a daily refresh of `GET /v1/organization`. A persistent repair issue fires when the balance drops below seven days of consumption or the API rejects requests with `PaymentRequiredError`.
- Sensor selection from a map — pick nearby public sensors from a radius-filtered map picker.
- Disabled-by-default derived entities: PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
- Disabled-by-default diagnostic entities: Confidence, Channel state, Channel flags, Last seen, Internal temperature/humidity/pressure, PM2.5 ALT, PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
- Platinum-tier quality-scale compliance.

See [GitHub Releases][releases-link] for per-release changes.\
See [Release History](./HISTORY.md) for historic changes.

## Features

**Features beyond Home Assistant's built-in PurpleAir integration**:

- **Private sensor support.** Each subentry can supply its own per-sensor **Read Key**, so the integration can query unlisted private sensors and query self-owned sensors at no API-point cost.
- **Config subentries.** One subentry per sensor (the current HA model) instead of a single config entry holding a list of sensor indices.
- **Sensor selection from a map.** Pick nearby public sensors from a radius-filtered map picker.
- **Cost-aware field selection.** Only fields for *enabled* entities are requested, and static device-info fields are fetched once per day instead of every refresh — see [API points and field selection](#api-points-and-field-selection).
- **Quality-aware availability.** Entities are marked unavailable when the sensor's `confidence` drops below 50 %, when the two Plantower channels disagree (`channel_state == 0`), or when the sensor has stopped reporting (`last_seen` older than 10 min).
- **Remaining-points diagnostics.** Account-level **Remaining points** and **Consumption rate** sensors (disabled by default) plus a persistent repair issue when fewer than seven days of points remain or the API rejects requests with `PaymentRequiredError`.
- **Platinum-tier quality scale.** Full [HA quality-scale][qualityscale-rules-link] platinum tier: `parallel-updates`, `entity-unavailable`, `log-when-unavailable`, `repair-issues`, `reconfiguration-flow`, entity translations, exception translations, ≥ 95 % test coverage, and more — see [`quality_scale.yaml`](custom_components/purpleair/quality_scale.yaml).
- **Automatic v1 → v2 migration.** Existing config entries from the built-in integration are converted to the subentry layout on first load; entity IDs, devices, and history are preserved.

**Why private sensor support matters**:

**PurpleAir uses a points for data access model**, see [PurpleAir Community: API Pricing][purpleair-api-pricing-link] for details. New accounts start with enough points to run for about a month using this integration, before more points may need to be purchased.

**Sensor owners can access data for their own sensors free of charge**, see [PurpleAir community: API points for sensor owners][free-points-link]. To run this integration long-term at no cost for your own sensors, use the **Read Key** that was provided via email during sensor registration.

## Installation

### Via HACS (Recommended)

1. In HACS, open **Integrations → ⋮ → Custom repositories**.
1. Add `https://github.com/ptr727/homeassistant-purpleair` with category **Integration**.
1. Install **PurpleAir** from the HACS list and restart Home Assistant.

### Manual

Copy `custom_components/purpleair/` into your Home Assistant `<config>/custom_components/` directory and restart Home Assistant.

## Configuration

### 1. Get a PurpleAir API Key

- Create a free account at the [PurpleAir Developer Portal][purpleair-developer-link].
- On the [API Keys page][purpleair-keys-link] create an API key.
- On the [Projects page][purpleair-projects-link] buy points as required (not required for using your own sensors).
- Return to the keys page and copy the API key (it looks like a GUID).

### 2. Add the Integration in Home Assistant

**Settings → Devices & Services → Add Integration → PurpleAir** and paste your API key.

### 3. Add Sensors

Each sensor is added as a **subentry** under the integration. Two methods:

- **Map search.** Pick from public sensors near a latitude/longitude/radius.
- **Manual entry.** Enter the sensor **Index** plus optional **Read Key**.
  - The Read Key is **required for private sensors** that are not shown on the public sensor map.
  - The Read Key is **required for no cost API usage** of your own sensors (the Read Key is sent via email during sensor registration). Refer to [PurpleAir community: API points for sensor owners][free-points-link].

## Sensor Behavior and Calibration

These notes explain why entities report the values they do. The integration takes two different approaches depending on how settled the underlying math is:

- **Widely-adopted, well-specified corrections are implemented in code** as disabled-by-default opt-in entities — specifically the US EPA PM2.5 humidity correction and the US EPA PM2.5 AQI. The formulas are cited below with their source documents.
- **Local, deployment-specific calibrations** (ambient temperature/humidity offsets, per-channel corrections, alternative AQI schemas) remain user-territory — the integration exposes the raw fields and the README shows template-sensor examples for the common cases.

All field semantics below are verified against the [official API documentation][purpleair-api-link].

### PM2.5 Mass Concentration

The `PM2.5 mass concentration` sensor returns the API's `pm2.5` field. On the real-time endpoint this field is **already**:

- indoor-vs-outdoor aware — it uses the CF=1 variant on sensors registered as indoor and the ATM variant on outdoor sensors;
- downgrade-aware — if one of the two Plantower channels is flagged as degraded, its reading is excluded from the average automatically.

See the [API docs § `pm2.5`][purpleair-api-pm25-link] for the full spec. You do not need to pick between ATM and CF=1 manually.

For the Wallace **ALT-CF3** variant (often preferred for wildfire smoke and low-concentration outdoor monitoring) enable the disabled-by-default **PM2.5 ALT mass concentration** sensor. See [the API docs § `pm2.5_alt`][purpleair-api-pm25-link] for the formula.

For US EPA-corrected PM2.5, enable the opt-in **PM2.5 EPA mass concentration** entity — see [EPA-corrected PM2.5](#epa-corrected-pm25-pm25-epa-mass-concentration) below for the formula and source.

### Rolling Averages

The disabled-by-default **PM2.5 10/30/60-minute**, **6/24-hour**, and **1-week average** sensors expose the API's running-average fields. These are the preferred input for AQI-style reporting (e.g. the US EPA AQI is defined against a 24-hour average). Same indoor/outdoor auto-selection applies.

### Internal Temperature and Humidity

The `temperature` and `humidity` entities expose readings from **inside the sensor housing**, not ambient conditions. Per the API docs:

> *This matches the "Operating Temperature" map layer and is not representative of ambient conditions. Formulas can be applied to estimate ambient temperature.*

In practice, a PA-II reads roughly **8 °F hotter** and **4 %RH drier** than the ambient air around it. No correction is applied to the entity values — they are the raw sensor readings.

If you need an ambient estimate, use a template sensor. Example:

```yaml
template:
  - sensor:
      - name: "Backyard ambient temperature"
        device_class: temperature
        unit_of_measurement: "°F"
        # Rule of thumb: PA-II reads ~8 °F hotter than ambient.
        # See the PurpleAir community for more precise formulas.
        state: >-
          {% set t = states('sensor.backyard_temperature') | float(none) %}
          {{ (t - 8) if t is number else none }}
      - name: "Backyard ambient humidity"
        device_class: humidity
        unit_of_measurement: "%"
        # Rule of thumb: PA-II reads ~4 %RH below ambient; cap at 100.
        state: >-
          {% set h = states('sensor.backyard_humidity') | float(none) %}
          {{ [h + 4, 100] | min if h is number else none }}
```

The raw internal readings are also available via the disabled-by-default **Internal temperature**, **Internal humidity**, and **Internal pressure** diagnostic entities.

### EPA-Corrected PM2.5 (`PM2.5 EPA Mass Concentration`)

A disabled-by-default sensor that applies the US EPA's published correction to the raw PurpleAir PM2.5 output. Reference: **"Fire and Smoke Map Sensor Data Processing"**, EPA Office of Research and Development, revised 2021, page 26 of [`dirEntryId=353088`][epa-pm25-link].

Implementation details:

- Inputs: the PurpleAir `pm2.5` field (ATM variant auto-selected for outdoor sensors) and raw `humidity`. Both are requested automatically when this sensor is enabled — you do not need to also enable the baseline PM2.5 and humidity entities.
- Uses a piecewise formula with five regions (PM < 30, 30 ≤ PM < 50, 50 ≤ PM \< 210, 210 ≤ PM < 260, PM ≥ 260) with linear blending across the two transition regions so the output is continuous at every breakpoint.
- Uses the sensor's **internal** housing humidity as input, matching how the EPA regression was fit — no ambient correction is applied to humidity here.
- Calibrated for outdoor sensors; enabling it on an indoor sensor is not meaningful.

The code lives in `_pm25_epa_correction` in [`sensor.py`](custom_components/purpleair/sensor.py). The implementation has unit tests that verify each region's formula and the continuity of every boundary.

### US AQI from 24-Hour PM2.5 (`PM2.5 Air Quality Index`)

A disabled-by-default sensor that reports the US EPA Air Quality Index for PM2.5 based on the sensor's 24-hour rolling average.

- Input: the PurpleAir `pm2.5_24hour` field (auto-selected for indoor/outdoor and excluding downgraded channels).
- Uses the breakpoint table from [AirNow — Air Quality Index (AQI) Basics][airnow-aqi-link], updated to the **2024 NAAQS revision** (Good/Moderate threshold lowered from 12.0 → 9.0 µg/m³, higher bands tightened).
- Concentrations are truncated to 0.1 µg/m³ before lookup (40 CFR § 58 App. G), AQI within each band is linearly interpolated, and values above 500.4 µg/m³ cap at AQI 500.

The breakpoint table and lookup live in `_pm25_aqi` in [`sensor.py`](custom_components/purpleair/sensor.py); unit tests cover every band edge.

### Availability Signals

Entities become **unavailable** when any of:

- the sensor's `confidence` score is below 50 % (the two PMS channels disagree too much to trust the average);
- `channel_state` reports **No PM** (no PM sensor detected at all);
- `last_seen` is more than 10 minutes behind the coordinator's `data_timestamp_utc` (the sensor has stopped reporting).

Each transition is logged once at `INFO` under the `custom_components.purpleair` logger.

### API Points and Field Selection

PurpleAir charges API points per **field** per sensor per call. The integration takes two steps to minimize that cost:

**1. Only fetch fields for enabled entities.** Each [`PurpleAirSensorEntityDescription`](custom_components/purpleair/sensor.py) declares its required API fields; at refresh time the coordinator walks the entity registry for the config entry and unions the `api_fields` of every enabled description. Disabled entities contribute zero API fields to the outgoing request. Enabling or disabling an entity in the UI triggers an immediate refresh so the field set reflects reality on the next cycle.

**2. Static fields are cached for 24 hours.** The API's field catalog mixes values that change every reading (PM2.5, humidity, `confidence`, `last_seen`) with values that only change on firmware updates or user actions (`name`, `hardware`, `model`, `firmware_version`, `latitude`, `longitude`). The coordinator splits them into two sets:

| Set | Fields | Fetch cadence |
| --- | --- | --- |
| `STATIC_DEVICE_FIELDS` | `name`, `hardware`, `model`, `firmware_version`, `latitude`, `longitude` | Once at setup, then every 24 h |
| `AVAILABILITY_FIELDS` | `last_seen`, `confidence`, `channel_state`, `channel_flags` | Every refresh (5 min) |
| Per-entity fields | e.g. `temperature`, `humidity`, `pm2.5`, `pm2.5_24hour` | Every refresh, only for enabled entities |

Reloading the config entry (**Settings → Devices & services → PurpleAir → ⋮ → Reload**) forces an immediate static re-fetch — useful after a firmware update or sensor relocation.

**Measured cost** for a default install of **one sensor with the six enabled-by-default entities** (temperature, humidity, pressure, PM1.0/PM2.5/PM10 mass concentrations). Both rows query the same 16 fields (4 availability + 6 default-enabled entity fields + 6 static device fields); the difference is whether the static fields ride along on every refresh or only once per day:

| Scenario | Fields per refresh | Refreshes per day | Field-fetches per day |
| --- | --- | --- | --- |
| Same fields, refetched every cycle (naive) | 16 | 288 | **4,608** |
| This integration (static fields cached 24 h) | 10 + 6 once daily | 288 + 1 | **2,886** (≈ 37 % less) |

The savings here come from the static-cache split alone. A second saving comes from **not** fetching fields for disabled entities: the integration declares 32 unique fields across all entities, but a default install only fetches 16 of them. Enabling every optional entity (PM particle counts, RSSI, uptime, ALT, six rolling averages, diagnostics) raises the per-refresh set to 26 fields; disabling a sensor you aren't using immediately drops its fields out of the next refresh.

Free points are available for sensor owners who use their own sensor's Read Key; see [API points for sensor owners][free-points-link].

## Upstream PRs

### Upstream `aiopurpleair` PR

This integration depends on the `aiopurpleair` library. The latest canonical release (`aiopurpleair==2025.08.1`) covers only the sensors endpoints and maps three error codes to exceptions, which means several of the [API's documented error codes][purpleair-api-link] collapse to a generic `PurpleAirError`, and there is no `GET /v1/organization` endpoint for tracking remaining API points.

The integration's typed error handling, organization coordinator, and low-points repair issue all depend on additions that aren't in the canonical library yet. While upstream review is pending, [`manifest.json`](custom_components/purpleair/manifest.json) pins to a temporary fork distribution published to PyPI as `aiopurpleair-ptr727==2026.4.0` (built from the [organization-endpoint-and-error-codes fork branch][aiopurpleair-fork-link]). The fork adds:

- 19 new exception subclasses (one per documented API error code), wired into `ERROR_CODE_MAP` so callers can `except InvalidDataReadKeyError`, `except PaymentRequiredError`, etc. instead of pattern-matching on `str(err)`.
- A `GET /v1/organization` endpoint exposed on `API` as `api.organizations`, with a `GetOrganizationResponse` Pydantic model carrying `remaining_points`, `consumption_rate`, `organization_id`, `organization_name`, `api_version`, and `timestamp_utc`.
- 100 % test coverage for both additions, no breaking changes to the public API.

The fork is shipped under a distinct PyPI name (`aiopurpleair-ptr727`) so it doesn't collide with the canonical `aiopurpleair` distribution; `packages = [{ include = "aiopurpleair" }]` in the fork's `pyproject.toml` keeps the import path unchanged, so `import aiopurpleair` continues to resolve. Hassfest rejects PEP 508 git-URL requirements ("contains a space"), which is why a published artifact is needed rather than a `git+...@SHA` pin.

A pull request against [bachya/aiopurpleair][bachya-aiopurpleair-link] is open. Once the maintainer merges and cuts a new canonical PyPI release, the pin in [`manifest.json`](custom_components/purpleair/manifest.json) and [`requirements-test.txt`](requirements-test.txt) flips back to `aiopurpleair==X.Y.Z`, the `aiopurpleair-ptr727` distribution gets yanked from PyPI, and this section can be removed.

All error codes and semantics in the fork are verified against the [official PurpleAir API documentation][purpleair-api-link].

### Upstream Home Assistant PR

An earlier version of this integration was submitted for inclusion in Home Assistant core as [home-assistant/core#140901][ha-core-pr-link] (with accompanying docs at [home-assistant/home-assistant.io#38063][ha-docs-pr-link]). That PR has been pending review for some time.

In the meantime, this version has continued to move forward — it now **supersedes** the PR in functionality.

The original core PR will not be kept in lockstep with these changes, and may be abandoned. The HACS release stream may be the maintained path going forward.

## Migration from the Built-in Integration

### Upgrade: Built-in → Custom

1. Install this custom integration via [HACS][hacs-xyz-link] or by copying `custom_components/purpleair/` into your Home Assistant config directory.
1. Restart Home Assistant. The installation has no effect until HA restarts — integrations are loaded once at startup.
1. On startup, HA's loader prefers the custom integration over the built-in one (they share the `purpleair` domain). Your existing PurpleAir config entry stays in place in `.storage/core.config_entries` and is migrated to the subentry layout. Entity IDs, devices, and long-term statistics are preserved. **You do not need to remove the built-in integration first — it is part of core, not a separate installation.**
1. You will see this warning in the log:

    ```text
    We found a custom integration purpleair which has not been tested by Home Assistant
    ```

    HA emits it for every custom integration and it is not a problem.

If migration fails, the entry is marked `SETUP_ERROR`. Check **Settings → System → Repairs** and the log; empty v1 entries raise a targeted repair issue.

### Downgrade: Custom → Built-in

**Downgrading requires manual work.** This custom integration uses config-entry schema **version 2** (one subentry per sensor). The built-in integration in Home Assistant core is still on schema **version 1**. If you simply delete `custom_components/purpleair/` and restart, the built-in cannot read v2 entries and the integration will fail to set up with `Config entry for purpleair is from a future version`.

Two recovery options:

- **Wait for the built-in integration to support schema v2.** Once the built-in adopts the same subentry layout, it can read existing v2 entries and the downgrade works automatically.
- **Rebuild the entry manually.** In Home Assistant go to **Settings → Devices & Services → PurpleAir → … → Delete**, then remove `custom_components/purpleair/`, restart, and re-add the built-in integration from scratch. Long-term-statistics history tied to the migrated entity IDs is lost.

There is no in-place downgrade until the built-in integration adopts schema v2. Plan accordingly before installing.

## Credits

- **API library:** [aiopurpleair][aiopurpleair-pypi-link], authored by [@bachya][bachya-link].
- **License:** Apache 2.0 — see [LICENSE](LICENSE).
- **Credits:** Original PurpleAir integration author [@bachya][bachya-link]; subentry redesign reviewed and supported by [@joostlek][joostlek-link].

## Issues and Discussions

Bug reports and feature requests are welcome on the [issue tracker][issues-link]. For questions, troubleshooting help, or ideas you're not sure are bugs, use [GitHub Discussions][discussions-link].

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow (branching, lint/test commands, PR guidelines) and [AGENTS.md](AGENTS.md) for the deeper contributor/agent reference (release flow, code style, devcontainer notes).

The repo includes a VS Code devcontainer and helper scripts:

```sh
scripts/setup     # install dev requirements
scripts/develop   # boot Home Assistant against ./config with this integration loaded
scripts/fix       # apply ruff auto-fixes (format + check --fix)
scripts/lint      # verify-only: ruff format --check + ruff check + mypy --strict (mirrors CI)
pytest            # run the test suite (after pip install -r requirements-test.txt)
```

`scripts/lint` is the CI gate — it fails non-zero on any ruff, format, or `mypy --strict` violation so "green locally" matches "green on GitHub". When it fails on an auto-fixable issue, run `scripts/fix` and re-run lint.

If you also run tests in the `aiopurpleair/` workspace folder, prefer a separate virtual environment for that repo. This integration targets Python 3.14, while aiopurpleair's Poetry lock may pin older C-extension builds that do not compile on 3.14 in all branches.

Recommended approach:

```sh
cd aiopurpleair
python3 -m venv .venv
. .venv/bin/activate
./script/setup
```

`scripts/setup` for this integration intentionally does not auto-run `aiopurpleair/script/setup`; it only ensures the minimal missing test dependency (`aresponses`) is installed in the current environment.

If you explicitly want to run the library's own setup from the integration bootstrap, opt in with:

```sh
RUN_AIOPURPLEAIR_SETUP=1 scripts/setup
```

Each script is also wired up as a VS Code task in [.vscode/tasks.json](.vscode/tasks.json) — open **Command Palette → Tasks: Run Task**, or use the shortcuts below:

| Script | VS Code task | Shortcut |
| --- | --- | --- |
| `scripts/setup` | **Setup: Install dev requirements** | Tasks: Run Task |
| `scripts/develop` | **Develop: Run Home Assistant** | Tasks: Run Task |
| `scripts/fix` | **Fix: ruff format + check --fix** | Tasks: Run Task |
| `scripts/lint` | **Lint: ruff + mypy (verify)** | `Ctrl+Shift+B` (default build task) |
| `pytest` | **Test: pytest** | Tasks: Run Test Task (default test) |

Additional useful tasks in the same file:

- **Test: pytest + branch coverage** — run CI-style branch coverage locally.
- **Setup: aiopurpleair venv** — create `aiopurpleair/.venv` and upgrade `pip`.
- **Setup: aiopurpleair deps (poetry)** — run `aiopurpleair/script/setup` inside that venv.
- **Test: aiopurpleair pytest (venv)** — run aiopurpleair tests inside that venv.

### Devcontainer Setup

The [`.devcontainer.json`](.devcontainer.json) bind-mounts host paths into the container so existing host credentials (SSH signing key, GitHub CLI auth) work inside it without re-setup:

| Host path | Mounted at | Purpose |
| --- | --- | --- |
| `~/.ssh/id_ed25519.pub` | `/home/vscode/.ssh/id_ed25519.pub` (read-only) | Public half of your SSH commit-signing key |
| `~/.config/git/allowed_signers` | `/home/vscode/.config/git/allowed_signers` (read-only) | Git config allowed signers |
| `~/.config/gh` | `/home/vscode/.config/gh` | GitHub CLI config and auth tokens — bind-mounted read-write so `gh auth login` / token refresh inside the container persists back to the host |

**All three paths must exist on the host before you reopen the folder in the devcontainer, otherwise the container build will fail with a bind-mount error.**

If you do not sign commits or use `gh` and don't want to set this up, delete the `"mounts"` block from [`.devcontainer.json`](.devcontainer.json) locally before opening, or simply don't use the devcontainer.

Configuration below applies to Debian or Ubuntu distros.

#### WSL Host Setup

Apply this configuration if you are running linux distros from WSL on Windows.

Enable `Use the WSL 2 based engine` in Docker Desktop under Settings / General.\
Enable `Enable integration with my default WSL distro` and `Enable integration with additional distros` in Docker Desktop under Settings / Resources / WSL integration.

Edit `/etc/wsl.conf` and enable `systemd`, run from a WSL distro terminal:

```ini
[boot]
systemd = true
```

Restart WSL if required, run from a Windows PowerShell terminal:

```shell
wsl --shutdown
```

#### Linux Host Setup

Apply this configuration from the linux docker host that will run the devcontainer.

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

# Enable the user-level ssh-agent service
systemctl --user enable --now ssh-agent.socket
```

Edit `~/.ssh/config` to add SSH keys to the agent:

```ini
Host *
    AddKeysToAgent yes
    IdentityFile ~/.ssh/id_ed25519
```

Edit `~/.bashrc` as fallback:

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

# SSH socket and keys should be available via ssh-agent
systemctl --user status ssh-agent.socket
echo $SSH_AUTH_SOCK
ssh-add -l

# Should show one ssh-agent process per user
ps aux | grep ssh-agent | grep -v grep
```

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

# Test github SSH login
gh ssh-key list
ssh -T git@github.com

# SSH socket and keys should be available via ssh-agent
echo $SSH_AUTH_SOCK
ssh-add -l
```

[actions-link]: https://github.com/ptr727/homeassistant-purpleair/actions
[aiopurpleair-fork-link]: https://github.com/ptr727/bachya-aiopurpleair/tree/feat/organization-endpoint-and-error-codes
[aiopurpleair-pypi-link]: https://pypi.org/project/aiopurpleair/
[airnow-aqi-link]: https://www.airnow.gov/aqi/aqi-basics/
[bachya-aiopurpleair-link]: https://github.com/bachya/aiopurpleair
[bachya-link]: https://github.com/bachya
[buildstatus-shield]: https://img.shields.io/github/actions/workflow/status/ptr727/homeassistant-purpleair/test-pull-request.yml?logo=github&label=Build%20Status
[commits-link]: https://github.com/ptr727/homeassistant-purpleair/commits/main
[coverage-link]: https://app.codecov.io/gh/ptr727/homeassistant-purpleair
[coverage-shield]: https://img.shields.io/codecov/c/github/ptr727/homeassistant-purpleair?logo=codecov&label=Coverage
[epa-pm25-link]: https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=353088&Lab=CEMM
[ha-core-pr-link]: https://github.com/home-assistant/core/pull/140901
[migration-link]: #migration-from-the-built-in-integration
[ha-custom-integration-link]: https://developers.home-assistant.io/docs/creating_integration_file_structure/
[ha-docs-pr-link]: https://github.com/home-assistant/home-assistant.io/pull/38063
[hacs-link]: https://github.com/hacs/integration
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistantcommunitystore&label=HACS
[hacs-xyz-link]: https://hacs.xyz/
[haversion-link]: https://www.home-assistant.io/blog/categories/release-notes/
[haversion-shield]: https://img.shields.io/badge/Home_Assistant-2026.4.0%2B-41BDF5?logo=homeassistant
[discussions-link]: https://github.com/ptr727/homeassistant-purpleair/discussions
[issues-link]: https://github.com/ptr727/homeassistant-purpleair/issues
[joostlek-link]: https://github.com/joostlek
[lastbuild-shield]: https://byob.yarr.is/ptr727/homeassistant-purpleair/lastbuild
[lastcommit-shield]: https://img.shields.io/github/last-commit/ptr727/homeassistant-purpleair?logo=github&label=Last%20Commit
[license-link]: ./LICENSE
[license-shield]: https://img.shields.io/github/license/ptr727/homeassistant-purpleair?label=License
[prereleaseversion-shield]: https://img.shields.io/github/v/release/ptr727/homeassistant-purpleair?include_prereleases&label=GitHub%20Pre-Release&logo=github&color=orange
[purpleair-api-link]: https://api.purpleair.com/
[purpleair-api-pm25-link]: https://api.purpleair.com/#api-sensors-get-sensor-data
[free-points-link]: https://community.purpleair.com/t/api-points-for-sensor-owners/7525
[purpleair-api-pricing-link]: https://community.purpleair.com/t/api-pricing/4523
[purpleair-developer-link]: https://develop.purpleair.com/
[purpleair-keys-link]: https://develop.purpleair.com/dashboards/keys
[purpleair-link]: https://www.purpleair.com/
[purpleair-projects-link]: https://develop.purpleair.com/dashboards/projects
[qualityscale-link]: ./custom_components/purpleair/quality_scale.yaml
[qualityscale-rules-link]: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/
[qualityscale-shield]: https://img.shields.io/badge/Quality_Scale-Platinum-9C27B0?logo=homeassistant
[releases-link]: https://github.com/ptr727/homeassistant-purpleair/releases
[releaseversion-shield]: https://img.shields.io/github/v/release/ptr727/homeassistant-purpleair?logo=github&label=GitHub%20Release
