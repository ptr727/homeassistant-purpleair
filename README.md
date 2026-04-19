# PurpleAir for Home Assistant (HACS)

A standalone Home Assistant custom integration for [PurpleAir](https://www.purpleair.com/) air-quality sensors, packaged for installation via [HACS](https://hacs.xyz/).

This repository ships the changes from upstream PR [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) — by the same author ([@ptr727](https://github.com/ptr727)) — without waiting for that PR to merge into Home Assistant core.

## What's different from Home Assistant's built-in PurpleAir integration

- **Private sensor support.** Each subentry can use its own per-sensor **Read Key**, allowing the integration to query private unlisted sensors, and to query self owned sensors at no cost.
- **Config subentries.** Follows the current HA model of one subentry per sensor, instead of a single config entry holding a list of sensor indices.
- **Sensor selection from a map.** Selection of a sensor from a map showing nearby public sensors.
- **Automatic v1 → v2 migration.** If you already use the built-in PurpleAir integration, this custom version shadows it on the `purpleair` domain and migrates your existing entries to the subentry layout on first load. Entity IDs, devices, and history are preserved.

Once #140901 merges upstream, the built-in integration will be functionally equivalent and this custom component will no longer be needed.

## Why private sensor support matters

PurpleAir's API uses a points/credits model. A new account starts with ~1,000,000 free points; the integration consumes roughly 30,000 points/day, so a fresh account lasts about a month before you must buy more points or the API stops returning data.

**Sensor owners can access data for their own sensors free of charge** — see [PurpleAir community: API points for sensor owners](https://community.purpleair.com/t/api-points-for-sensor-owners/7525). The Read Key (delivered via email when you registered the sensor) is what unlocks this. Adding your own sensors via private Read Key allows you to run this integration long-term at no cost.

## Installation

### Via HACS (recommended)

1. In HACS, open **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/ptr727/homeassistant-purpleair` with category **Integration**.
3. Install **PurpleAir** from the HACS list and restart Home Assistant.

### Manual

Copy `custom_components/purpleair/` into your Home Assistant `<config>/custom_components/` directory and restart Home Assistant.

## Configuration

### 1. Get a PurpleAir API key

- Create a free account at the [PurpleAir Developer Portal](https://develop.purpleair.com/).
- On the [API Keys page](https://develop.purpleair.com/dashboards/keys) create an API key.
- On the [Projects page](https://develop.purpleair.com/dashboards/projects) buy points as required (not required for using your own sensors).
- Return to the keys page and copy the API key (it looks like a GUID).

### 2. Add the integration in Home Assistant

**Settings → Devices & Services → Add Integration → PurpleAir** and paste your API key.

### 3. Add sensors

Each sensor is added as a **subentry** under the integration. Two methods:

- **Map search.** Pick from public sensors near a latitude/longitude/radius.
- **Manual entry.** Enter the sensor **Index** plus optional **Read Key**.
  - The Read Key is **required for private sensors** that are not shown on the public sensor map.
  - The Read Key is **required for no cost API uage** of your own sensors (the Read Key is sent via email during sensor registration). Refer to [PurpleAir community: API points for sensor owners](https://community.purpleair.com/t/api-points-for-sensor-owners/7525).

## Migration from the built-in integration

On first load this integration will detect any existing v1 PurpleAir config entries (the layout used by HA's built-in integration), convert them to the subentry layout, and rehome existing devices/entities to the new subentries. No manual reconfiguration is needed.

## Status & disclaimer

- **Branch:** `develop` for testing, releases will be cut from `main`.
- **Upstream PR:** [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901).
- **Upstream docs PR:** [home-assistant/home-assistant.io#38063](https://github.com/home-assistant/home-assistant.io/pull/38063).
- **API library:** [aiopurpleair](https://pypi.org/project/aiopurpleair/), authored by [@bachya](https://github.com/bachya).
- **License:** Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
- **Credits:** Original PurpleAir integration author and code owner [@bachya](https://github.com/bachya); subentry redesign reviewed and supported by [@joostlek](https://github.com/joostlek).

This is an unofficial fork. Bug reports and feature requests welcome on the [issue tracker](https://github.com/ptr727/homeassistant-purpleair/issues); upstream functional issues should also be reported to the PR thread so the change benefits all Home Assistant users.

## Development

The repo includes a VS Code devcontainer and helper scripts:

```sh
scripts/setup     # install dev requirements
scripts/develop   # boot Home Assistant against ./config with this integration loaded
scripts/lint      # ruff format + ruff check --fix
pytest            # run the test suite (after pip install -r requirements-test.txt)
```

Each script is also wired up as a VS Code task in [.vscode/tasks.json](.vscode/tasks.json) — open **Command Palette → Tasks: Run Task**, or use the shortcuts below:

| Script          | VS Code task                      | Shortcut                               |
| --------------- | --------------------------------- | -------------------------------------- |
| `scripts/setup` | **Setup: Install dev requirements** | Tasks: Run Task                        |
| `scripts/develop` | **Develop: Run Home Assistant**   | Tasks: Run Task                        |
| `scripts/lint`  | **Lint: ruff format + check --fix** | `Ctrl+Shift+B` (default build task)    |
| `pytest`        | **Test: pytest**                  | Tasks: Run Test Task (default test)    |
