"""PurpleAir sensor tests."""

from datetime import datetime, timedelta
import logging
from math import nan
from types import MappingProxyType, SimpleNamespace
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

from custom_components.purpleair.const import (
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
)
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
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_SHOW_ON_MAP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2, TEST_SENSOR_INDEX_NO_LOCATION


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
    assert device.model == "PA-II-ZEN"
    assert device.name == "Test Sensor"
    assert (
        device.hw_version
        == "3.0+OPENLOG+NO-DISK+RV3028+BME68X+KX122+PMSX003-A+PMSX003-B"
    )
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
    [{CONF_SENSOR_INDEX: TEST_SENSOR_INDEX_NO_LOCATION, CONF_SENSOR_READ_KEY: None}],
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


async def test_voc_entity_created_for_voc_hardware(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """BME68X hardware → VOC entity is created and value flows through.

    Asserting state, not just registration, guards against a regression where
    the entity exists in the registry but ``value_fn`` returns ``None``.
    """
    entry = entity_registry.async_get(
        "sensor.test_sensor_volatile_organic_compounds_iaq"
    )
    assert entry is not None
    entity_registry.async_update_entity(entry.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == "42.5"


@pytest.mark.parametrize(
    "config_subentry_data",
    [{CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None}],
)
async def test_voc_entity_skipped_for_no_voc_hardware(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """BME280 hardware → VOC entity is not created.

    Look-up is by ``unique_id`` rather than ``entity_id``: VOC's
    ``translation_key`` slugifies the entity_id, so a literal entity_id
    assertion would silently pass on regression.
    """
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SENSOR_INDEX2}-voc"
        )
        is None
    )
    # Sibling check — guards against a setup-failure regression.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SENSOR_INDEX2}-temperature"
        )
        is not None
    )


@pytest.mark.parametrize(
    "config_subentry_data",
    [{CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None}],
)
@pytest.mark.parametrize(
    "pre_seed_disabled_by",
    [
        None,
        er.RegistryEntryDisabler.INTEGRATION,
        er.RegistryEntryDisabler.USER,
    ],
    ids=["enabled", "integration_disabled", "user_disabled"],
)
async def test_voc_entity_preserved_on_upgrade_for_no_voc_hardware(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    api,
    entity_registry: er.EntityRegistry,
    mock_aiopurpleair,
    pre_seed_disabled_by,
) -> None:
    """Pre-seeded VOC entries on no-VOC hardware survive upgrade in any disabled_by state.

    INTEGRATION-disabled is the common upgrade state since VOC ships disabled
    by default; covering all three states (None, INTEGRATION, USER) pins the
    contract that the gate's existing-registry bypass preserves the row's
    ``disabled_by`` value verbatim and keeps a live entity behind enabled rows.
    """
    pre_seeded = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-voc",
        config_entry=config_entry,
        config_subentry_id=config_subentry.subentry_id,
        original_name="Volatile organic compounds (IAQ)",
        disabled_by=pre_seed_disabled_by,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    after = entity_registry.async_get(pre_seeded.entity_id)
    assert after is not None
    # Registry entry preserved with the same disabled_by state.
    assert after.disabled_by is pre_seed_disabled_by
    # Live entity only present when the entry was enabled.
    if pre_seed_disabled_by is None:
        assert hass.states.get(pre_seeded.entity_id) is not None
    else:
        assert hass.states.get(pre_seeded.entity_id) is None


async def test_voc_entity_gating_per_subentry_in_mixed_hardware_entry(
    hass: HomeAssistant,
    config_entry,
    api,
    entity_registry: er.EntityRegistry,
    mock_aiopurpleair,
) -> None:
    """Mixed-hardware entry: per-subentry VOC gate uses each sensor's own hardware.

    Two subentries on one entry (123456 BME68X, 567890 BME280) — guards
    against a regression that hoists hardware out of the per-subentry loop
    and applies one sensor's value to the whole entry.
    """
    for sensor_index in (TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2):
        hass.config_entries.async_add_subentry(
            config_entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {CONF_SENSOR_INDEX: sensor_index, CONF_SENSOR_READ_KEY: None}
                ),
                subentry_type=CONF_SENSOR,
                title=f"sensor {sensor_index}",
                unique_id=str(sensor_index),
            ),
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # BME68X sensor: VOC entity created.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SENSOR_INDEX1}-voc"
        )
        is not None
    )
    # BME280 sensor: VOC entity skipped.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SENSOR_INDEX2}-voc"
        )
        is None
    )


