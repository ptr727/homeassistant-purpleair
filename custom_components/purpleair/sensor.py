"""Support for PurpleAir sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from aiopurpleair.const import ChannelFlag, ChannelState
from aiopurpleair.models.organizations import GetOrganizationResponse
from aiopurpleair.models.sensors import SensorModel

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SENSOR_INDEX, DOMAIN
from .coordinator import PurpleAirConfigEntry, PurpleAirOrganizationCoordinator
from .entity import MANUFACTURER, PurpleAirEntity

# PARALLEL_UPDATES = 0 is the Home Assistant convention for coordinator-backed
# read-only platforms: the coordinator fans out a single API response to every
# entity, so there is no per-entity request to serialise. A non-zero value
# would throttle entity state updates without touching API traffic, which is
# exactly the wrong trade-off here. Required by the `parallel-updates` rule of
# the Silver quality scale — see
# https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates/
PARALLEL_UPDATES = 0

CONCENTRATION_PARTICLES_PER_100_MILLILITERS: Final[str] = (
    f"particles/100{UnitOfVolume.MILLILITERS}"
)

CHANNEL_STATE_OPTIONS: Final[list[str]] = [
    "no_pm",
    "pm_a",
    "pm_b",
    "pm_a_pm_b",
]

CHANNEL_FLAGS_OPTIONS: Final[list[str]] = [
    "normal",
    "a_downgraded",
    "b_downgraded",
    "a_b_downgraded",
]


def _pm25_epa_correction(sensor: SensorModel) -> float | None:
    """Return the EPA-corrected PM2.5 for this sensor, or None if inputs are missing.

    Implements the piecewise correction published by the US EPA for PurpleAir
    PM2.5 data. Reference: "Fire and Smoke Map Sensor Data Processing",
    EPA Office of Research and Development, revised 2021, page 26 of
    https://cfpub.epa.gov/si/si_public_record_report.cfm?dirEntryId=353088&Lab=CEMM

    The formula is designed for **outdoor** sensors and expects the raw
    ATM PM2.5 concentration. We use the PurpleAir ``pm2.5`` field which the
    real-time API auto-selects to the ATM variant for outdoor sensors and
    excludes downgraded channels (see the API docs at
    https://api.purpleair.com/#api-sensors-get-sensor-data - "pm2.5"). For
    indoor sensors the correction is not meaningful.

    Piecewise (PM is raw µg/m³, RH is raw %)::

        PM <  30:   0.524·PM − 0.0862·RH + 5.75
        30 ≤ PM <  50:  blended transition from the <30 to the 50–210 form
        50 ≤ PM < 210:  0.786·PM − 0.0862·RH + 5.75
        210 ≤ PM < 260: blended transition from the 50–210 to the ≥260 form
        PM ≥ 260:  2.966 + 0.69·PM + 8.84e-4·PM²

    The transition regions linearly blend the two adjacent formulas so that
    the corrected value is continuous across breakpoints. The EPA
    document notes that the humidity input uses the sensor's internal
    humidity as-is (the regression was fit against the housing-internal
    BME280 readings), so we do **not** apply the ~4 % RH offset that
    approximates ambient humidity.
    """
    pm = sensor.pm2_5
    rh = sensor.humidity
    if pm is None or rh is None:
        return None
    if pm < 30:
        return 0.524 * pm - 0.0862 * rh + 5.75
    if pm < 50:
        # Blend coefficient: 0 at PM=30, 1 at PM=50.
        # Form: t = PM/20 − 3/2 → t=0 at 30, t=1 at 50.
        t = pm / 20 - 3 / 2
        return (0.786 * t + 0.524 * (1 - t)) * pm - 0.0862 * rh + 5.75
    if pm < 210:
        return 0.786 * pm - 0.0862 * rh + 5.75
    if pm < 260:
        # Blend coefficient: t = PM/50 − 21/5 → t=0 at 210, t=1 at 260.
        t = pm / 50 - 21 / 5
        return (
            (0.69 * t + 0.786 * (1 - t)) * pm
            - 0.0862 * rh * (1 - t)
            + 2.966 * t
            + 5.75 * (1 - t)
            + 8.84e-4 * t * pm * pm
        )
    return 2.966 + 0.69 * pm + 8.84e-4 * pm * pm


# US EPA AQI breakpoints for PM2.5 24-hour average (µg/m³) → AQI value.
# Current NAAQS (effective 2024-05-06): the "Good/Moderate" threshold was
# lowered from 12.0 to 9.0 µg/m³ to reflect the revised annual standard of
# 9 µg/m³ and stricter protective recommendations. Higher breakpoints were
# also tightened. Source: AirNow "About the AQI" and 40 CFR § 58 Appendix
# G, as updated in the 2024 Final Rule on the PM NAAQS.
# Tuples are (concentration_low, concentration_high, aqi_low, aqi_high).
_AQI_BREAKPOINTS: Final[tuple[tuple[float, float, int, int], ...]] = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 500.4, 301, 500),
)


def _pm25_aqi(sensor: SensorModel) -> int | None:
    """Return the US EPA AQI for this sensor's 24-hour PM2.5 average.

    Uses the piecewise-linear interpolation defined in 40 CFR § 58 Appendix
    G: within a concentration bucket, AQI is linearly interpolated between
    the bucket's AQI endpoints. See also AirNow's "Air Quality Index (AQI)
    Basics" at https://www.airnow.gov/aqi/aqi-basics/ and the PurpleAir
    API docs for ``pm2.5_24hour`` at
    https://api.purpleair.com/#api-sensors-get-sensor-data.

    Values above the 500.4 µg/m³ top of the Hazardous band cap at AQI 500.
    """
    pm = sensor.pm2_5_24hour
    if pm is None or pm < 0:
        return None
    # Per 40 CFR § 58 App. G, PM2.5 is truncated to 0.1 µg/m³ before AQI
    # lookup so that the 9.0/9.1-style boundaries are unambiguous.
    pm = int(pm * 10) / 10
    if pm > 500.4:
        return 500
    for c_lo, c_hi, i_lo, i_hi in _AQI_BREAKPOINTS:
        if c_lo <= pm <= c_hi:
            return round((i_hi - i_lo) / (c_hi - c_lo) * (pm - c_lo) + i_lo)
    return None


_CHANNEL_STATE_TO_OPTION: Final[dict[ChannelState, str]] = {
    ChannelState.NO_PM: "no_pm",
    ChannelState.PM_A: "pm_a",
    ChannelState.PM_B: "pm_b",
    ChannelState.PM_A_PM_B: "pm_a_pm_b",
}

_CHANNEL_FLAG_TO_OPTION: Final[dict[ChannelFlag, str]] = {
    ChannelFlag.NORMAL: "normal",
    ChannelFlag.A_DOWNGRADED: "a_downgraded",
    ChannelFlag.B_DOWNGRADED: "b_downgraded",
    ChannelFlag.A_B_DOWNGRADED: "a_b_downgraded",
}


def _channel_state_value(sensor: SensorModel) -> str | None:
    """Map a channel_state enum to its translation key."""
    if sensor.channel_state is None:
        return None
    return _CHANNEL_STATE_TO_OPTION.get(sensor.channel_state)


def _channel_flags_value(sensor: SensorModel) -> str | None:
    """Map a channel_flags enum to its translation key."""
    if sensor.channel_flags is None:
        return None
    return _CHANNEL_FLAG_TO_OPTION.get(sensor.channel_flags)


@dataclass(frozen=True, kw_only=True)
class PurpleAirSensorEntityDescription(SensorEntityDescription):
    """Describe a PurpleAir sensor entity.

    ``api_fields`` lists the on-wire PurpleAir v1 field names required to populate
    this entity. They are only added to the outgoing ``fields`` parameter while at
    least one instance of this description is enabled in the entity registry, so
    disabled entities cost zero API points.
    """

    value_fn: Callable[[SensorModel], float | str | datetime | None]
    api_fields: tuple[str, ...] = field(default_factory=tuple)


SENSOR_DESCRIPTIONS: Final[tuple[PurpleAirSensorEntityDescription, ...]] = (
    PurpleAirSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.humidity,
        api_fields=("humidity",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm0.3_count_concentration",
        translation_key="pm0_3_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm0_3_um_count,
        api_fields=("0.3_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm0.5_count_concentration",
        translation_key="pm0_5_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm0_5_um_count,
        api_fields=("0.5_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm1.0_count_concentration",
        translation_key="pm1_0_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm1_0_um_count,
        api_fields=("1.0_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm1.0_mass_concentration",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm1_0,
        api_fields=("pm1.0",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm10.0_count_concentration",
        translation_key="pm10_0_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm10_0_um_count,
        api_fields=("10.0_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm10.0_mass_concentration",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm10_0,
        api_fields=("pm10.0",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_count_concentration",
        translation_key="pm2_5_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_um_count,
        api_fields=("2.5_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_mass_concentration",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5,
        api_fields=("pm2.5",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm5.0_count_concentration",
        translation_key="pm5_0_count_concentration",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTICLES_PER_100_MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm5_0_um_count,
        api_fields=("5.0_um_count",),
    ),
    PurpleAirSensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pressure,
        api_fields=("pressure",),
    ),
    PurpleAirSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.rssi,
        api_fields=("rssi",),
    ),
    PurpleAirSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.temperature,
        api_fields=("temperature",),
    ),
    PurpleAirSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda sensor: sensor.uptime,
        api_fields=("uptime",),
    ),
    PurpleAirSensorEntityDescription(
        key="voc",
        translation_key="voc_iaq",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.voc,
        api_fields=("voc",),
    ),
    # --- Phase 2 opt-in diagnostics (disabled by default) ---
    PurpleAirSensorEntityDescription(
        key="pm2.5_alt_mass_concentration",
        translation_key="pm2_5_alt_mass_concentration",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_alt,
        api_fields=("pm2.5_alt",),
    ),
    # Derived: US EPA-corrected PM2.5 mass concentration. See the docstring of
    # _pm25_epa_correction above for the formula and citation.
    PurpleAirSensorEntityDescription(
        key="pm2.5_epa_mass_concentration",
        translation_key="pm2_5_epa_mass_concentration",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_pm25_epa_correction,
        # The EPA correction requires both the raw ATM PM2.5 and the raw
        # relative humidity. Declaring both as api_fields means that
        # enabling this sensor alone will pull both fields even if the
        # user has disabled the baseline PM2.5 and humidity entities.
        api_fields=("pm2.5", "humidity"),
    ),
    # Derived: US EPA AQI from the 24-hour PM2.5 average. See the docstring
    # of _pm25_aqi above for the formula, breakpoint source, and the 2024
    # NAAQS update.
    PurpleAirSensorEntityDescription(
        key="pm2.5_aqi",
        translation_key="pm2_5_aqi",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_pm25_aqi,
        api_fields=("pm2.5_24hour",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_10minute",
        translation_key="pm2_5_10minute",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_10minute,
        api_fields=("pm2.5_10minute",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_30minute",
        translation_key="pm2_5_30minute",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_30minute,
        api_fields=("pm2.5_30minute",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_60minute",
        translation_key="pm2_5_60minute",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_60minute,
        api_fields=("pm2.5_60minute",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_6hour",
        translation_key="pm2_5_6hour",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_6hour,
        api_fields=("pm2.5_6hour",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_24hour",
        translation_key="pm2_5_24hour",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_24hour,
        api_fields=("pm2.5_24hour",),
    ),
    PurpleAirSensorEntityDescription(
        key="pm2.5_1week",
        translation_key="pm2_5_1week",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pm2_5_1week,
        api_fields=("pm2.5_1week",),
    ),
    PurpleAirSensorEntityDescription(
        key="confidence",
        translation_key="confidence",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.confidence,
    ),
    PurpleAirSensorEntityDescription(
        key="channel_state",
        translation_key="channel_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=CHANNEL_STATE_OPTIONS,
        value_fn=_channel_state_value,
    ),
    PurpleAirSensorEntityDescription(
        key="channel_flags",
        translation_key="channel_flags",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=CHANNEL_FLAGS_OPTIONS,
        value_fn=_channel_flags_value,
    ),
    PurpleAirSensorEntityDescription(
        key="last_seen",
        translation_key="last_seen",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sensor: sensor.last_seen_utc,
    ),
    PurpleAirSensorEntityDescription(
        key="temperature_internal",
        translation_key="temperature_internal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.temperature,
        api_fields=("temperature",),
    ),
    PurpleAirSensorEntityDescription(
        key="humidity_internal",
        translation_key="humidity_internal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.humidity,
        api_fields=("humidity",),
    ),
    PurpleAirSensorEntityDescription(
        key="pressure_internal",
        translation_key="pressure_internal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sensor: sensor.pressure,
        api_fields=("pressure",),
    ),
)


DESCRIPTIONS_BY_KEY: Final[dict[str, PurpleAirSensorEntityDescription]] = {
    desc.key: desc for desc in SENSOR_DESCRIPTIONS
}


@dataclass(frozen=True, kw_only=True)
class PurpleAirOrganizationSensorEntityDescription(SensorEntityDescription):
    """Describe an account-level (organization) PurpleAir sensor entity."""

    value_fn: Callable[[GetOrganizationResponse], int | str | None]


ORGANIZATION_SENSOR_DESCRIPTIONS: Final[
    tuple[PurpleAirOrganizationSensorEntityDescription, ...]
] = (
    PurpleAirOrganizationSensorEntityDescription(
        key="remaining_points",
        translation_key="remaining_points",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="points",
        value_fn=lambda response: response.remaining_points,
    ),
    PurpleAirOrganizationSensorEntityDescription(
        key="consumption_rate",
        translation_key="consumption_rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="points/d",
        value_fn=lambda response: response.consumption_rate,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PurpleAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PurpleAir sensors based on a config entry."""
    for subentry in entry.subentries.values():
        async_add_entities(
            (
                PurpleAirSensorEntity(
                    entry, int(subentry.data[CONF_SENSOR_INDEX]), description
                )
                for description in SENSOR_DESCRIPTIONS
            ),
            update_before_add=False,
            config_subentry_id=subentry.subentry_id,
        )

    async_add_entities(
        PurpleAirOrganizationSensorEntity(entry, description)
        for description in ORGANIZATION_SENSOR_DESCRIPTIONS
    )


class PurpleAirSensorEntity(PurpleAirEntity, SensorEntity):
    """Define a representation of a PurpleAir sensor."""

    entity_description: PurpleAirSensorEntityDescription

    def __init__(
        self,
        entry: PurpleAirConfigEntry,
        sensor_index: int,
        description: PurpleAirSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry, sensor_index)

        self._attr_unique_id = f"{sensor_index}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        sensor = self._maybe_sensor_data()
        if sensor is None:
            return None
        return self.entity_description.value_fn(sensor)


class PurpleAirOrganizationSensorEntity(
    CoordinatorEntity[PurpleAirOrganizationCoordinator], SensorEntity
):
    """Define an account-level PurpleAir sensor (remaining points / consumption rate)."""

    _attr_has_entity_name = True
    entity_description: PurpleAirOrganizationSensorEntityDescription

    def __init__(
        self,
        entry: PurpleAirConfigEntry,
        description: PurpleAirOrganizationSensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data.organization)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-organization-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"organization-{entry.entry_id}")},
            manufacturer=MANUFACTURER,
            name=f"{entry.title} organization",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | str | None:
        """Return the value of the entity."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
