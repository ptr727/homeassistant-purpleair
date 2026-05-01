"""PurpleAir sensor tests."""

from datetime import datetime, timedelta
import logging
from math import nan
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiopurpleair.const import ChannelFlag, ChannelState
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy import SnapshotAssertion

from custom_components.purpleair.const import DOMAIN
from custom_components.purpleair.coordinator import UPDATE_INTERVAL
from custom_components.purpleair.sensor import (
    CHANNEL_FLAGS_OPTIONS,
    CHANNEL_STATE_OPTIONS,
    ORGANIZATION_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    PurpleAirOrganizationSensorEntity,
    PurpleAirSensorEntity,
    _channel_flags_value,
    _channel_state_value,
    _pm25_aqi,
    _pm25_epa_correction,
)
from homeassistant.components.sensor import UnitOfTemperature
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_SHOW_ON_MAP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX_NO_LOCATION


async def test_sensor_snapshot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every entity created for a sensor subentry.

    snapshot_platform requires all entities be enabled; the PM counts,
    RSSI and uptime are disabled by default, so re-enable them before
    snapshotting.
    """
    for entry in list(
        er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    ):
        if entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_sensor_temperature_value(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """Spot-check a single value passes through the value_fn and unit conversion."""
    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.state == "27.7777777777778"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS


async def test_sensor_unique_ids(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unique IDs follow the {sensor_index}-{key} contract."""
    entry = entity_registry.async_get("sensor.test_sensor_temperature")
    assert entry is not None
    assert entry.unique_id == f"{TEST_SENSOR_INDEX1}-temperature"