@pytest.mark.parametrize(
    "config_subentry_data",
    [{CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2, CONF_SENSOR_READ_KEY: None}],
)
async def test_voc_entity_can_be_enabled_after_upgrade_on_no_voc_hardware(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    api,
    entity_registry: er.EntityRegistry,
    mock_aiopurpleair,
) -> None:
    """Re-enabling a pre-seeded INTEGRATION-disabled VOC entry surfaces a live entity.

    Pins the ``existing_unique_ids`` bypass contract: even though the gate
    would normally skip VOC creation on BME280 hardware, a pre-existing
    registry row makes ``async_setup_entry`` create the entity object
    anyway. Without that, re-enabling the row post-upgrade would leave it
    orphaned with no live state.
    """
    pre_seeded = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-voc",
        config_entry=config_entry,
        config_subentry_id=config_subentry.subentry_id,
        original_name="Volatile organic compounds (IAQ)",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Initially disabled → no state.
    assert hass.states.get(pre_seeded.entity_id) is None
    # User clears disabled_by; reload picks up the now-enabled entity.
    entity_registry.async_update_entity(pre_seeded.entity_id, disabled_by=None)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(pre_seeded.entity_id) is not None


async def test_voc_entity_skipped_when_hardware_unknown(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    api,
    get_sensors_response,
    entity_registry: er.EntityRegistry,
    mock_aiopurpleair,
) -> None:
    """``hardware=None`` → gate fails closed, VOC entity not created.

    Failing closed for ``entity_registry_enabled_default=False`` gated
    entities is preferable: a transient miss self-heals on next setup,
    whereas failing open would permanently register an orphan entity on
    every truly no-VOC device that the user would have to clean up.
    """
    original = get_sensors_response.data[TEST_SENSOR_INDEX1]
    no_hw_sensor = original.model_copy(update={"hardware": None})
    no_hw_response = get_sensors_response.model_copy(
        update={
            "data": {
                **get_sensors_response.data,
                TEST_SENSOR_INDEX1: no_hw_sensor,
            }
        }
    )

    async def _stub(*_args, **kwargs):
        indices = kwargs.get("sensor_indices")
        if not indices:
            return no_hw_response
        return no_hw_response.model_copy(
            update={
                "data": {
                    idx: sensor
                    for idx, sensor in no_hw_response.data.items()
                    if idx in indices
                }
            }
        )

    api.sensors.async_get_sensors = AsyncMock(side_effect=_stub)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{TEST_SENSOR_INDEX1}-voc"
        )
        is None
    )


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
        # Confidence is only gated when both PM channels are reporting; the
        # fixture defaults channel_state to None, so set it explicitly here.
        bad_sensor = original.model_copy(
            update={
                "channel_state": ChannelState.PM_A_PM_B,
                "confidence": 10,
            }
        )
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


