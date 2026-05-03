"""Define fixtures for PurpleAir tests."""

from collections.abc import Generator
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiopurpleair.endpoints.sensors import NearbySensorResult
from aiopurpleair.models.keys import GetKeysResponse
from aiopurpleair.models.organizations import GetOrganizationResponse
from aiopurpleair.models.sensors import GetSensorsResponse, SensorModel
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, load_fixture
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy import SnapshotAssertion

from custom_components.purpleair.const import (
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    SCHEMA_VERSION,
    TITLE,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

from .const import TEST_API_KEY, TEST_SENSOR_INDEX1


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return snapshot assertion fixture with the Home Assistant extension."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(name="get_keys_response")
def get_keys_response_fixture() -> GetKeysResponse:
    """Return a valid GetKeysResponse with api_key_type=READ."""
    return GetKeysResponse.model_validate(
        {
            "api_version": "V1.0.11-0.0.41",
            "time_stamp": 1668985817,
            "api_key_type": "READ",
        }
    )


@pytest.fixture(name="get_organization_response")
def get_organization_response_fixture() -> GetOrganizationResponse:
    """Return a healthy GetOrganizationResponse (well above the 7-day floor)."""
    return GetOrganizationResponse.model_validate(
        {
            "api_version": "V1.0.11-0.0.41",
            "time_stamp": 1668985817,
            "organization_id": "abc123def456",
            "organization_name": "Test Org",
            "remaining_points": 50000,
            "consumption_rate": 1500,
        }
    )


@pytest.fixture(name="api")
def api_fixture(
    get_sensors_response: GetSensorsResponse,
    get_keys_response: GetKeysResponse,
    get_organization_response: GetOrganizationResponse,
) -> Mock:
    """Define a fixture to return a mocked aiopurpleair API object.

    ``async_get_sensors`` mimics the real endpoint by filtering both
    ``sensor_indices`` and the ``fields`` argument: the server only returns
    sensors you asked for, and within each sensor only the fields you
    requested. Without the field filter, gated entries like ``voc`` would
    appear populated in tests where production would have skipped the
    field — masking regressions in ``_compute_requested_fields``.
    """
    # Map wire field name (alias) → SensorModel attribute name.
    wire_to_attr = {
        (info.alias or name): name for name, info in SensorModel.model_fields.items()
    }

    async def _filtered_get_sensors(*args, **kwargs):
        requested_fields = set(args[0] if args else kwargs.get("fields", ()))
        indices = kwargs.get("sensor_indices")
        filtered: dict[int, SensorModel] = {}
        for idx, sensor in get_sensors_response.data.items():
            if indices and idx not in indices:
                continue
            # Strip every attribute whose wire name wasn't in `fields`.
            # Preserve `sensor_index` (always present in the wire row).
            stripped: dict[str, Any] = {}
            for wire_name, attr_name in wire_to_attr.items():
                if attr_name == "sensor_index":
                    continue
                if wire_name not in requested_fields:
                    stripped[attr_name] = None
            filtered[idx] = sensor.model_copy(update=stripped) if stripped else sensor
        return get_sensors_response.model_copy(update={"data": filtered})

    return Mock(
        async_check_api_key=AsyncMock(return_value=get_keys_response),
        get_map_url=Mock(return_value="http://example.com"),
        sensors=Mock(
            async_get_nearby_sensors=AsyncMock(
                return_value=[
                    NearbySensorResult(sensor=sensor, distance=1.0)
                    for sensor in get_sensors_response.data.values()
                ]
            ),
            async_get_sensors=AsyncMock(side_effect=_filtered_get_sensors),
        ),
        organizations=Mock(
            async_get_organization=AsyncMock(return_value=get_organization_response),
        ),
    )


@pytest.fixture(name="config_entry")
def config_entry_fixture(
    hass: HomeAssistant,
    config_entry_data: dict[str, Any],
    config_entry_options: dict[str, Any],
) -> MockConfigEntry:
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        # Fixed entry_id for deterministic snapshots — production entry_ids are
        # randomly generated. The new account-level diagnostic entities use it
        # in their unique_id (account-level identifiers can't legitimately
        # reuse a per-sensor index).
        entry_id="purpleair_test_entry_id",
        unique_id=TEST_API_KEY,
        data=config_entry_data,
        options=config_entry_options,
        version=SCHEMA_VERSION,
        title=TITLE,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> dict[str, Any]:
    """Define a config entry data fixture."""
    return {CONF_API_KEY: TEST_API_KEY}


@pytest.fixture(name="config_subentry_data")
def config_subentry_data_fixture() -> dict[str, Any]:
    """Define a config subentry data fixture."""
    return {
        CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1,
        CONF_SENSOR_READ_KEY: None,
    }


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture() -> dict[str, Any]:
    """Define a config entry options fixture."""
    return {CONF_SHOW_ON_MAP: True}


@pytest.fixture(name="config_subentry")
def config_subentry_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_subentry_data: dict[str, Any],
) -> ConfigSubentry:
    """Define a config subentry fixture and attach it to the entry."""
    subentry = ConfigSubentry(
        data=MappingProxyType(config_subentry_data),
        subentry_type=CONF_SENSOR,
        title=f"TEST_SENSOR_INDEX1 ({TEST_SENSOR_INDEX1})",
        unique_id=str(TEST_SENSOR_INDEX1),
    )
    hass.config_entries.async_add_subentry(config_entry, subentry)
    return subentry


@pytest.fixture(name="get_sensors_response", scope="package")
def get_sensors_response_fixture() -> GetSensorsResponse:
    """Define a fixture to mock an aiopurpleair GetSensorsResponse object."""
    return GetSensorsResponse.model_validate_json(
        load_fixture("get_sensors_response.json")
    )


@pytest.fixture(name="mock_aiopurpleair")
def mock_aiopurpleair_fixture(api: Mock) -> Generator[Mock]:
    """Define a fixture to patch aiopurpleair."""
    with (
        patch("custom_components.purpleair.coordinator.API", return_value=api),
        patch("custom_components.purpleair.config_flow.API", return_value=api),
    ):
        yield api


@pytest.fixture(name="setup_config_entry")
async def setup_config_entry_fixture(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_aiopurpleair: Mock
) -> None:
    """Define a fixture to set up purpleair."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
