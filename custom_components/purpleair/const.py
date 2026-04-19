"""Constants for the PurpleAir integration."""

import logging
from typing import Final

DOMAIN: Final[str] = "purpleair"
LOGGER: Final[logging.Logger] = logging.getLogger(DOMAIN)
TITLE: Final[str] = "PurpleAir"
SCHEMA_VERSION: Final[int] = 2

CONF_LEGACY_SENSOR_INDICES: Final[str] = "sensor_indices"

CONF_ADD_MAP_LOCATION: Final[str] = "add_map_location"
CONF_ADD_OPTIONS: Final[str] = "add_options"
CONF_ADD_SENSOR_INDEX: Final[str] = "add_sensor_index"
CONF_ALREADY_CONFIGURED: Final[str] = "already_configured"
CONF_INVALID_API_KEY: Final[str] = "invalid_api_key"
CONF_INVALID_READ_KEY: Final[str] = "invalid_read_key"
CONF_KEY_DISABLED: Final[str] = "key_disabled"
CONF_NO_SENSOR_FOUND: Final[str] = "no_sensor_found"
CONF_NO_SENSORS_FOUND: Final[str] = "no_sensors_found"
CONF_REAUTH_CONFIRM: Final[str] = "reauth_confirm"
CONF_REAUTH_SUCCESSFUL: Final[str] = "reauth_successful"
CONF_RECONFIGURE_SUCCESSFUL: Final[str] = "reconfigure_successful"
CONF_RECONFIGURE: Final[str] = "reconfigure"
CONF_SELECT_SENSOR: Final[str] = "select_sensor"
CONF_SENSOR_INDEX: Final[str] = "sensor_index"
CONF_SENSOR_READ_KEY: Final[str] = "sensor_read_key"
CONF_SENSOR: Final[str] = "sensor"
CONF_SETTINGS: Final[str] = "settings"
CONF_UNKNOWN: Final[str] = "unknown"
CONF_WRONG_KEY_TYPE: Final[str] = "wrong_key_type"

# API key types returned by /v1/keys (Field api_key_type).
KEY_TYPE_READ: Final[str] = "READ"
KEY_TYPE_WRITE: Final[str] = "WRITE"
KEY_TYPE_READ_DISABLED: Final[str] = "READ_DISABLED"
KEY_TYPE_WRITE_DISABLED: Final[str] = "WRITE_DISABLED"

# PurpleAir charges API points per field per sensor per call. Splitting the
# fields into a static set (fetched once every 24 h) and a dynamic set
# (fetched every 5 min) avoids paying for values that do not change between
# readings. See the "API points and field selection" section in the README
# for the per-day point-cost breakdown.

# STATIC_DEVICE_FIELDS describe the physical sensor and only change on
# firmware updates, user renames on the PurpleAir map, or sensor relocation.
# Populated into DeviceInfo on first refresh and cached on the coordinator;
# re-fetched every STATIC_REFRESH_INTERVAL. Reloading the config entry
# forces an immediate re-fetch for users who updated firmware or moved
# their sensor and don't want to wait for the daily cycle.
STATIC_DEVICE_FIELDS: Final[list[str]] = [
    "name",
    "hardware",
    "model",
    "firmware_version",
    "latitude",
    "longitude",
]

# AVAILABILITY_FIELDS drive entity availability checks (stale last_seen, low
# confidence, no-PM channel_state). Cheap but must be fresh every refresh.
AVAILABILITY_FIELDS: Final[list[str]] = [
    "last_seen",
    "confidence",
    "channel_state",
    "channel_flags",
]

# BASE_FIELDS is the union of the two sets above. It is only used by the
# subentry-validation flow in config_flow.py, where a single request has to
# both prove the sensor exists (static fields) and test read_key / API
# health (availability fields). On the coordinator's repeated refreshes
# STATIC_DEVICE_FIELDS and AVAILABILITY_FIELDS are requested separately.
BASE_FIELDS: Final[list[str]] = STATIC_DEVICE_FIELDS + AVAILABILITY_FIELDS
