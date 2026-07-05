"""Test PurpleAir diagnostics."""

from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
    config_subentry,
    setup_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Diagnostics dump redacts the API key and captures coordinator state."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    # Volatile keys (timestamps, random ids) are excluded from the snapshot.
    assert diagnostics == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "entry_id",
            "subentry_id",
            "last_exception",
        )
    )


async def test_diagnostics_before_refresh(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry,
    setup_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Diagnostics must not crash when the coordinator has no subentries yet."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    # `JsonObjectType` values are `JsonValueType` (a union including ints,
    # bools, lists, etc.), so each nested subscript needs a concrete narrow
    # before the next one type-checks.
    assert diagnostics["data"] is not None
    coordinator = diagnostics["coordinator"]
    assert isinstance(coordinator, dict)
    assert coordinator["last_update_success"] is True