@pytest.mark.parametrize(
    "single_channel_state",
    [ChannelState.PM_A, ChannelState.PM_B],
)
async def test_low_confidence_does_not_gate_single_channel_sensors(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    api,
    get_sensors_response,
    freezer,
    single_channel_state,
) -> None:
    """Single-channel sensors keep working despite low confidence.

    PA-I and downgraded-channel sensors report low confidence by definition
    because there's no second channel to cross-check against. The
    availability rule must only gate on confidence when both PM channels are
    reporting (PM-A+PM-B); otherwise indoor PA-I sensors get marked
    unavailable even when they're working fine.
    """
    assert hass.states.get("sensor.test_sensor_temperature") is not None

    original = get_sensors_response.data[TEST_SENSOR_INDEX1]
    single_channel_sensor = original.model_copy(
        update={
            "channel_state": single_channel_state,
            "confidence": 30,  # below MIN_CONFIDENCE; would gate if both channels
        }
    )
    response = get_sensors_response.model_copy(
        update={
            "data": {
                **get_sensors_response.data,
                TEST_SENSOR_INDEX1: single_channel_sensor,
            }
        }
    )
    api.sensors.async_get_sensors = AsyncMock(return_value=response)

    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_temperature")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_last_seen_renders_as_tz_aware_timestamp(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    api,
    get_sensors_response,
    freezer,
) -> None:
    """`Last seen` entity must render as a tz-aware ISO timestamp, not unavailable.

    HA's TIMESTAMP-class `SensorEntity` forces state to STATE_UNAVAILABLE when
    given a tz-naive `datetime`. The aiopurpleair fork was returning naive
    datetimes (fixed in 2026.5.0), which made the Last seen entity silently
    unavailable on every device while every sibling kept reporting fresh
    values. This test pins the rendered state, not just the SensorModel field,
    so a future library swap that reintroduces tz-naive datetimes is caught
    here instead of surfacing as a broken HA entity.

    The construction goes through `SensorModel.model_validate` with `last_seen`
    as an int so the upstream `validate_timestamp` validator runs — without
    that, the test would bypass the bug entirely.
    """
    from datetime import UTC  # noqa: PLC0415

    from aiopurpleair.models.sensors import SensorModel  # noqa: PLC0415

    original = get_sensors_response.data[TEST_SENSOR_INDEX1]
    last_seen_epoch = 1762147200  # 2025-11-03 04:00:00 UTC
    sensor_with_last_seen = SensorModel.model_validate(
        {
            **original.model_dump(by_alias=True, exclude_none=True),
            "last_seen": last_seen_epoch,
        }
    )
    # Sanity check: the upstream validator must produce a tz-aware datetime.
    assert sensor_with_last_seen.last_seen_utc is not None
    assert sensor_with_last_seen.last_seen_utc.tzinfo is not None, (
        "aiopurpleair regression: validate_timestamp returned a naive datetime "
        "(would force HA TIMESTAMP entity to STATE_UNAVAILABLE)"
    )

    patched_response = get_sensors_response.model_copy(
        update={
            "data": {
                **get_sensors_response.data,
                TEST_SENSOR_INDEX1: sensor_with_last_seen,
            },
            # Set data_timestamp_utc near the new last_seen so the staleness
            # gate doesn't fire (default fixture timestamp is 2022). Must be
            # tz-aware to match last_seen_utc — the staleness gate subtracts
            # the two and Python rejects naive/aware mixing.
            "data_timestamp_utc": datetime(2025, 11, 3, 4, 5, 0, tzinfo=UTC),
        }
    )
    api.sensors.async_get_sensors = AsyncMock(return_value=patched_response)

    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_sensor_last_seen")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE, (
        "Last seen entity unavailable — likely a tz-naive datetime "
        "regression in aiopurpleair. Expected a tz-aware ISO timestamp."
    )
    # HA renders TIMESTAMP-class state as ISO 8601 with a tz suffix
    # ("+00:00" for UTC). Confirm the offset is present so we know we got
    # a real tz-aware datetime through the whole pipeline.
    assert "+00:00" in state.state, (
        f"Expected tz-aware ISO 8601 string ending in +00:00, got {state.state!r}"
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
    assert entity._maybe_sensor_data() is None
    entity._refresh_device_info()


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

    assert entity._is_sensor_healthy() is True
    assert entity._unhealthy_reason() == "unknown"


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


def test_organization_sensor_default_enablement() -> None:
    """Pin the documented default-enabled state for each org diagnostic sensor."""
    defaults = {
        desc.key: desc.entity_registry_enabled_default
        for desc in ORGANIZATION_SENSOR_DESCRIPTIONS
    }
    assert defaults == {"remaining_points": True, "consumption_rate": True}


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
