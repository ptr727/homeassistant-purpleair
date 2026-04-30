# PurpleAir for Home Assistant — Release History

Long-running release ledger. The README's [Release notes](./README.md#release-notes) section summarises only the current release; older releases live here. Per-commit detail (PR titles, authors, diff range) is auto-generated on each [GitHub Release][releases-link] page.

## Release History

- **Current release** (Requires Home Assistant 2026.4.0 or newer):
  - Private sensor support via per-sensor read keys (free API points when querying your own sensors).
  - Subentry layout — one subentry per sensor; automatic v1 → v2 migration from the built-in integration preserving entity IDs, devices, and long-term-statistics history.
  - Cost-aware field selection — only fields backing enabled entities are requested, and static device-info fields are fetched once per day. Roughly 37 % fewer field-fetches per day than a naive implementation for a default install.
  - Quality-aware availability — entities go unavailable on `confidence < 50`, `channel_state == 0` ("No PM"), or a stale `last_seen`.
  - Account-level **Remaining points** and **Consumption rate** diagnostic sensors (disabled by default), backed by a daily refresh of `GET /v1/organization`. A persistent repair issue fires when the balance drops below seven days of consumption or the API rejects requests with `PaymentRequiredError`.
  - Typed config-flow & coordinator errors — the integration matches on `aiopurpleair`'s typed exception subclasses (`InvalidDataReadKeyError`, `ApiKeyTypeMismatchError`, `ApiDisabledError`, `PaymentRequiredError`, …) instead of `str(err)` substrings. Distributed via the temporary fork `aiopurpleair-ptr727==2026.4.0` while upstream review is pending.
  - Sensor selection from a map — pick nearby public sensors from a radius-filtered map picker.
  - Disabled-by-default derived entities: PM2.5 EPA mass concentration (US EPA piecewise humidity correction) and PM2.5 air quality index (US EPA AQI from the 24-hour average, 2024 NAAQS breakpoints).
  - Disabled-by-default diagnostic entities: Confidence, Channel state, Channel flags, Last seen, Internal temperature/humidity/pressure, PM2.5 ALT, PM2.5 10-minute/30-minute/60-minute/6-hour/24-hour/1-week averages.
  - Clear config-flow errors — WRITE API keys, disabled keys, and wrong per-sensor read keys each surface a targeted error on the right field.
  - Platinum-tier quality-scale compliance.

[releases-link]: https://github.com/ptr727/homeassistant-purpleair/releases
