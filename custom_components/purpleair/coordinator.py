"""Define a PurpleAir DataUpdateCoordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from aiopurpleair.api import API
from aiopurpleair.errors import InvalidApiKeyError, PurpleAirError
from aiopurpleair.models.sensors import GetSensorsResponse, SensorModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AVAILABILITY_FIELDS,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    LOGGER,
    STATIC_DEVICE_FIELDS,
)

type PurpleAirConfigEntry = ConfigEntry[PurpleAirDataUpdateCoordinator]

UPDATE_INTERVAL: Final[timedelta] = timedelta(minutes=5)
STATIC_REFRESH_INTERVAL: Final[timedelta] = timedelta(hours=24)

# SensorModel attribute names matching STATIC_DEVICE_FIELDS on-wire names.
# name, hardware, model, firmware_version, latitude, longitude are direct.
_STATIC_MODEL_ATTRS: Final[tuple[str, ...]] = (
    "name",
    "hardware",
    "model",
    "firmware_version",
    "latitude",
    "longitude",
)


def _empty_response() -> GetSensorsResponse:
    """Construct an empty response for the no-subentry case."""
    now = datetime.now(UTC).replace(tzinfo=None)
    return GetSensorsResponse.model_validate(
        {
            "fields": [],
            "data": [],
            "api_version": "",
            "firmware_default_version": "",
            "max_age": 0,
            "data_time_stamp": int(now.timestamp()),
            "time_stamp": int(now.timestamp()),
        }
    )


class PurpleAirDataUpdateCoordinator(DataUpdateCoordinator[GetSensorsResponse]):
    """Define a PurpleAir-specific coordinator.

    PurpleAir charges API points per field per sensor per call, so the
    coordinator is designed around two cost-saving strategies:

    1. **Only request fields backing enabled entities.** Every refresh, the
       field list is recomputed from the live entity registry: an entity
       that is disabled in the UI contributes zero fields to the outgoing
       request. Enabling or disabling an entity triggers an immediate
       refresh so the change takes effect on the very next cycle (see
       ``_handle_registry_update``).
    2. **Cache static device-info fields for 24 h.** ``name``, ``hardware``,
       ``model``, ``firmware_version``, ``latitude``, and ``longitude``
       almost never change between readings. They are fetched once at first
       refresh, cached in ``_static_cache``, and only re-fetched every
       ``STATIC_REFRESH_INTERVAL``. Each response is merged with the cache
       so entities always observe a fully-populated ``SensorModel`` even
       when the on-wire response omitted those fields. Reloading the
       config entry forces an immediate re-fetch.

    For a default 6-entity single-sensor install this reduces per-day
    field-fetches from ~4,608 (hard-coded 16-field list) to ~2,886 (10
    per 5-min refresh + one daily 16-field catch-up) — roughly 37 % fewer
    points consumed per day.
    """

    config_entry: PurpleAirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=UPDATE_INTERVAL,
            always_update=True,
        )
        self._api = API(
            entry.data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(hass),
        )
        self._registry_unsub: CALLBACK_TYPE | None = None
        self._static_cache: dict[int, SensorModel] = {}
        self._last_static_refresh: datetime | None = None

    async def async_setup(self) -> None:
        """Subscribe to entity-registry changes to pick up enable/disable."""
        self._registry_unsub = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._handle_registry_update,
        )
        # Release on entry unload.
        self.config_entry.async_on_unload(self._async_release_registry_listener)

    @callback
    def _async_release_registry_listener(self) -> None:
        if self._registry_unsub is not None:
            self._registry_unsub()
            self._registry_unsub = None

    @callback
    def _handle_registry_update(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Trigger a refresh when one of our entities is enabled or disabled."""
        data = event.data
        if data["action"] != "update":
            return
        if "disabled_by" not in data.get("changes", {}):
            return
        entity_id = data["entity_id"]
        registry = er.async_get(self.hass)
        entry = registry.async_get(entity_id)
        if entry is None or entry.config_entry_id != self.config_entry.entry_id:
            return
        self.hass.async_create_task(self.async_request_refresh())

    def async_get_map_url(self, sensor_index: int) -> str:
        """Get map URL."""
        return self._api.get_map_url(sensor_index)

    def _should_fetch_static(self) -> bool:
        """Return True when STATIC_DEVICE_FIELDS must be included in the next request.

        True on first refresh, whenever a new subentry's sensor is missing from
        the cache, or once STATIC_REFRESH_INTERVAL has elapsed since the last
        static fetch so that firmware updates and sensor renames get picked up.
        """
        if self._last_static_refresh is None:
            return True
        for subentry in self.config_entry.subentries.values():
            if int(subentry.data[CONF_SENSOR_INDEX]) not in self._static_cache:
                return True
        age = datetime.now(UTC) - self._last_static_refresh
        return age >= STATIC_REFRESH_INTERVAL

    def _compute_requested_fields(self, include_static: bool) -> list[str]:
        """Compute the fields to request from the API.

        Always returns AVAILABILITY_FIELDS (drive availability) plus the
        api_fields of every enabled description for this config entry.
        STATIC_DEVICE_FIELDS are only included when the cache needs refreshing.
        """
        # Local import: ``.sensor`` imports from this module, so a top-level
        # import here would be circular.
        from .sensor import DESCRIPTIONS_BY_KEY, SENSOR_DESCRIPTIONS  # noqa: PLC0415

        requested: set[str] = set(AVAILABILITY_FIELDS)
        if include_static:
            requested.update(STATIC_DEVICE_FIELDS)

        registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        )
        if not entries:
            # First-refresh fallback — use every description enabled by default.
            for default_description in SENSOR_DESCRIPTIONS:
                if default_description.entity_registry_enabled_default:
                    requested.update(default_description.api_fields)
            return sorted(requested)

        for entity_entry in entries:
            if entity_entry.disabled_by is not None:
                continue
            # Unique IDs are `{sensor_index}-{description.key}`.
            key = entity_entry.unique_id.split("-", 1)[-1]
            matched = DESCRIPTIONS_BY_KEY.get(key)
            if matched is None:
                continue
            requested.update(matched.api_fields)
        return sorted(requested)

    @callback
    def _update_static_cache(self, response: GetSensorsResponse) -> None:
        """Refresh the in-memory static cache from a response that requested them."""
        for sensor_index, live in response.data.items():
            # Only cache if the response actually populated at least one static
            # field. (Guards against the "sensor present in response but with
            # all static fields stripped" edge case.)
            if any(
                getattr(live, attr, None) is not None for attr in _STATIC_MODEL_ATTRS
            ):
                self._static_cache[sensor_index] = live
        self._last_static_refresh = datetime.now(UTC)

    @callback
    def _merge_static_cache(self, response: GetSensorsResponse) -> GetSensorsResponse:
        """Overlay cached static values onto each SensorModel in the response."""
        if not self._static_cache:
            return response
        merged: dict[int, SensorModel] = {}
        for sensor_index, live in response.data.items():
            cached = self._static_cache.get(sensor_index)
            if cached is None:
                merged[sensor_index] = live
                continue
            updates = {
                attr: getattr(cached, attr)
                for attr in _STATIC_MODEL_ATTRS
                if getattr(live, attr, None) is None
                and getattr(cached, attr, None) is not None
            }
            merged[sensor_index] = live.model_copy(update=updates) if updates else live
        return response.model_copy(update={"data": merged})

    async def _async_update_data(self) -> GetSensorsResponse:
        """Get the latest sensor information."""
        index_list: list[int] = [
            int(subentry.data[CONF_SENSOR_INDEX])
            for subentry in self.config_entry.subentries.values()
        ]
        if not index_list:
            # No sensors configured — don't hit the API.
            return _empty_response()

        read_keys: list[str] = [
            str(subentry.data[CONF_SENSOR_READ_KEY])
            for subentry in self.config_entry.subentries.values()
            if subentry.data.get(CONF_SENSOR_READ_KEY) is not None
        ]
        read_key_list: list[str] | None = read_keys or None

        include_static = self._should_fetch_static()

        try:
            response = await self._api.sensors.async_get_sensors(
                self._compute_requested_fields(include_static),
                sensor_indices=index_list,
                read_keys=read_key_list,
            )
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PurpleAirError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if include_static:
            self._update_static_cache(response)

        return self._merge_static_cache(response)
