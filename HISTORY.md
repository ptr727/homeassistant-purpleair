# PurpleAir for Home Assistant — Release History

Curated highlights of what's shipped. The canonical per-version release ledger (with auto-generated PR/commit detail and downloadable artifacts) is the [GitHub Releases][releases-link] page; this file just summarizes the headline features that landed in each milestone.

## Release History

- **Version 0.1**:
  - Requires Home Assistant 2026.4.0 or newer.
  - Private sensor support via per-sensor read keys (free API points when querying your own sensors).
  - Subentry layout — one subentry per sensor; automatic v1 → v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
  - Cost-aware field selection — only fields backing enabled entities are requested, and static device-info fields are fetched once per day. Roughly 37 % fewer field-fetches per day than a naive implementation for a default install.
  - Quality-aware availability — entities go unavailable on `channel_state == 0` ("No PM"), a stale `last_seen`, or `confidence < 50` when both PM channels are reporting (single-channel sensors aren't gated on confidence because there's no second channel to cross-check).
  - Account-level **Remaining points** and **Consumption rate** diagnostic sensors (both enabled by default), backed by a daily refresh of `GET /v1/organization`. A persistent repair issue fires when the balance drops below seven days of consumption or the API rejects requests with `PaymentRequiredError`.
  - Typed config-flow & coordinator errors — the integration matches on `aiopurpleair`'s typed exception subclasses (`InvalidDataReadKeyError`, `ApiKeyTypeMismatchError`, `ApiDisabledError`, `PaymentRequiredError`, …) instead of `str(err)` substrings. Distributed via the temporary fork `aiopurpleair-ptr727==2026.5.0` while upstream review is pending.
  - Auto-reconciled entity defaults on upgrade — when a description's `entity_registry_enabled_default` flips from `False` to `True`, pre-existing installs would otherwise keep the disabled state from first registration (HA only honors the default once). On every HA startup the integration now scans its registry entries and re-enables anything that is INTEGRATION-disabled but whose current default is enabled. User-explicit disables (`disabled_by=USER`) are preserved.
  - Fixed `Last seen` sensor stuck at "Unavailable" — the `aiopurpleair-ptr727` fork was returning tz-naive `datetime` for `last_seen_utc`/`date_created_utc`/`last_modified_utc`, which HA's TIMESTAMP-class `SensorEntity` rejects by forcing the entity unavailable. The fork's `validate_timestamp` helper now returns tz-aware UTC datetimes; the integration pins `aiopurpleair-ptr727==2026.5.0` to pick up the fix.
  - Hardware-aware VOC entity creation — the VOC IAQ entity is now skipped at first registration on devices whose `hardware` string lacks the BME680/688 gas sensor (PA-I, original PA-II). PA-II-ZEN and newer (BME68X) get the entity as before. Pre-existing installs that already registered the entity for a no-VOC sensor keep it (the gate is bypassed when an entity with the matching unique_id is already in the registry). The `HARDWARE_GATES` map keeps adding gates for further `entity_registry_enabled_default=False` entities cheap; entries that flip to enabled-by-default would also need a parallel gate in the coordinator's first-refresh fallback (`coordinator.py:_compute_requested_fields`), which iterates `SENSOR_DESCRIPTIONS` independently of the registry on the very first refresh.
  - Sensor selection from a map — pick nearby public sensors from a radius-filtered map picker.
  - Disabled-by-default derived entities: PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
  - Enabled-by-default diagnostic entities: Confidence, Channel state, Last seen — these surface the values the availability gate uses, so a sensor marked Unavailable can be diagnosed at a glance from its device card. They cost zero extra API points (already fetched on every refresh).
  - Disabled-by-default diagnostic entities: Channel flags, Internal temperature/humidity/pressure, PM2.5 ALT, PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
  - Clear config-flow errors — WRITE API keys, disabled keys, and wrong per-sensor read keys each surface a targeted error on the right field.
  - Platinum-tier quality-scale compliance.

[releases-link]: https://github.com/ptr727/homeassistant-purpleair/releases
