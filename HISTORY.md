# PurpleAir for Home Assistant — Release History

Curated highlights of what's shipped. The canonical per-version release ledger (with auto-generated PR/commit detail and downloadable artifacts) is the [GitHub Releases][releases-link] page; this file just summarizes the headline features that landed in each milestone.

## Release History

- **Version 0.1**:
  - Requires Home Assistant 2026.4.0 or newer.
  - New services use the PurpleAir organization name as their service title (e.g. *Acme Corp* instead of *PurpleAir* / *PurpleAir (1)*) so multi-key installs stay legible at a glance. Falls back to the numbered default when the organization lookup is unavailable.
  - Private sensor support via per-sensor read keys (free API points when querying your own sensors).
  - Subentry layout — one subentry per sensor; automatic v1 → v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
  - Cost-aware field selection — only fields backing enabled entities are requested, and static device-info fields are fetched once per day. Roughly 37 % fewer field-fetches per day than a naive implementation for a default install.
  - Quality-aware availability — entities go unavailable on `channel_state == 0` ("No PM"), a stale `last_seen`, or `confidence < 50` when both PM channels are reporting (single-channel sensors aren't gated on confidence because there's no second channel to cross-check).
  - Account-level **Remaining points** and **Consumption rate** diagnostic sensors (both enabled by default), backed by a daily refresh of `GET /v1/organization`. A persistent repair issue fires when the balance drops below seven days of consumption or the API rejects requests with `PaymentRequiredError`.
  - Typed config-flow & coordinator errors — the integration matches on `aiopurpleair`'s typed exception subclasses (`InvalidDataReadKeyError`, `ApiKeyTypeMismatchError`, `ApiDisabledError`, `PaymentRequiredError`, …) instead of `str(err)` substrings.
  - Auto-reconciled entity defaults on upgrade — entities whose description default has flipped from disabled-to-enabled (e.g. **Confidence**, **Channel state**, **Last seen**, **Consumption rate**) come on automatically on the next HA startup. User-explicit disables are preserved.
  - Fixed **Last seen** stuck at "Unavailable".
  - Hardware-aware VOC — the **Volatile organic compounds (IAQ)** entity is only created on devices whose hardware reports a BME680/688 gas sensor (PA-II-ZEN and newer). PA-I and original PA-II don't get the entity. Pre-existing entity-registry rows are preserved on upgrade.
  - Sensor selection from a map — pick nearby public sensors from a radius-filtered map picker.
  - Disabled-by-default derived entities: PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
  - Enabled-by-default diagnostic entities: Confidence, Channel state, Last seen — these surface the values the availability gate uses, so a sensor marked Unavailable can be diagnosed at a glance from its device card. They cost zero extra API points (already fetched on every refresh).
  - Disabled-by-default diagnostic entities: Channel flags, PM2.5 ALT, PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
  - Clear config-flow errors — WRITE API keys, disabled keys, and wrong per-sensor read keys each surface a targeted error on the right field.
  - Platinum-tier quality-scale compliance.

[releases-link]: https://github.com/ptr727/homeassistant-purpleair/releases