async def test_sensor_device_info(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Device info is populated from the API response."""
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))}
    )
    assert device is not None
    assert device.manufacturer == "PurpleAir, Inc."
    assert device.model == "PA-II"
    assert device.name == "Test Sensor"
    assert device.hw_version == "2.0+BME280+PMSX003-B+PMSX003-A"
    assert device.sw_version == "7.02"
    assert device.configuration_url == "http://example.com"


async def test_show_on_map_enabled_adds_location_attrs(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """With show_on_map on and valid coords, latitude/longitude are exposed."""
    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.attributes[ATTR_LATITUDE] == pytest.approx(51.5285582)
    assert state.attributes[ATTR_LONGITUDE] == pytest.approx(-0.2416796)


@pytest.mark.parametrize("config_entry_options", [{CONF_SHOW_ON_MAP: False}])
async def test_show_on_map_disabled_omits_location_attrs(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """When show_on_map is off, location attributes are absent."""
    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes


@pytest.mark.parametrize(
    "config_subentry_data",
    [{"sensor_index": TEST_SENSOR_INDEX_NO_LOCATION, "sensor_read_key": None}],
)
async def test_sensor_without_location_omits_attrs_even_when_show_on_map(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
) -> None:
    """A sensor with null lat/lon never exposes location attributes."""
    state = hass.states.get("sensor.test_sensor_3_temperature")
    assert state is not None
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes


@pytest.mark.parametrize(
    ("pm", "rh", "expected"),
    [
        # <30 formula: 0.524·PM − 0.0862·RH + 5.75
        (0.0, 0.0, 5.75),
        (10.0, 50.0, 0.524 * 10 - 0.0862 * 50 + 5.75),
        (29.9, 50.0, 0.524 * 29.9 - 0.0862 * 50 + 5.75),
        # 50–210 formula: 0.786·PM − 0.0862·RH + 5.75
        (50.0, 50.0, 0.786 * 50 - 0.0862 * 50 + 5.75),
        (150.0, 50.0, 0.786 * 150 - 0.0862 * 50 + 5.75),
        (209.9, 50.0, 0.786 * 209.9 - 0.0862 * 50 + 5.75),
        # ≥260 formula: 2.966 + 0.69·PM + 8.84e-4·PM²
        (260.0, 50.0, 2.966 + 0.69 * 260 + 8.84e-4 * 260 * 260),
        (500.0, 50.0, 2.966 + 0.69 * 500 + 8.84e-4 * 500 * 500),
    ],
)
def test_pm25_epa_correction_formula(pm: float, rh: float, expected: float) -> None:
    """Verify the EPA formula at each piecewise branch's interior."""
    sensor = SimpleNamespace(pm2_5=pm, humidity=rh)
    assert _pm25_epa_correction(sensor) == pytest.approx(expected, rel=1e-6)


def test_pm25_epa_correction_transition_is_continuous() -> None:
    """The 30↔50 and 210↔260 transitions must be continuous.

    At PM=30 the <30 and blended forms must agree; at PM=50 the blended and
    50–210 forms must agree; likewise at 210 and 260.
    """
    # PM just below 30 vs at 30 should be very close.
    lower = _pm25_epa_correction(SimpleNamespace(pm2_5=29.9999, humidity=50))
    upper = _pm25_epa_correction(SimpleNamespace(pm2_5=30.0, humidity=50))
    assert lower == pytest.approx(upper, rel=1e-3)

    # PM at 50 from the blended form must match the 50–210 form at 50.
    lower = _pm25_epa_correction(SimpleNamespace(pm2_5=49.9999, humidity=50))
    upper = _pm25_epa_correction(SimpleNamespace(pm2_5=50.0, humidity=50))
    assert lower == pytest.approx(upper, rel=1e-3)

    # PM at 210 from the 50–210 form must match the blended form at 210.
    lower = _pm25_epa_correction(SimpleNamespace(pm2_5=209.9999, humidity=50))
    upper = _pm25_epa_correction(SimpleNamespace(pm2_5=210.0, humidity=50))
    assert lower == pytest.approx(upper, rel=1e-3)

    # PM at 260 from the blended form must match the ≥260 form.
    lower = _pm25_epa_correction(SimpleNamespace(pm2_5=259.9999, humidity=50))
    upper = _pm25_epa_correction(SimpleNamespace(pm2_5=260.0, humidity=50))
    assert lower == pytest.approx(upper, rel=1e-3)


def test_pm25_epa_correction_missing_inputs() -> None:
    """Either pm2_5 or humidity being None yields None."""
    assert _pm25_epa_correction(SimpleNamespace(pm2_5=None, humidity=50)) is None
    assert _pm25_epa_correction(SimpleNamespace(pm2_5=10, humidity=None)) is None


@pytest.mark.parametrize(
    ("pm", "expected"),
    [
        (None, None),
        (-1.0, None),
        (0.0, 0),  # AQI 0 at 0 µg/m³
        (9.0, 50),  # Top of Good
        (9.1, 51),  # Bottom of Moderate
        (35.4, 100),  # Top of Moderate
        (35.5, 101),  # Bottom of USG
        (55.4, 150),  # Top of USG
        (55.5, 151),  # Bottom of Unhealthy
        (125.4, 200),  # Top of Unhealthy
        (125.5, 201),  # Bottom of Very Unhealthy
        (225.4, 300),  # Top of Very Unhealthy
        (225.5, 301),  # Bottom of Hazardous
        (500.4, 500),  # Top of Hazardous
        (750.0, 500),  # Beyond the scale — cap at 500
    ],
)
def test_pm25_aqi_breakpoints(pm: float | None, expected: int | None) -> None:
    """Verify the AQI formula at every breakpoint edge."""
    assert _pm25_aqi(SimpleNamespace(pm2_5_24hour=pm)) == expected


def test_pm25_aqi_truncates_to_tenth() -> None:
    """Concentrations between reported precisions truncate to 0.1 µg/m³.

    9.05 is not meaningful per 40 CFR; it should behave as 9.0, i.e. AQI 50
    (top of the Good band), not 51 (which would imply it's in Moderate).
    """
    assert _pm25_aqi(SimpleNamespace(pm2_5_24hour=9.05)) == 50


def test_pm25_aqi_nan_returns_none() -> None:
    """NaN PM2.5 values are treated as invalid and return None."""
    assert _pm25_aqi(SimpleNamespace(pm2_5_24hour=nan)) is None


def test_channel_state_value_helper() -> None:
    """Every ChannelState enum member maps to its translation key."""
    expected_by_member = dict(zip(ChannelState, CHANNEL_STATE_OPTIONS, strict=True))
    for member, expected in expected_by_member.items():
        assert _channel_state_value(SimpleNamespace(channel_state=member)) == expected
    assert _channel_state_value(SimpleNamespace(channel_state=None)) is None


def test_channel_flags_value_helper() -> None:
    """Every ChannelFlag enum member maps to its translation key."""
    expected_by_member = dict(zip(ChannelFlag, CHANNEL_FLAGS_OPTIONS, strict=True))
    for member, expected in expected_by_member.items():
        assert _channel_flags_value(SimpleNamespace(channel_flags=member)) == expected
    assert _channel_flags_value(SimpleNamespace(channel_flags=None)) is None


@pytest.mark.parametrize(
    ("mutate_field", "log_needle"),
    [
        ("confidence", "confidence"),
        ("channel_state", "channel_state"),
        ("last_seen", "last_seen"),
    ],
)
async def test_availability_guards(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    api,
    get_sensors_response,
    freezer,
    caplog,
    mutate_field,
    log_needle,
) -> None:
    """Low confidence, no-PM channel_state, or stale last_seen → unavailable.

    Setting up with good data first means each case triggers a healthy→
    unhealthy transition, which exercises the _unhealthy_reason branches.
    """
    # Good initial state.
    assert hass.states.get("sensor.test_sensor_temperature") is not None

    original = get_sensors_response.data[TEST_SENSOR_INDEX1]
    if mutate_field == "confidence":
        bad_sensor = original.model_copy(update={"confidence": 10})
    elif mutate_field == "channel_state":
        bad_sensor = original.model_copy(update={"channel_state": ChannelState.NO_PM})
    else:  # last_seen
        ref = get_sensors_response.data_timestamp_utc or datetime(2020, 1, 1)
        bad_sensor = original.model_copy(
            update={"last_seen_utc": ref - timedelta(hours=1)}
        )

    bad_response = get_sensors_response.model_copy(
        update={
            "data": {
                **get_sensors_response.data,
                TEST_SENSOR_INDEX1: bad_sensor,
            }
        }
    )
    api.sensors.async_get_sensors = AsyncMock(return_value=bad_response)

    caplog.clear()
    caplog.set_level(logging.INFO, logger="custom_components.purpleair")
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert any(log_needle in record.message for record in caplog.records), (
        f"No log mentioning {log_needle!r}"
    )


async def test_sensor_unavailable_when_missing_from_response(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    api,
    get_sensors_response,
    freezer,
    caplog,
) -> None:
    """Entities become unavailable when the sensor disappears from the API.

    Also verifies the log-when-unavailable rule: exactly one INFO log on the
    transition to unavailable, and one on the transition back.
    """
    # Initial setup succeeds — the sensor is known.
    assert hass.states.get("sensor.test_sensor_temperature") is not None

    # Next refresh returns a response without this sensor.
    stripped = get_sensors_response.model_copy(
        update={
            "data": {
                idx: sensor
                for idx, sensor in get_sensors_response.data.items()
                if idx != TEST_SENSOR_INDEX1
            }
        }
    )
    api.sensors.async_get_sensors = AsyncMock(return_value=stripped)

    caplog.clear()
    caplog.set_level(logging.INFO, logger="custom_components.purpleair")
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    # Entity-level guards: extra_state_attributes and native_value must both
    # short-circuit when the sensor has vanished from the API response.
    assert ATTR_LATITUDE not in state.attributes
    assert ATTR_LONGITUDE not in state.attributes
    n_unavailable_logs = sum(
        "is unavailable" in record.message for record in caplog.records
    )
    # One log per active entity on the transition.
    assert n_unavailable_logs >= 1

    # Second refresh with the same (stripped) response must NOT re-log.
    caplog.clear()
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not any("is unavailable" in record.message for record in caplog.records)

    # Back online — log once again on recovery.
    api.sensors.async_get_sensors = AsyncMock(return_value=get_sensors_response)
    caplog.clear()
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert (
        sum("is back online" in record.message for record in caplog.records)
        == n_unavailable_logs
    )


async def test_entity_helpers_when_coordinator_data_missing(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
) -> None:
    """Base entity helpers must short-circuit cleanly when data is None."""
    description = next(
        desc for desc in SENSOR_DESCRIPTIONS if desc.key == "temperature"
    )
    entity = PurpleAirSensorEntity(config_entry, TEST_SENSOR_INDEX1, description)

    config_entry.runtime_data.sensors.data = None
    assert entity.native_value is None
    assert entity.extra_state_attributes == {}
    assert entity._maybe_sensor_data() is None  # noqa: SLF001
    entity._refresh_device_info()  # noqa: SLF001


async def test_stale_guard_reference_none_keeps_sensor_healthy(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    get_sensors_response,
) -> None:
    """Staleness checks skip when data_timestamp_utc is missing."""
    description = next(
        desc for desc in SENSOR_DESCRIPTIONS if desc.key == "temperature"
    )
    entity = PurpleAirSensorEntity(config_entry, TEST_SENSOR_INDEX1, description)

    stale_like_sensor = get_sensors_response.data[TEST_SENSOR_INDEX1].model_copy(
        update={"last_seen_utc": datetime(2000, 1, 1)}
    )
    config_entry.runtime_data.sensors.data = get_sensors_response.model_copy(
        update={
            "data": {
                **get_sensors_response.data,
                TEST_SENSOR_INDEX1: stale_like_sensor,
            },
            "data_timestamp_utc": None,
        }
    )

    assert entity._is_sensor_healthy() is True  # noqa: SLF001
    assert entity._unhealthy_reason() == "unknown"  # noqa: SLF001


async def test_organization_native_value_none_without_data(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
) -> None:
    """Organization sensor entities return None when coordinator has no data."""
    description = next(
        desc
        for desc in ORGANIZATION_SENSOR_DESCRIPTIONS
        if desc.key == "remaining_points"
    )
    entity = PurpleAirOrganizationSensorEntity(config_entry, description)

    config_entry.runtime_data.organization.data = None
    assert entity.native_value is None


@pytest.mark.parametrize(
    "get_sensors_mock",
    [
        AsyncMock(side_effect=Exception),
        AsyncMock(side_effect=PurpleAirError),
    ],
)
async def test_setup_fails_on_coordinator_error(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    mock_aiopurpleair,
    api,
    get_sensors_mock,
) -> None:
    """Entry goes to SETUP_RETRY on coordinator UpdateFailed."""
    with patch.object(api.sensors, "async_get_sensors", get_sensors_mock):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()

    assert hass.states.get("sensor.test_sensor_temperature") is None


async def test_setup_triggers_reauth_on_invalid_key(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    mock_aiopurpleair,
    api,
) -> None:
    """An InvalidApiKeyError raises ConfigEntryAuthFailed and starts a reauth flow."""
    with patch.object(
        api.sensors,
        "async_get_sensors",
        AsyncMock(side_effect=InvalidApiKeyError),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
        await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"].get("source") == "reauth"
    ]
    assert len(flows) == 1
