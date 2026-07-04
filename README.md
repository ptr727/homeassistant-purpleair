# PurpleAir Integration for Home Assistant

A Home Assistant custom integration for [PurpleAir][purpleair-link] air-quality sensors.

## Build and Distribution

### Build Status

[![Build Status][buildstatus-shield]][actions-link]\
[![Last Commit][lastcommit-shield]][commits-link]\
[![Coverage][coverage-shield]][coverage-link]\
[![HACS Custom][hacs-shield]][hacs-link]\
[![Quality Scale][qualityscale-shield]][qualityscale-link]\
[![Home Assistant][haversion-shield]][haversion-link]

### Releases

[![GitHub Release][releaseversion-shield]][releases-link]\
[![GitHub Pre-Release][prereleaseversion-shield]][releases-link]

### Release Notes

**Version 1.0**:

- Private sensor support via per-sensor read keys (free API points when querying your own sensors).
- Subentry layout - one subentry per sensor; automatic v1 -> v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
- Cost-aware field selection - only fields backing enabled entities are requested, and static device-info fields are fetched once per day.
- Quality-aware availability - entities go unavailable on `channel_state == 0` ("No PM"), a stale `last_seen`, or `confidence < 50` when both PM channels are reporting (single-channel sensors aren't gated on confidence because there's no second channel to cross-check).
- Account-level **Remaining points** and **Consumption rate** diagnostic sensors (both enabled by default), backed by a daily refresh of `GET /v1/organization`. A persistent repair issue fires when the balance drops below seven days of consumption or the API rejects requests with `PaymentRequiredError`.
- Sensor selection from a map - pick nearby public sensors from a radius-filtered map picker.
- Disabled-by-default derived entities: PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
- Enabled-by-default diagnostic entities: Confidence, Channel state, Last seen - these surface the values the availability gate uses, so a sensor marked Unavailable can be diagnosed at a glance from its device card. They cost zero extra API points (already fetched on every refresh).
- Disabled-by-default diagnostic entities: Channel flags, PM2.5 ALT, PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
- Platinum-tier quality-scale compliance.

See [Release History](./HISTORY.md) for complete release notes and older versions.

## Table of Contents

