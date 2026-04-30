"""Base entity for the PurpleAir integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any, Final

from aiopurpleair.const import ChannelState
from aiopurpleair.models.sensors import SensorModel

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

MANUFACTURER: Final[str] = "PurpleAir, Inc."

# Availability thresholds driven by the PurpleAir v1 API docs.
# - last_seen: sensors report every ~40 s; data can be up to 30 s behind
#   data_time_stamp. 10 min gives comfortable headroom for a missed upload.
# - confidence: 0-100; below 50 means the two PMS channels disagree too much to
#   trust the averaged value.
# - channel_state NO_PM means no PM sensor was detected at all.
STALE_THRESHOLD: Final[timedelta] = timedelta(minutes=10)
MIN_CONFIDENCE: Final[int] = 50


class PurpleAirEntity(CoordinatorEntity[PurpleAirDataUpdateCoordinator]):
    """Define a base PurpleAir entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: PurpleAirConfigEntry,
        sensor_index: int,
    ) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data.sensors)

        self._sensor_index = sensor_index
        self._entry = entry
        self._unavailable_logged = False

        self._attr_device_info = DeviceInfo(
            configuration_url=self.coordinator.async_get_map_url(sensor_index),
            identifiers={(DOMAIN, str(sensor_index))},
            manufacturer=MANUFACTURER,
        )
        self._refresh_device_info()

    @callback
    def _refresh_device_info(self) -> None:
        """Pull hw/sw/name off the latest sensor data if available."""
        sensor = self._maybe_sensor_data()
        if sensor is None:
            return
        assert self._attr_device_info is not None
        self._attr_device_info["hw_version"] = sensor.hardware
        self._attr_device_info["model"] = sensor.model
        self._attr_device_info["name"] = sensor.name
        self._attr_device_info["sw_version"] = sensor.firmware_version

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator.

        The availability predicate here must match the ``available`` property
        exactly — otherwise we can end up logging a "back online" transition
        without having previously logged the "unavailable" side (or vice
        versa) when a coordinator-level failure coincides with healthy
        stale-cached sensor data.
        """
        currently_available = super().available and self._is_sensor_healthy()
        if not currently_available:
            if not self._unavailable_logged:
                LOGGER.info(
                    "Sensor %s is unavailable: %s",
                    self._sensor_index,
                    self._unhealthy_reason(),
                )
                self._unavailable_logged = True
        else:
            if self._unavailable_logged:
                LOGGER.info("Sensor %s is back online", self._sensor_index)
                self._unavailable_logged = False
            self._refresh_device_info()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if the entity has data available."""
        return super().available and self._is_sensor_healthy()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        sensor = self._maybe_sensor_data()
        if sensor is None:
            return {}
        if sensor.latitude is None or sensor.longitude is None:
            # Location is required for the show_on_map attributes.
            return {}
        if not self._entry.options.get(CONF_SHOW_ON_MAP, False):
            return {}
        return {
            ATTR_LATITUDE: sensor.latitude,
            ATTR_LONGITUDE: sensor.longitude,
        }

    def _maybe_sensor_data(self) -> SensorModel | None:
        """Return this entity's SensorModel, or None if it is not in the response."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.data.get(self._sensor_index)

    def _is_sensor_healthy(self) -> bool:
        """Check every availability rule: returns False if any fails."""
        sensor = self._maybe_sensor_data()
        if sensor is None:
            return False
        if sensor.confidence is not None and sensor.confidence < MIN_CONFIDENCE:
            return False
        if sensor.channel_state is ChannelState.NO_PM:
            return False
        if sensor.last_seen_utc is not None and self.coordinator.data is not None:
            reference = self.coordinator.data.data_timestamp_utc
            if (
                reference is not None
                and (reference - sensor.last_seen_utc) > STALE_THRESHOLD
            ):
                return False
        return True

    def _unhealthy_reason(self) -> str:
        """One-line description of why the sensor is unhealthy (for logs)."""
        sensor = self._maybe_sensor_data()
        if sensor is None:
            return "not present in API response"
        if sensor.confidence is not None and sensor.confidence < MIN_CONFIDENCE:
            return f"confidence {sensor.confidence} below {MIN_CONFIDENCE}"
        if sensor.channel_state is ChannelState.NO_PM:
            return "no PM channel detected (channel_state=NO_PM)"
        if sensor.last_seen_utc is not None and self.coordinator.data is not None:
            reference = self.coordinator.data.data_timestamp_utc
            if (
                reference is not None
                and (reference - sensor.last_seen_utc) > STALE_THRESHOLD
            ):
                return f"last_seen {sensor.last_seen_utc} older than {STALE_THRESHOLD}"
        return "unknown"
