"""Define a PurpleAir DataUpdateCoordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from aiopurpleair.api import API
from aiopurpleair.errors import InvalidApiKeyError, PaymentRequiredError, PurpleAirError
from aiopurpleair.models.organizations import GetOrganizationResponse
from aiopurpleair.models.sensors import GetSensorsResponse, SensorModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AVAILABILITY_FIELDS,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    LOGGER,
    STATIC_DEVICE_FIELDS,
)


@dataclass(frozen=True)
class PurpleAirRuntimeData:
    """Container for both coordinators attached to a PurpleAir config entry."""

    sensors: PurpleAirDataUpdateCoordinator
    organization: PurpleAirOrganizationCoordinator


type PurpleAirConfigEntry = ConfigEntry[PurpleAirRuntimeData]

UPDATE_INTERVAL: Final[timedelta] = timedelta(minutes=5)
STATIC_REFRESH_INTERVAL: Final[timedelta] = timedelta(hours=24)
ORGANIZATION_UPDATE_INTERVAL: Final[timedelta] = timedelta(hours=24)
LOW_POINTS_DAYS_THRESHOLD: Final[int] = 7
ISSUE_LOW_API_POINTS: Final[str] = "low_api_points"
ISSUE_OUT_OF_API_POINTS: Final[str] = "out_of_api_points"
PURCHASE_URL: Final[str] = "https://develop.purpleair.com/dashboards/projects"


def _low_points_issue_id(entry_id: str) -> str:
    """Build the per-entry low-points repair issue id."""
    return f"{ISSUE_LOW_API_POINTS}_{entry_id}"


def _out_of_points_issue_id(entry_id: str) -> str:
    """Build the per-entry out-of-points repair issue id."""
    return f"{ISSUE_OUT_OF_API_POINTS}_{entry_id}"


@callback
def _async_raise_out_of_points_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Surface the persistent ERROR repair issue for an exhausted points balance.

    Distinct from the WARNING-level low-points issue so the severity reflects
    the operational difference: low_points is "buy soon", out_of_points is
    "the API is rejecting requests right now". Both issues use distinct ids
    so they don't overwrite each other when both coordinators fire.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        _out_of_points_issue_id(entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_OUT_OF_API_POINTS,
        translation_placeholders={"purchase_url": PURCHASE_URL},
    )


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
    """Construct an empty response for the no-subentry case.

    Keeps the datetime tz-aware; a naive UTC datetime's ``.timestamp()`` is
    interpreted in the host's local time and yields a wrong epoch on any
    non-UTC system.
    """
    epoch = int(datetime.now(UTC).timestamp())
    return GetSensorsResponse.model_validate(
        {
            "fields": [],
            "data": [],
            "api_version": "",
            "firmware_default_version": "",
            "max_age": 0,
            "data_time_stamp": epoch,
            "time_stamp": epoch,
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
        # Pin the scheduled refresh to the config entry so unloading the
        # integration cancels any in-flight refresh kicked off by a registry
        # toggle. Using hass.async_create_task directly would leave an
        # untracked task (RUF006 doesn't catch HA helpers, but the lifecycle
        # concern is real).
        self.config_entry.async_create_task(
            self.hass,
            self.async_request_refresh(),
            name=f"{DOMAIN} refresh after entity registry update ({entity_id})",
        )

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
        except PaymentRequiredError as err:
            # Surface the dedicated out-of-points issue (distinct id from the
            # low-points warning) so the user sees a clear ERROR-level repair
            # without confusing "0 points/day" placeholders.
            _async_raise_out_of_points_issue(self.hass, self.config_entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
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

        # Successful sensor refresh → API is accepting requests, so the
        # out-of-points ERROR cannot be true. Clear it here so the user
        # sees the issue disappear within the 5-minute sensors cycle
        # rather than waiting up to 24 h for the next org refresh.
        # `async_delete_issue` is a no-op when the issue isn't registered.
        ir.async_delete_issue(
            self.hass,
            DOMAIN,
            _out_of_points_issue_id(self.config_entry.entry_id),
        )

        if include_static:
            self._update_static_cache(response)

        return self._merge_static_cache(response)


class PurpleAirOrganizationCoordinator(DataUpdateCoordinator[GetOrganizationResponse]):
    """Define an account-level coordinator polling GET /v1/organization once a day.

    Drives the Remaining-points and Consumption-rate diagnostic sensors and
    raises a repair issue when remaining points fall below ``consumption_rate
    * LOW_POINTS_DAYS_THRESHOLD`` so the user can buy more before the integration
    starts failing every refresh with PaymentRequiredError.
    """

    config_entry: PurpleAirConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} (organization)",
            update_interval=ORGANIZATION_UPDATE_INTERVAL,
        )
        self._api = API(
            entry.data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> GetOrganizationResponse:
        """Fetch the organization metadata and manage the repair issues."""
        try:
            response = await self._api.organizations.async_get_organization()
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from err
        except PaymentRequiredError as err:
            # The API confirms we're out of points — surface the dedicated
            # out-of-points ERROR issue. Don't touch the low-points warning
            # here; we don't have a current balance reading to evaluate.
            _async_raise_out_of_points_issue(self.hass, self.config_entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except PurpleAirError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self._async_evaluate_low_points(response)
        return response

    @callback
    def _async_evaluate_low_points(self, response: GetOrganizationResponse) -> None:
        """Create or clear the repair issues based on the current balance.

        A successful response means the API is accepting requests, so the
        out-of-points ERROR issue is always cleared here. Only the
        low-points WARNING is balance-dependent.
        """
        # Successful read → API is accepting requests → out-of-points cannot
        # be true right now. Clear it unconditionally.
        ir.async_delete_issue(
            self.hass, DOMAIN, _out_of_points_issue_id(self.config_entry.entry_id)
        )

        rate = response.consumption_rate
        remaining = response.remaining_points
        low_points_id = _low_points_issue_id(self.config_entry.entry_id)
        if rate > 0 and remaining < rate * LOW_POINTS_DAYS_THRESHOLD:
            days_left = remaining // rate
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                low_points_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_LOW_API_POINTS,
                translation_placeholders={
                    "remaining": str(remaining),
                    "rate": str(rate),
                    "days_left": str(days_left),
                    "purchase_url": PURCHASE_URL,
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, low_points_id)
