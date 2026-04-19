# PurpleAir for Home Assistant (custom integration)

A Home Assistant [custom integration](https://developers.home-assistant.io/docs/creating_integration_file_structure/) for [PurpleAir](https://www.purpleair.com/) air-quality sensors. Distributed via [HACS](https://hacs.xyz/) or installed manually by copying into `<config>/custom_components/`.

> **Not the built-in PurpleAir integration.** This custom integration shares the `purpleair` domain with the core built-in one. When loaded, Home Assistant's loader picks the custom version over the built-in and migrates existing config entries forward — the upgrade is automatic and preserves entity IDs and history. **The downgrade is not:** if you later remove this custom integration, the built-in cannot read the migrated v2 entries until [core PR #140901](https://github.com/home-assistant/core/pull/140901) ships. See [Migration from the built-in integration](#migration-from-the-built-in-integration) for details. In the **Add Integration** picker this appears as **"PurpleAir (custom)"** to distinguish it from the built-in **"PurpleAir"**.

## What it provides beyond Home Assistant's built-in PurpleAir integration

- **Private sensor support.** Each subentry can supply its own per-sensor **Read Key**, so the integration can query unlisted private sensors and query self-owned sensors at no API-point cost.
- **Config subentries.** One subentry per sensor (the current HA model) instead of a single config entry holding a list of sensor indices.
- **Sensor selection from a map.** Pick nearby public sensors from a radius-filtered map picker.
- **Cost-aware field selection.** Only fields for *enabled* entities are requested, and static device-info fields are fetched once per day instead of every refresh. A typical 6-entity config uses roughly **37 % fewer field-fetches per day** than a naive implementation — see [API points and field selection](#api-points-and-field-selection).
- **Quality-aware availability.** Entities are marked unavailable when the sensor's `confidence` drops below 50 %, when the two Plantower channels disagree (`channel_state == 0`), or when the sensor has stopped reporting (`last_seen` older than 10 min).
- **Clear error messages in the config flow.** WRITE API keys, disabled API keys, and wrong per-sensor read keys each surface a distinct error on the right field.
- **Gold-tier quality scale.** Full HA quality-scale gold tier: `parallel-updates`, `entity-unavailable`, `log-when-unavailable`, `repair-issues`, `reconfiguration-flow`, entity translations, exception translations, ≥ 97 % test coverage, and more — see [`quality_scale.yaml`](custom_components/purpleair/quality_scale.yaml).
- **Automatic v1 → v2 migration.** Existing config entries from the built-in integration are converted to the subentry layout on first load; entity IDs, devices, and history are preserved.

## Why private sensor support matters

**PurpleAir uses a points for data access model**, see [PurpleAir Community: API Pricing](https://community.purpleair.com/t/api-pricing/4523) for details. New accounts start with enough points to run for about a month using this integration, before more points may need to be purchased.

**Sensor owners can access data for their own sensors free of charge**, see [PurpleAir community: API points for sensor owners](https://community.purpleair.com/t/api-points-for-sensor-owners/7525). To run this integration long-term at no cost for your own sensors, use the Read Key that was provided via email during sensor registration.

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

## Sensor behaviour and calibration

These notes explain why entities report the values they do. The integration takes two different approaches depending on how settled the underlying math is:

- **Widely-adopted, well-specified corrections are implemented in code** as disabled-by-default opt-in entities — specifically the US EPA PM2.5 humidity correction and the US EPA PM2.5 AQI. The formulas are cited below with their source documents.
- **Local, deployment-specific calibrations** (ambient temperature/humidity offsets, per-channel corrections, alternative AQI schemas) remain user-territory — the integration exposes the raw fields and the README shows template-sensor examples for the common cases.

All field semantics below are verified against the [official API documentation](https://api.purpleair.com/).

### PM2.5 mass concentration

The `PM2.5 mass concentration` sensor returns the API's `pm2.5` field. On the real-time endpoint this field is **already**:

- indoor-vs-outdoor aware — it uses the CF=1 variant on sensors registered as indoor and the ATM variant on outdoor sensors;
- downgrade-aware — if one of the two Plantower channels is flagged as degraded, its reading is excluded from the average automatically.

See the [API docs § `pm2.5`](https://api.purpleair.com/#api-sensors-get-sensor-data) for the full spec. You do not need to pick between ATM and CF=1 manually.

For the Wallace **ALT-CF3** variant (often preferred for wildfire smoke and low-concentration outdoor monitoring) enable the disabled-by-default **PM2.5 ALT mass concentration** sensor. See [the API docs § `pm2.5_alt`](https://api.purpleair.com/#api-sensors-get-sensor-data) for the formula.

For US EPA-corrected PM2.5, enable the opt-in **PM2.5 EPA mass concentration** entity — see [EPA-corrected PM2.5](#epa-corrected-pm25-pm25-epa-mass-concentration) below for the formula and source.

### Rolling averages

The disabled-by-default **PM2.5 10/30/60-minute**, **6/24-hour**, and **1-week average** sensors expose the API's running-average fields. These are the preferred input for AQI-style reporting (e.g. the US EPA AQI is defined against a 24-hour average). Same indoor/outdoor auto-selection applies.

### Temperature and humidity are INTERNAL to the sensor housing

Per the API docs:

> *This matches the "Operating Temperature" map layer and is not representative of ambient conditions. Formulas can be applied to estimate ambient temperature.*

In practice, a PA-II reads roughly **8 °F hotter** and **4 %RH drier** than the ambient air around it. The `temperature` and `humidity` entities expose the raw sensor readings with no correction applied.

If you need an ambient estimate, use a template sensor. Example:

```yaml
template:
  - sensor:
      - name: "Backyard ambient temperature"
        device_class: temperature
        unit_of_measurement: "°F"
        # Rule of thumb: PA-II reads ~8 °F hotter than ambient.
        # See https://community.purpleair.com/ for more precise formulas.
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

### EPA-corrected PM2.5 (`PM2.5 EPA mass concentration`)

A disabled-by-default sensor that applies the US EPA's published correction to the raw PurpleAir PM2.5 output. Reference: **"Fire and Smoke Map Sensor Data Processing"**, EPA Office of Research and Development, revised 2021, page 26 of [`dirEntryId=353088`](https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=353088&Lab=CEMM).

Implementation details:

- Inputs: the PurpleAir `pm2.5` field (ATM variant auto-selected for outdoor sensors) and raw `humidity`. Both are requested automatically when this sensor is enabled — you do not need to also enable the baseline PM2.5 and humidity entities.
- Uses a piecewise formula with five regions (PM < 30, 30 ≤ PM < 50, 50 ≤ PM < 210, 210 ≤ PM < 260, PM ≥ 260) with linear blending across the two transition regions so the output is continuous at every breakpoint.
- Uses the sensor's **internal** housing humidity as input, matching how the EPA regression was fit — no ambient correction is applied to humidity here.
- Calibrated for outdoor sensors; enabling it on an indoor sensor is not meaningful.

The code lives in `_pm25_epa_correction` in [`sensor.py`](custom_components/purpleair/sensor.py). The implementation has unit tests that verify each region's formula and the continuity of every boundary.

### US AQI from 24-hour PM2.5 (`PM2.5 air quality index`)

A disabled-by-default sensor that reports the US EPA Air Quality Index for PM2.5 based on the sensor's 24-hour rolling average.

- Input: the PurpleAir `pm2.5_24hour` field (auto-selected for indoor/outdoor and excluding downgraded channels).
- Uses the breakpoint table from [AirNow — Air Quality Index (AQI) Basics](https://www.airnow.gov/aqi/aqi-basics/), updated to the **2024 NAAQS revision** (Good/Moderate threshold lowered from 12.0 → 9.0 µg/m³, higher bands tightened).
- Concentrations are truncated to 0.1 µg/m³ before lookup (40 CFR § 58 App. G), AQI within each band is linearly interpolated, and values above 500.4 µg/m³ cap at AQI 500.

The breakpoint table and lookup live in `_pm25_aqi` in [`sensor.py`](custom_components/purpleair/sensor.py); unit tests cover every band edge.

### Implementing your own corrections

If you prefer different calibration (e.g. ambient-temperature offset, alternative AQI schema), template sensors in `configuration.yaml` work fine. The integration exposes the raw fields needed for any such derivation via its opt-in entities (PM2.5, ALT, 24-hour average, rolling averages, raw internal temp/humidity).

### Availability signals

Entities become **unavailable** when any of:

- the sensor's `confidence` score is below 50 % (the two PMS channels disagree too much to trust the average);
- `channel_state` reports **No PM** (no PM sensor detected at all);
- `last_seen` is more than 10 minutes behind the coordinator's `data_timestamp_utc` (the sensor has stopped reporting).

Each transition is logged once at `INFO` under the `custom_components.purpleair` logger.

### API points and field selection

PurpleAir charges API points per **field** per sensor per call. The integration takes two steps to minimise that cost:

**1. Only fetch fields for enabled entities.** Each [`PurpleAirSensorEntityDescription`](custom_components/purpleair/sensor.py) declares its required API fields; at refresh time the coordinator walks the entity registry for the config entry and unions the `api_fields` of every enabled description. Disabled entities contribute zero API fields to the outgoing request. Enabling or disabling an entity in the UI triggers an immediate refresh so the field set reflects reality on the next cycle.

**2. Static fields are cached for 24 hours.** The API's field catalogue mixes values that change every reading (PM2.5, humidity, `confidence`, `last_seen`) with values that only change on firmware updates or user actions (`name`, `hardware`, `model`, `firmware_version`, `latitude`, `longitude`). The coordinator splits them into two sets:

| Set | Fields | Fetch cadence |
|---|---|---|
| `STATIC_DEVICE_FIELDS` | `name`, `hardware`, `model`, `firmware_version`, `latitude`, `longitude` | Once at setup, then every 24 h |
| `AVAILABILITY_FIELDS` | `last_seen`, `confidence`, `channel_state`, `channel_flags` | Every refresh (5 min) |
| Per-entity fields | e.g. `temperature`, `humidity`, `pm2.5`, `pm2.5_24hour` | Every refresh, only for enabled entities |

Reloading the config entry (**Settings → Devices & services → PurpleAir → ⋮ → Reload**) forces an immediate static re-fetch — useful after a firmware update or sensor relocation.

**Measured cost** for a default install of **one sensor with the six enabled-by-default entities** (temperature, humidity, pressure, PM1.0/PM2.5/PM10 mass concentrations):

| Scenario | Fields per refresh | Refreshes per day | Field-fetches per day |
|---|---|---|---|
| Hard-coded full field list (naive) | 16 | 288 | **4,608** |
| This integration | 10 + 6 once daily | 288 + 1 | **2,886** (≈ 37 % less) |

Enabling every optional entity (PM particle counts, RSSI, uptime, ALT, six rolling averages, diagnostics) raises the per-refresh set to roughly 26 fields; disabling a sensor you aren't using immediately drops its fields out of the next refresh.

Free points are available for sensor owners who use their own sensor's Read Key; see [API points for sensor owners](https://community.purpleair.com/t/api-points-for-sensor-owners/7525).

## Upstream dependency: proposed `aiopurpleair` changes

The `aiopurpleair` library this integration depends on (pinned to `2025.08.1` in [`manifest.json`](custom_components/purpleair/manifest.json)) covers only the sensors endpoints and maps three error codes to exceptions. Several of the [API's documented error codes](https://api.purpleair.com/) collapse to a generic `PurpleAirError` today. This integration works around that by pattern-matching on exception messages; cleaner error handling is gated on the following upstream additions.

### 1. Extend `ERROR_CODE_MAP` in `aiopurpleair/errors.py`

Currently:

```python
ERROR_CODE_MAP = {
    "ApiKeyInvalidError": InvalidApiKeyError,
    "ApiKeyMissingError": InvalidApiKeyError,
    "NotFoundError": NotFoundError,
}
```

Add new exception subclasses and map entries for every error code the PurpleAir v1 API documents:

| API error code | HTTP | New exception class | Base class | Why we need it |
|---|---|---|---|---|
| `ApiKeyTypeMismatchError` | 403 | `ApiKeyTypeMismatchError` | `InvalidApiKeyError` | User supplied a WRITE key where READ is required. |
| `ApiKeyRestrictedError` | 403 | `ApiKeyRestrictedError` | `InvalidApiKeyError` | Key restricted to host/referrer. |
| `ApiDisabledError` | 403 | `ApiDisabledError` | `InvalidApiKeyError` | Endpoint disabled for this key. |
| `InvalidDataReadKeyError` | 400 | `InvalidDataReadKeyError` | `InvalidRequestError` | Wrong per-sensor read key — needed to distinguish from "sensor not found." |
| `InvalidFieldValueError` | 400 | `InvalidFieldValueError` | `InvalidRequestError` | Unknown field requested. |
| `InvalidParameterValueError` | 400 | `InvalidParameterValueError` | `InvalidRequestError` | Generic parameter validation failure. |
| `MissingRequiredParameterError` | 400 | `MissingRequiredParameterError` | `InvalidRequestError` | |
| `InvalidRequestUrlError` | 400 | `InvalidRequestUrlError` | `InvalidRequestError` | |
| `InvalidTimestampError` | 400 | `InvalidTimestampError` | `InvalidRequestError` | History endpoints only. |
| `InvalidTimestampSpanError` | 400 | `InvalidTimestampSpanError` | `InvalidRequestError` | History endpoints only. |
| `InvalidAverageError` | 400 | `InvalidAverageError` | `InvalidRequestError` | History endpoints only. |
| `RequiresHttpsError` | 403 | `RequiresHttpsError` | `PurpleAirError` | |
| `PaymentRequiredError` | 402 | `PaymentRequiredError` | `PurpleAirError` | Out of API points — should trigger a persistent repair issue. |
| `RateLimitExceededError` | 429 | `RateLimitExceededError` | `PurpleAirError` | Standard 429; coordinators should back off. |
| `DataInitializingError` | 503 | `DataInitializingError` | `PurpleAirError` | Transient — API says retry in 10 s. |
| `ProjectArchivedError` | 403 | `ProjectArchivedError` | `InvalidApiKeyError` | |
| `MissingJsonPayloadError` | 415 | `MissingJsonPayloadError` | `InvalidRequestError` | |
| `InvalidJsonPayloadError` | 400 | `InvalidJsonPayloadError` | `InvalidRequestError` | |
| `InvalidTokenError` | 403 | `InvalidTokenError` | `InvalidApiKeyError` | |

### 2. Add `GET /v1/organization` endpoint

New file `aiopurpleair/endpoints/organizations.py`:

```python
class OrganizationsEndpoints(APIEndpointsBase):
    async def async_get_organization(self) -> GetOrganizationResponse: ...
```

Companion model `aiopurpleair/models/organizations.py` (`GetOrganizationResponse`) with fields:

- `organization_id: str` — hexadecimal identifier
- `organization_name: str`
- `remaining_points: int`
- `consumption_rate: int` — estimated points/day
- `api_version: str`
- `timestamp_utc: datetime`

Rate limit: 1 s. Endpoint: `GET /v1/organization`. Auth: `X-API-Key` header.

Exposed on `API` as `api.organizations`, analogous to `api.sensors`.

Use case: this integration wants a daily `OrganizationCoordinator` driving **Remaining points** and **Consumption rate** diagnostic sensors, plus a repair issue when `remaining_points` drops below `consumption_rate × 7`.

### 3. Testing expectations for the upstream PR

- Unit tests per new exception subclass: mock a 4xx/5xx aiohttp response containing the error code in the JSON body, assert `raise_error` raises the correct subclass.
- Unit test for `async_get_organization` parsing a mock response.
- Existing tests remain green (no breaking changes to the public API).

### 4. Migration path once the above ships

Once a new `aiopurpleair` release is published:

1. Bump the pin in [`manifest.json`](custom_components/purpleair/manifest.json) and [`requirements.txt`](requirements.txt).
2. Replace the `str(err)` message matches in [`coordinator.py`](custom_components/purpleair/coordinator.py) and [`config_flow.py`](custom_components/purpleair/config_flow.py) with `except InvalidDataReadKeyError`, `except PaymentRequiredError`, etc.
3. Add an `OrganizationCoordinator` for the diagnostic points sensors and the low-points repair issue.

All error codes and semantics above are verified against a snapshot of the official docs at `.claude/API - PurpleAir.mhtml`.

## Relationship to the upstream Home Assistant PR

An earlier version of this integration was submitted for inclusion in Home Assistant core as [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) (with accompanying docs at [home-assistant/home-assistant.io#38063](https://github.com/home-assistant/home-assistant.io/pull/38063)). That PR has been pending review for some time.

In the meantime, this HACS distribution has continued to move forward — it now **supersedes** the PR in functionality. Everything in the "What it provides beyond Home Assistant's built-in PurpleAir integration" section at the top of this README was developed after the PR was filed:

- Quality-aware availability (`confidence`, `channel_state`, `last_seen`).
- Cost-aware dynamic field selection and the 24 h static-field cache.
- The opt-in diagnostic entities: PM2.5 ALT, six rolling-average sensors, confidence, channel state / flags, last-seen, internal-vs-ambient diagnostics.
- Opt-in derived entities implemented in code with source-document citations: **PM2.5 EPA mass concentration** (humidity correction) and **PM2.5 air quality index** (2024 NAAQS).
- Gold-tier quality-scale compliance (`parallel-updates`, repair issues, stale-device cleanup, exception translations, enum entity device classes, etc.).
- Distinct config-flow errors for WRITE-type keys, disabled keys, and wrong per-sensor read keys.
- Documented sensor behaviour with formulas, citations, and template-sensor examples for user-side calibrations.

The original core PR will not be kept in lockstep with these changes, and may be abandoned. The HACS release stream is the maintained path going forward.

## Release notes

### v0.1.0 — initial release

Requires Home Assistant 2026.4.0 or newer.

Highlights over the built-in PurpleAir integration:

- **Private sensor support** via per-sensor read keys (free API points when querying your own sensors).
- **Subentry layout** — one subentry per sensor; automatic v1 → v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
- **Cost-aware field selection** — only fields backing enabled entities are requested, and static device-info fields are fetched once per day. Roughly 37 % fewer field-fetches per day than a naive implementation for a default install.
- **Quality-aware availability** — entities go unavailable on `confidence < 50`, `channel_state == 0` ("No PM"), or a stale `last_seen`.
- **Sensor selection from a map.** Pick nearby public sensors from a radius-filtered map picker.
- **Derived entities (disabled by default):** PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
- **Diagnostic entities (disabled by default):** Confidence, Channel state, Channel flags, Last seen, Internal temperature/humidity/pressure, PM2.5 ALT, and PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
- **Clear config-flow errors** — WRITE API keys, disabled keys, and wrong per-sensor read keys each surface a targeted error on the right field.
- **Gold-tier** quality-scale compliance (`parallel-updates`, `entity-unavailable`, `log-when-unavailable`, `repair-issues`, `reconfiguration-flow`, exception translations, ≥ 97 % test coverage, `mypy --strict` clean).

Known limitation: the v1 → v2 migration is one-way until [core PR #140901](https://github.com/home-assistant/core/pull/140901) merges. Uninstalling this custom integration after migration requires manually deleting and re-creating the PurpleAir config entry (long-term-statistics for the old entity IDs are lost). See [Migration from the built-in integration](#migration-from-the-built-in-integration) for the upgrade and downgrade procedures.

## Migration from the built-in integration

### Upgrade: built-in → custom

1. Install this custom integration via [HACS](https://hacs.xyz/) or by copying `custom_components/purpleair/` into your Home Assistant config directory.
2. Restart Home Assistant. The installation has no effect until HA restarts — integrations are loaded once at startup.
3. On startup, HA's loader prefers the custom integration over the built-in one (they share the `purpleair` domain). Your existing PurpleAir config entry stays in place in `.storage/core.config_entries` and is migrated to the subentry layout. Entity IDs, devices, and long-term statistics are preserved. **You do not need to remove the built-in integration first — it is part of core, not a separate installation.**
4. You will see `We found a custom integration purpleair which has not been tested by Home Assistant` in the log. That warning is emitted by HA for every custom integration and is not a problem.

If migration fails, the entry is marked `SETUP_ERROR`. Check **Settings → System → Repairs** and the log; empty v1 entries raise a targeted repair issue.

### Downgrade: custom → built-in — **requires manual work**

This custom integration uses config-entry schema **version 2** (one subentry per sensor). The built-in integration in Home Assistant core is still on schema **version 1**. If you simply delete `custom_components/purpleair/` and restart, the built-in cannot read v2 entries and the integration will fail to set up with `Config entry for purpleair is from a future version`.

Two recovery options:

- **Wait for [home-assistant/core#140901](https://github.com/home-assistant/core/pull/140901) to merge.** That PR moves the built-in to schema v2 with the same subentry layout, at which point the downgrade works automatically.
- **Rebuild the entry manually.** In Home Assistant go to **Settings → Devices & Services → PurpleAir → … → Delete**, then remove `custom_components/purpleair/`, restart, and re-add the built-in integration from scratch. Long-term-statistics history tied to the migrated entity IDs is lost.

There is no in-place downgrade until the core PR merges. Plan accordingly before installing.

## Status & credits

- **Branch layout:** `develop` for testing, releases cut from `main`.
- **API library:** [aiopurpleair](https://pypi.org/project/aiopurpleair/), authored by [@bachya](https://github.com/bachya).
- **License:** Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
- **Credits:** Original PurpleAir integration author [@bachya](https://github.com/bachya); subentry redesign reviewed and supported by [@joostlek](https://github.com/joostlek).

Bug reports and feature requests are welcome on the [issue tracker](https://github.com/ptr727/homeassistant-purpleair/issues).

## Development

The repo includes a VS Code devcontainer and helper scripts:

```sh
scripts/setup     # install dev requirements
scripts/develop   # boot Home Assistant against ./config with this integration loaded
scripts/fix       # apply ruff auto-fixes (format + check --fix)
scripts/lint      # verify-only: ruff format --check + ruff check + mypy --strict (mirrors CI)
pytest            # run the test suite (after pip install -r requirements-test.txt)
```

`scripts/lint` is the CI gate — it fails non-zero on any ruff, format, or `mypy --strict` violation so "green locally" matches "green on GitHub". When it fails on an auto-fixable issue, run `scripts/fix` and re-run lint.

Each script is also wired up as a VS Code task in [.vscode/tasks.json](.vscode/tasks.json) — open **Command Palette → Tasks: Run Task**, or use the shortcuts below:

| Script          | VS Code task                      | Shortcut                               |
| --------------- | --------------------------------- | -------------------------------------- |
| `scripts/setup` | **Setup: Install dev requirements** | Tasks: Run Task                        |
| `scripts/develop` | **Develop: Run Home Assistant**   | Tasks: Run Task                        |
| `scripts/fix`   | **Fix: ruff format + check --fix** | Tasks: Run Task                        |
| `scripts/lint`  | **Lint: ruff + mypy (verify)**    | `Ctrl+Shift+B` (default build task)    |
| `pytest`        | **Test: pytest**                  | Tasks: Run Test Task (default test)    |

### Devcontainer signing prerequisites

The [`.devcontainer.json`](.devcontainer.json) bind-mounts two files from the host so commits made inside the container are signed with your existing SSH signing key:

| Host path | Mounted at | Purpose |
|---|---|---|
| `~/.ssh/id_ed25519.pub` | `/home/vscode/.ssh/id_ed25519.pub` (read-only) | Public half of your SSH commit-signing key |
| `~/.config/git/allowed_signers` | `/home/vscode/.config/git/allowed_signers` (read-only) | Git's `allowed_signers` file listing which public keys are accepted as valid signers |

**Both files must exist on the host before you reopen the folder in the devcontainer, otherwise the container build will fail with a bind-mount error.**

First-time setup on the host:

```sh
# 1. Generate (or reuse) an SSH signing key pair.
#    Skip this if you already use ~/.ssh/id_ed25519 for signing.
ssh-keygen -t ed25519 -C "you@example.com" -f ~/.ssh/id_ed25519

# 2. Create the allowed_signers file. Replace the email and key material with
#    your own — the second/third fields are the contents of id_ed25519.pub.
mkdir -p ~/.config/git
printf '%s %s\n' "you@example.com" "$(cat ~/.ssh/id_ed25519.pub)" \
    > ~/.config/git/allowed_signers

# 3. Tell git to use SSH for signing (one-time, global).
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global gpg.ssh.allowedSignersFile ~/.config/git/allowed_signers
git config --global commit.gpgsign true
```

After those files exist, open the repo in VS Code and **Reopen in Container** — the devcontainer will build and every commit from inside will be signed with the host's key.

If you do not sign commits and don't want to set this up, delete the `"mounts"` block from [`.devcontainer.json`](.devcontainer.json) locally before reopening (or simply don't use the devcontainer).
