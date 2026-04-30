"""Tests for the PurpleAir data update coordinator."""

from datetime import timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from aiopurpleair.errors import InvalidApiKeyError, PaymentRequiredError, PurpleAirError
from aiopurpleair.models.organizations import GetOrganizationResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.purpleair.const import CONF_SENSOR, CONF_SENSOR_INDEX, DOMAIN
from custom_components.purpleair.coordinator import (
    ISSUE_LOW_API_POINTS,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2


async def test_coordinator_calls_api_with_configured_indices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
) -> None:
    """The coordinator must forward sensor_indices and read_keys to aiopurpleair."""
    api.sensors.async_get_sensors.assert_awaited()
    call = api.sensors.async_get_sensors.await_args
    assert call.kwargs["sensor_indices"] == [TEST_SENSOR_INDEX1]
    # The default subentry has no read_key, so read_keys must be None (not []).
    assert call.kwargs["read_keys"] is None


async def test_coordinator_requests_only_enabled_entity_fields(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
) -> None:
    """Disabled entities must not contribute fields to the API request.

    This is the contract that keeps API point cost proportional to what the
    user is actually using.
    """
    fields = api.sensors.async_get_sensors.await_args.args[0]
    # Availability fields are always present.
    assert "last_seen" in fields
    assert "confidence" in fields
    assert "channel_state" in fields
    # Enabled-by-default entity fields are present.
    assert "temperature" in fields
    assert "humidity" in fields
    assert "pm2.5" in fields
    # Disabled-by-default entity fields are absent.
    assert "pm2.5_alt" not in fields
    assert "pm2.5_24hour" not in fields
    assert "uptime" not in fields
    assert "rssi" not in fields
    # location_type is unused client-side and must not be requested.
    assert "location_type" not in fields


async def test_coordinator_first_refresh_includes_static_fields(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
) -> None:
    """First refresh must fetch STATIC_DEVICE_FIELDS so DeviceInfo is populated."""
    # The first call has static fields.
    first_fields = api.sensors.async_get_sensors.await_args_list[0].args[0]
    for field in (
        "name",
        "hardware",
        "model",
        "firmware_version",
        "latitude",
        "longitude",
    ):
        assert field in first_fields