- [PurpleAir Integration for Home Assistant](#purpleair-integration-for-home-assistant)
  - [Build and Distribution](#build-and-distribution)
    - [Build Status](#build-status)
    - [Releases](#releases)
    - [Release Notes](#release-notes)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation](#installation)
    - [Via HACS (Recommended)](#via-hacs-recommended)
    - [Manual](#manual)
  - [Configuration](#configuration)
    - [1. Get a PurpleAir API Key](#1-get-a-purpleair-api-key)
    - [2. Add the Integration in Home Assistant](#2-add-the-integration-in-home-assistant)
    - [3. Add Sensors](#3-add-sensors)
    - [Account-Level Diagnostics](#account-level-diagnostics)
  - [Sensor Behavior and Calibration](#sensor-behavior-and-calibration)
    - [PM2.5 Mass Concentration](#pm25-mass-concentration)
    - [Rolling Averages](#rolling-averages)
    - [Internal Temperature and Humidity](#internal-temperature-and-humidity)
    - [EPA-Corrected PM2.5 (`PM2.5 EPA Mass Concentration`)](#epa-corrected-pm25-pm25-epa-mass-concentration)
    - [US AQI from 24-Hour PM2.5 (`PM2.5 Air Quality Index`)](#us-aqi-from-24-hour-pm25-pm25-air-quality-index)
    - [Availability Signals](#availability-signals)
    - [API Points and Field Selection](#api-points-and-field-selection)
  - [Migration from the Built-in Integration](#migration-from-the-built-in-integration)
    - [Upgrade: Built-in -\> Custom](#upgrade-built-in---custom)
    - [Switch an Existing Sensor to a Read Key](#switch-an-existing-sensor-to-a-read-key)
  - [Questions or Issues](#questions-or-issues)
  - [Contributing](#contributing)
  - [Credits](#credits)
  - [License](#license)

## Features

**Features beyond Home Assistant's built-in PurpleAir integration**:

- **Private sensor support.** Each subentry can supply its own per-sensor **Read Key**, so the integration can query unlisted private sensors and query self-owned sensors at no API-point cost.
- **Config subentries.** One subentry per sensor (the current HA model) instead of a single config entry holding a list of sensor indices.
- **Sensor selection from a map.** Pick nearby public sensors from a radius-filtered map picker.
- **Cost-aware field selection.** Only fields for *enabled* entities are requested, and static device-info fields are fetched once per day instead of every refresh - see [API points and field selection](#api-points-and-field-selection).
- **Quality-aware availability.** Entities are marked unavailable when the sensor reports no PM data (`channel_state == 0`, "No PM"), when it has stopped reporting (`last_seen` older than 10 min), or when both Plantower channels are reporting and disagree too much (`confidence < 50`). Single-channel sensors (PA-I or one channel downgraded) aren't gated on confidence because there's no second channel to cross-check against - on those sensors the displayed Confidence value reflects internal sensor-health checks rather than channel agreement, so values typically sit between 20 and 40 by design and that's not a defect. Confidence, channel state, and last-seen diagnostic entities are all enabled by default so the reason a sensor went unavailable is visible at a glance from the device card.
- **Hardware-aware entities.** The Volatile organic compounds (IAQ) entity is only created for devices whose `hardware` string indicates a BME680/688 gas sensor (PA-II-ZEN and newer). PA-I and original PA-II boards ship a BME280 with no gas-sensing capability, so the integration skips the entity entirely on those boards rather than registering one that would always sit at `unknown` (the API returns `voc: null`, which HA renders as Unknown for measurement entities). Existing installs that already have the entity registered keep it (the gate is bypassed for entities already present in the entity registry).
- **Remaining-points diagnostics.** Account-level **Remaining points** and **Consumption rate** sensors (both enabled by default) plus a persistent repair issue when fewer than seven days of points remain or the API rejects requests with `PaymentRequiredError`.
- **Platinum-tier quality scale.** Full [HA quality-scale][qualityscale-rules-link] platinum tier: `parallel-updates`, `entity-unavailable`, `log-when-unavailable`, `repair-issues`, `reconfiguration-flow`, entity translations, exception translations, >= 95 % test coverage, and more - see [`quality_scale.yaml`](custom_components/purpleair/quality_scale.yaml).
- **Automatic v1 -> v2 migration.** Existing config entries from the built-in integration are converted to the subentry layout on first load; entity IDs, devices, and history are preserved.

**Why private sensor support matters**:

**PurpleAir uses a points for data access model**, see [PurpleAir Community: API Pricing][purpleair-api-pricing-link] for details. New accounts start with enough points to run for about a month using this integration, before more points may need to be purchased.

**Sensor owners can access data for their own sensors free of charge**, see [PurpleAir community: API points for sensor owners][free-points-link]. To run this integration long-term at no cost for your own sensors, use the **Read Key** that was provided via email during sensor registration.

## Installation

> **Not the built-in PurpleAir integration.** This custom integration shares the `purpleair` domain with the core built-in one. When loaded, Home Assistant's loader picks the custom version over the built-in and migrates existing config entries forward - the upgrade is automatic and preserves entity IDs and history. See [Migration][migration-link] below for details. In the **Add Integration** picker this appears as **"PurpleAir (custom)"** to distinguish it from the built-in **"PurpleAir"**.

### Via HACS (Recommended)

1. In HACS, open **Integrations -> ⋮ -> Custom repositories**.
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

**Settings -> Devices & Services -> Add Integration -> PurpleAir** and paste your API key.

### 3. Add Sensors

Each sensor is added as a **subentry** under the integration. Two methods:

- **Map search.** Pick from public sensors near a latitude/longitude/radius.
- **Manual entry.** Enter the sensor **Index** plus optional **Read Key**.
  - The Read Key is **required for private sensors** that are not shown on the public sensor map.
  - The Read Key is **required for no cost API usage** of your own sensors (the Read Key is sent via email during sensor registration). Refer to [PurpleAir community: API points for sensor owners][free-points-link].

### Account-Level Diagnostics

In addition to the per-sensor subentries, the integration registers a single per-config-entry **organization** device (named `<entry-title> organization` - e.g. "PurpleAir organization" for the default integration title) that surfaces account-level information shared across all sensors under the same API key. It backs the **Remaining points** and **Consumption rate** diagnostic sensors (both enabled by default), plus the points-related repair issues. In **Settings -> Devices & Services -> PurpleAir** this device appears under HA's "Devices that don't belong to a sub-entry" heading. That label reads as a defect but is intentional: the organization endpoint is account-scoped (per API key), not per-sensor, so the device deliberately has no subentry parent. The device also disambiguates account-level entities when multiple PurpleAir API keys are configured - without it, entity IDs and friendly names would collide across accounts.

## Sensor Behavior and Calibration

These notes explain why entities report the values they do. The integration takes two different approaches depending on how settled the underlying math is:

- **Widely-adopted, well-specified corrections are implemented in code** as disabled-by-default opt-in entities - specifically the US EPA PM2.5 humidity correction and the US EPA PM2.5 AQI. The formulas are cited below with their source documents.
- **Local, deployment-specific calibrations** (ambient temperature/humidity offsets, per-channel corrections, alternative AQI schemas) remain user-territory - the integration exposes the raw fields and the README shows template-sensor examples for the common cases.

All field semantics below are verified against the [official API documentation][purpleair-api-link].

### PM2.5 Mass Concentration

The `PM2.5 mass concentration` sensor returns the API's `pm2.5` field. On the real-time endpoint this field is **already**:

- indoor-vs-outdoor aware - it uses the CF=1 variant on sensors registered as indoor and the ATM variant on outdoor sensors;
- downgrade-aware - if one of the two Plantower channels is flagged as degraded, its reading is excluded from the average automatically.

See the [API docs § `pm2.5`][purpleair-api-pm25-link] for the full spec. You do not need to pick between ATM and CF=1 manually.

For the Wallace **ALT-CF3** variant (often preferred for wildfire smoke and low-concentration outdoor monitoring) enable the disabled-by-default **PM2.5 ALT mass concentration** sensor. See [the API docs § `pm2.5_alt`][purpleair-api-pm25-link] for the formula.

For US EPA-corrected PM2.5, enable the opt-in **PM2.5 EPA mass concentration** entity - see [EPA-corrected PM2.5](#epa-corrected-pm25-pm25-epa-mass-concentration) below for the formula and source.

### Rolling Averages

The disabled-by-default **PM2.5 10/30/60-minute**, **6/24-hour**, and **1-week average** sensors expose the API's running-average fields. These are the preferred input for AQI-style reporting (e.g. the US EPA AQI is defined against a 24-hour average). Same indoor/outdoor auto-selection applies.

### Internal Temperature and Humidity

The `temperature` and `humidity` entities expose readings from **inside the sensor housing**, not ambient conditions. Per the API docs:

> *This matches the "Operating Temperature" map layer and is not representative of ambient conditions. Formulas can be applied to estimate ambient temperature.*

In practice, a PA-II reads roughly **8 °F hotter** and **4 %RH drier** than the ambient air around it. No correction is applied to the entity values - they are the raw sensor readings.

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

### EPA-Corrected PM2.5 (`PM2.5 EPA Mass Concentration`)

A disabled-by-default sensor that applies the US EPA's published correction to the raw PurpleAir PM2.5 output. Reference: **"Fire and Smoke Map Sensor Data Processing"**, EPA Office of Research and Development, revised 2021, page 26 of [`dirEntryId=353088`][epa-pm25-link].

Implementation details:

- Inputs: the PurpleAir `pm2.5` field (ATM variant auto-selected for outdoor sensors) and raw `humidity`. Both are requested automatically when this sensor is enabled - you do not need to also enable the baseline PM2.5 and humidity entities.
- Uses a piecewise formula with five regions (PM < 30, 30 <= PM < 50, 50 <= PM \< 210, 210 <= PM < 260, PM >= 260) with linear blending across the two transition regions so the output is continuous at every breakpoint.
- Uses the sensor's **internal** housing humidity as input, matching how the EPA regression was fit - no ambient correction is applied to humidity here.
- Calibrated for outdoor sensors; enabling it on an indoor sensor is not meaningful.

The code lives in `_pm25_epa_correction` in [`sensor.py`](custom_components/purpleair/sensor.py). The implementation has unit tests that verify each region's formula and the continuity of every boundary.

### US AQI from 24-Hour PM2.5 (`PM2.5 Air Quality Index`)

A disabled-by-default sensor that reports the US EPA Air Quality Index for PM2.5 based on the sensor's 24-hour rolling average.

- Input: the PurpleAir `pm2.5_24hour` field (auto-selected for indoor/outdoor and excluding downgraded channels).
- Uses the breakpoint table from [AirNow - Air Quality Index (AQI) Basics][airnow-aqi-link], updated to the **2024 NAAQS revision** (Good/Moderate threshold lowered from 12.0 -> 9.0 µg/m³, higher bands tightened).
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

Reloading the config entry (**Settings -> Devices & Services -> PurpleAir -> ⋮ -> Reload**) forces an immediate static re-fetch - useful after a firmware update or sensor relocation.

**Measured cost** for a default install of **one sensor with the six enabled-by-default entities** (temperature, humidity, pressure, PM1.0/PM2.5/PM10 mass concentrations). Both rows query the same 16 fields (4 availability + 6 default-enabled entity fields + 6 static device fields); the difference is whether the static fields ride along on every refresh or only once per day:

| Scenario | Fields per refresh | Refreshes per day | Field-fetches per day |
| --- | --- | --- | --- |
| Same fields, refetched every cycle (naive) | 16 | 288 | **4,608** |
| This integration (static fields cached 24 h) | 10 + 6 once daily | 288 + 1 | **2,886** (≈ 37 % less) |

The savings here come from the static-cache split alone. A second saving comes from **not** fetching fields for disabled entities: the integration declares 32 unique fields across all entities, but a default install only fetches 16 of them. Enabling every optional entity (PM particle counts, RSSI, uptime, ALT, six rolling averages, diagnostics) raises the per-refresh set to 26 fields; disabling a sensor you aren't using immediately drops its fields out of the next refresh.

Free points are available for sensor owners who use their own sensor's Read Key; see [API points for sensor owners][free-points-link].

The integration tracks remaining points and consumption rate via the [Account-Level Diagnostics](#account-level-diagnostics) and raises a **PurpleAir API points are running low** repair issue when fewer than seven days of points remain at the current consumption rate. New small accounts can hit the threshold soon after install while the consumption rate stabilizes; that's expected. Two ways to clear the warning:

- **Buy more points** at the [PurpleAir Developer dashboard][purpleair-projects-link].
- **Use a per-sensor Read Key** for sensors you own. Queries to your own sensors with their Read Key cost zero points. For new sensors, enter the Read Key when adding (see [3. Add Sensors](#3-add-sensors)). For sensors migrated from the built-in integration that don't yet have a Read Key, see [Switch an Existing Sensor to a Read Key](#switch-an-existing-sensor-to-a-read-key).

A separate **PurpleAir API points are exhausted** repair issue fires (severity error) if the account runs out of points entirely; it clears automatically on the next successful refresh after points are restored.

## Migration from the Built-in Integration

### Upgrade: Built-in -> Custom

1. Install this custom integration via [HACS][hacs-xyz-link] or by copying `custom_components/purpleair/` into your Home Assistant config directory.
2. Restart Home Assistant. The installation has no effect until HA restarts - integrations are loaded once at startup.
3. On startup, HA's loader prefers the custom integration over the built-in one (they share the `purpleair` domain). Your existing PurpleAir config entry stays in place in `.storage/core.config_entries` and is migrated to the subentry layout. Entity IDs, devices, and long-term statistics are preserved. **You do not need to remove the built-in integration first - it is part of core, not a separate installation.**
4. You will see this warning in the log:

    ```text
    We found a custom integration purpleair which has not been tested by Home Assistant
    ```

    HA emits it for every custom integration and it is not a problem.

If migration fails, the entry is marked `SETUP_ERROR`. Check **Settings -> System -> Repairs** and the log; empty v1 entries raise a targeted repair issue.

### Switch an Existing Sensor to a Read Key

The built-in integration didn't support per-sensor Read Keys, so subentries migrated from it have only the sensor **Index** populated. If you own a sensor, switching it to use a per-sensor Read Key makes its API queries free - see [PurpleAir community: API points for sensor owners][free-points-link]. This is the recommended remediation when the [low-points repair issue](#api-points-and-field-selection) fires on a small account.

In **Settings -> Devices & Services -> PurpleAir**, click ⋮ next to the sensor -> **Configure**, then enter the sensor's Read Key. The integration validates the key against PurpleAir before saving and reloads on success - long-term-statistics history, entity IDs, and devices are preserved (only the sensor's API authentication changes). The same flow can clear an existing Read Key by leaving the field blank, or replace one that's been rotated.

The Read Key can also be added at sensor-add time for new sensors - see [3. Add Sensors](#3-add-sensors).

## Questions or Issues

- **General questions**:
  - Use the [Discussions][discussions-link] forum for general questions.
- **Bug reports**:
  - Ask in the [Discussions][discussions-link] forum if you are not sure if it is a bug.
  - Check the existing [Issues][issues-link] tracker for known problems.
  - If the issue is unique and a bug, file it in [Issues][issues-link], and include all pertinent steps to reproduce the issue.

## Contributing

- **Branching workflow**:
  - Feature branch -> `develop` via **squash merge**; `develop` -> `main` via **merge commit**. Both methods are pinned in the branch rulesets.
  - CI runs on every branch push (there is no `pull_request` trigger); a fork PR's pushes don't run the base-repo check, so a maintainer lands the change on an in-repo branch before merge.
  - Dependabot and the HA-version-bump bot target `develop` and auto-merge once the required check passes.
  - See [`WORKFLOW.md`](WORKFLOW.md) and [`AGENTS.md`](AGENTS.md) for the full release flow and HA-version-bump process.
- **Code style**:
  - [ruff][ruff-link] (config in [`.ruff.toml`](.ruff.toml)), `mypy --strict`, and `pyright`; see [`CODESTYLE.md`](CODESTYLE.md) and [`.editorconfig`](.editorconfig). Apply auto-fixes with `scripts/fix`, verify with `scripts/lint` (CI runs the same checks).
- **Development**:
  - See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the devcontainer and local development setup.
- **Repository setup**:
  - See [`repo-config/README.md`](repo-config/README.md) for repository configuration details.

## Credits

This integration is an independent implementation based on the [`home-assistant/core` PurpleAir component][ha-core-components-link].\
It was created to be maintained independently after the upstream PR [home-assistant/core#140901][ha-core-pr-link] - reducing API token usage and adding support for private sensors - was abandoned.

The original Apache 2.0 copyright is retained alongside the current maintainer's in [LICENSE](./LICENSE) and [NOTICE](./NOTICE).

## License

Licensed under the [Apache 2.0 License][license-link] and [NOTICE](./NOTICE)\
[![License][license-shield]][license-link]

<!-- Shields links -->

[actions-link]: https://github.com/ptr727/homeassistant-purpleair/actions
[buildstatus-shield]: https://img.shields.io/github/actions/workflow/status/ptr727/homeassistant-purpleair/test-pull-request.yml?logo=github&label=Build%20Status
[commits-link]: https://github.com/ptr727/homeassistant-purpleair/commits/main
[coverage-link]: https://app.codecov.io/gh/ptr727/homeassistant-purpleair
[coverage-shield]: https://img.shields.io/codecov/c/github/ptr727/homeassistant-purpleair?logo=codecov&label=Coverage
[discussions-link]: https://github.com/ptr727/homeassistant-purpleair/discussions
[hacs-link]: https://github.com/hacs/integration
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=homeassistantcommunitystore&label=HACS
[haversion-link]: https://www.home-assistant.io/blog/categories/release-notes/
[haversion-shield]: https://img.shields.io/badge/Home_Assistant-2026.4.0%2B-41BDF5?logo=homeassistant
[issues-link]: https://github.com/ptr727/homeassistant-purpleair/issues
[lastcommit-shield]: https://img.shields.io/github/last-commit/ptr727/homeassistant-purpleair?logo=github&label=Last%20Commit
[license-link]: ./LICENSE
[license-shield]: https://img.shields.io/github/license/ptr727/homeassistant-purpleair?label=License
[prereleaseversion-shield]: https://img.shields.io/github/v/release/ptr727/homeassistant-purpleair?include_prereleases&label=GitHub%20Pre-Release&logo=github&color=orange
[qualityscale-link]: ./custom_components/purpleair/quality_scale.yaml
[qualityscale-shield]: https://img.shields.io/badge/Quality_Scale-Platinum-9C27B0?logo=homeassistant
[releases-link]: https://github.com/ptr727/homeassistant-purpleair/releases
[releaseversion-shield]: https://img.shields.io/github/v/release/ptr727/homeassistant-purpleair?logo=github&label=GitHub%20Release

<!-- Other links -->

[airnow-aqi-link]: https://www.airnow.gov/aqi/aqi-basics/
[epa-pm25-link]: https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=353088&Lab=CEMM
[free-points-link]: https://community.purpleair.com/t/api-points-for-sensor-owners/7525
[ha-core-components-link]: https://github.com/home-assistant/core/tree/dev/homeassistant/components/purpleair
[ha-core-pr-link]: https://github.com/home-assistant/core/pull/140901
[hacs-xyz-link]: https://hacs.xyz/
[migration-link]: #migration-from-the-built-in-integration
[purpleair-api-link]: https://api.purpleair.com/
[purpleair-api-pm25-link]: https://api.purpleair.com/#api-sensors-get-sensor-data
[purpleair-api-pricing-link]: https://community.purpleair.com/t/api-pricing/4523
[purpleair-developer-link]: https://develop.purpleair.com/
[purpleair-keys-link]: https://develop.purpleair.com/dashboards/keys
[purpleair-link]: https://www.purpleair.com/
[purpleair-projects-link]: https://develop.purpleair.com/dashboards/projects
[qualityscale-rules-link]: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/
[ruff-link]: https://docs.astral.sh/ruff/