async def test_coordinator_subsequent_refresh_skips_static_fields(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After first refresh, static fields are not requested again within 24 h."""
    api.sensors.async_get_sensors.reset_mock()
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    fields = api.sensors.async_get_sensors.await_args.args[0]
    for field in (
        "name",
        "hardware",
        "model",
        "firmware_version",
        "latitude",
        "longitude",
    ):
        assert field not in fields, f"{field} should not be in follow-up refresh"
    # Availability + entity fields must still be there.
    assert "last_seen" in fields
    assert "temperature" in fields


async def test_coordinator_refetches_static_after_24h(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After 24 h, the next refresh must re-include static fields."""
    api.sensors.async_get_sensors.reset_mock()
    freezer.tick(timedelta(hours=24, seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    fields = api.sensors.async_get_sensors.await_args.args[0]
    assert "name" in fields
    assert "firmware_version" in fields


async def test_coordinator_merges_cached_static_values(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    get_sensors_response,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Sensors in follow-up responses must report cached static values."""
    # Simulate a follow-up response that omits static fields (as would happen
    # because we didn't request them).
    stripped_sensors = {
        idx: sensor.model_copy(
            update={
                "name": None,
                "hardware": None,
                "model": None,
                "firmware_version": None,
                "latitude": None,
                "longitude": None,
            }
        )
        for idx, sensor in get_sensors_response.data.items()
    }
    stripped = get_sensors_response.model_copy(update={"data": stripped_sensors})
    api.sensors.async_get_sensors = AsyncMock(return_value=stripped)

    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # DeviceInfo values came from the cached (initial) response.
    coordinator = config_entry.runtime_data.sensors
    merged = coordinator.data.data[TEST_SENSOR_INDEX1]
    assert merged.name == "Test Sensor"
    assert merged.hardware == "2.0+BME280+PMSX003-B+PMSX003-A"
    assert merged.model == "PA-II"


async def test_coordinator_refreshes_when_entity_enabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    entity_registry,
) -> None:
    """Enabling a previously-disabled entity must trigger a refresh with its field."""
    api.sensors.async_get_sensors.reset_mock()

    disabled_entity = next(
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.unique_id.endswith("-pm2.5_24hour")
    )
    entity_registry.async_update_entity(disabled_entity.entity_id, disabled_by=None)
    await hass.async_block_till_done()

    # The registry listener should have triggered a refresh with the new field.
    assert api.sensors.async_get_sensors.await_count >= 1
    fields = api.sensors.async_get_sensors.await_args.args[0]
    assert "pm2.5_24hour" in fields


async def test_derived_sensors_dont_cost_points_while_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
) -> None:
    """EPA and AQI sensors' fields are absent from the default request.

    The PM2.5 EPA sensor is derived from pm2.5 + humidity and the AQI sensor
    is derived from pm2.5_24hour. When both are disabled-by-default (the
    default state):

    - pm2.5 and humidity ARE in the request, but that is because the
      baseline pm2.5_mass_concentration and humidity entities are also
      enabled by default — not because the EPA entity demands them.
    - pm2.5_24hour must NOT be in the request, since nothing else needs it.
    """
    fields = api.sensors.async_get_sensors.await_args.args[0]
    assert "pm2.5_24hour" not in fields


async def test_aqi_enables_its_field(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    entity_registry,
) -> None:
    """Enabling only the AQI sensor pulls in pm2.5_24hour on the next refresh."""
    api.sensors.async_get_sensors.reset_mock()
    aqi_entity = next(
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.unique_id.endswith("-pm2.5_aqi")
    )
    entity_registry.async_update_entity(aqi_entity.entity_id, disabled_by=None)
    await hass.async_block_till_done()

    fields = api.sensors.async_get_sensors.await_args.args[0]
    assert "pm2.5_24hour" in fields


async def test_epa_sensor_pulls_both_fields_when_baselines_disabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    entity_registry,
) -> None:
    """Enabling only the EPA sensor pulls in pm2.5 and humidity.

    With the default pm2.5 and humidity entities disabled, enabling the EPA
    entity must still cause pm2.5 and humidity to be requested. This is the
    self-sufficiency contract for derived sensors — they carry their own
    api_fields so users can enable a single derived entity without having
    to keep the baselines on for the points-cost side-effect.
    """
    # Disable the two baseline entities that normally pull these fields.
    for unique_id_tail in ("-pm2.5_mass_concentration", "-humidity"):
        entity = next(
            e
            for e in entity_registry.entities.values()
            if e.config_entry_id == config_entry.entry_id
            and e.unique_id.endswith(unique_id_tail)
        )
        entity_registry.async_update_entity(
            entity.entity_id,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

    # Enable the EPA derived entity.
    epa_entity = next(
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.unique_id.endswith("-pm2.5_epa_mass_concentration")
    )
    entity_registry.async_update_entity(epa_entity.entity_id, disabled_by=None)
    await hass.async_block_till_done()

    # Force a refresh so we get a deterministic final call (the registry
    # listener uses async_request_refresh which is debounced).
    api.sensors.async_get_sensors.reset_mock()
    await config_entry.runtime_data.sensors.async_refresh()
    await hass.async_block_till_done()

    fields = api.sensors.async_get_sensors.await_args.args[0]
    assert "pm2.5" in fields
    assert "humidity" in fields


async def test_coordinator_empty_subentries_skips_api(
    hass: HomeAssistant, config_entry: MockConfigEntry, setup_config_entry, api
) -> None:
    """With no subentries, the coordinator returns an empty response without calling the API."""
    api.sensors.async_get_sensors.assert_not_called()
    coordinator = config_entry.runtime_data.sensors
    assert coordinator.data is not None
    assert coordinator.data.data == {}


async def test_coordinator_map_url(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
) -> None:
    """async_get_map_url delegates to the underlying API object."""
    coordinator = config_entry.runtime_data.sensors
    assert coordinator.async_get_map_url(TEST_SENSOR_INDEX1) == "http://example.com"


async def test_coordinator_refresh_invalid_api_key_triggers_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A scheduled refresh that 401s must open a reauth flow."""
    with patch.object(
        api.sensors,
        "async_get_sensors",
        AsyncMock(side_effect=InvalidApiKeyError),
    ):
        freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = [
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["handler"] == DOMAIN and flow["context"].get("source") == "reauth"
    ]
    assert len(flows) == 1


@pytest.mark.parametrize(
    "side_effect",
    [PurpleAirError("boom"), RuntimeError("surprise")],
)
async def test_coordinator_refresh_update_failures_are_reported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Non-auth failures surface as last_update_success = False."""
    coordinator = config_entry.runtime_data.sensors

    with patch.object(
        api.sensors,
        "async_get_sensors",
        AsyncMock(side_effect=side_effect),
    ):
        freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert coordinator.last_update_success is False


async def test_static_refresh_when_new_subentry_is_cache_miss(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
) -> None:
    """New subentry triggers a static-fields refresh on its next update.

    Covers the "sensor missing from _static_cache" branch in
    _should_fetch_static and the "no cache entry yet for this sensor"
    branch in _merge_static_cache. Verified by driving ``_async_update_data``
    directly after mutating cache / subentry state, which is how the
    DataUpdateCoordinator ultimately invokes it.
    """
    coordinator = config_entry.runtime_data.sensors

    # Add a second subentry and evict its cache entry to simulate a fresh add.
    new_subentry = ConfigSubentry(
        data=MappingProxyType({CONF_SENSOR_INDEX: TEST_SENSOR_INDEX2}),
        subentry_type=CONF_SENSOR,
        title=f"Extra sensor ({TEST_SENSOR_INDEX2})",
        unique_id=str(TEST_SENSOR_INDEX2),
    )
    hass.config_entries.async_add_subentry(config_entry, new_subentry)
    await hass.async_block_till_done()
    coordinator._static_cache.pop(TEST_SENSOR_INDEX2, None)  # noqa: SLF001

    # _should_fetch_static must detect the cache miss.
    assert coordinator._should_fetch_static() is True  # noqa: SLF001

    # Call _async_update_data directly — bypasses the debouncer that would
    # otherwise suppress rapid refreshes in the test.
    api.sensors.async_get_sensors.reset_mock()
    await coordinator._async_update_data()  # noqa: SLF001

    fields = api.sensors.async_get_sensors.await_args.args[0]
    for field in ("name", "hardware", "model", "firmware_version"):
        assert field in fields, f"{field} missing from refresh after new subentry"
    # And merging populated the new cache entry.
    assert TEST_SENSOR_INDEX2 in coordinator._static_cache  # noqa: SLF001


async def test_registry_event_for_foreign_entity_does_not_refresh(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    entity_registry: er.EntityRegistry,
) -> None:
    """Entity-registry updates for entities owned by another integration are ignored.

    Otherwise every toggle in any unrelated integration would trigger a PurpleAir
    API request. Covers the entry.config_entry_id != self.config_entry.entry_id
    early-return in _handle_registry_update.
    """
    # Register an entity that looks like it belongs to a different config entry.
    other_entry = MockConfigEntry(domain="other_integration", data={})
    other_entry.add_to_hass(hass)
    foreign_entity_id = entity_registry.async_get_or_create(
        "sensor",
        "other_integration",
        "foreign-unique-id",
        config_entry=other_entry,
    ).entity_id

    api.sensors.async_get_sensors.reset_mock()

    # Toggle the foreign entity's disabled_by — this fires the registry event.
    entity_registry.async_update_entity(
        foreign_entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    # The PurpleAir coordinator must NOT have issued a refresh.
    assert api.sensors.async_get_sensors.await_count == 0


def _organization_response(remaining: int, rate: int) -> GetOrganizationResponse:
    """Build a synthetic organization response."""
    return GetOrganizationResponse.model_validate(
        {
            "api_version": "V1.0.11-0.0.41",
            "time_stamp": 1668985817,
            "organization_id": "abc123def456",
            "organization_name": "Test Org",
            "remaining_points": remaining,
            "consumption_rate": rate,
        }
    )


async def test_organization_low_points_creates_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Remaining < rate*7 must raise the low_api_points repair issue."""
    issue_id = f"{ISSUE_LOW_API_POINTS}_{config_entry.entry_id}"
    # Healthy default fixture means no issue at setup time.
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # Drop the balance below the 7-day floor and refresh directly. The 24 h
    # `update_interval` rules out async_fire_time_changed without a full-day
    # tick, which the freezer can do but it's awkward to compose with the
    # sensors coordinator's 5-minute schedule. Driving `async_refresh()`
    # exercises the same `_async_update_data` path that the scheduler does.
    api.organizations.async_get_organization.return_value = _organization_response(
        remaining=1000, rate=200
    )
    await config_entry.runtime_data.organization.async_refresh()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == ISSUE_LOW_API_POINTS
    assert issue.translation_placeholders == {
        "remaining": "1000",
        "rate": "200",
        "days_left": "5",
    }


async def test_organization_recovery_clears_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A subsequent refresh that's back above the floor must clear the issue."""
    issue_id = f"{ISSUE_LOW_API_POINTS}_{config_entry.entry_id}"

    # First refresh: low.
    api.organizations.async_get_organization.return_value = _organization_response(
        remaining=500, rate=200
    )
    await config_entry.runtime_data.organization.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    # Second refresh: balance topped up.
    api.organizations.async_get_organization.return_value = _organization_response(
        remaining=50000, rate=200
    )
    await config_entry.runtime_data.organization.async_refresh()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_organization_payment_required_creates_repair_issue(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry,
    setup_config_entry,
    api,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A PaymentRequiredError on the org refresh must still raise the repair issue."""
    issue_id = f"{ISSUE_LOW_API_POINTS}_{config_entry.entry_id}"

    api.organizations.async_get_organization.side_effect = PaymentRequiredError(
        "out of points"
    )
    await config_entry.runtime_data.organization.async_refresh()

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == ISSUE_LOW_API_POINTS
