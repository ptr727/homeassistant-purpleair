"""Diagnostics support for PurpleAir."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .coordinator import PurpleAirConfigEntry

CONF_TITLE = "title"

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    # Config entry title and unique ID contain the API key (whole or part):
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PurpleAirConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    sensors_coordinator = entry.runtime_data.sensors
    organization_coordinator = entry.runtime_data.organization
    sensors_data_dump: dict[str, Any] | None = (
        sensors_coordinator.data.model_dump()
        if sensors_coordinator.data is not None
        else None
    )
    organization_data_dump: dict[str, Any] | None = (
        organization_coordinator.data.model_dump()
        if organization_coordinator.data is not None
        else None
    )
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "coordinator": {
                "last_update_success": sensors_coordinator.last_update_success,
                "last_exception": (
                    repr(sensors_coordinator.last_exception)
                    if sensors_coordinator.last_exception is not None
                    else None
                ),
                "update_interval": str(sensors_coordinator.update_interval),
            },
            "organization_coordinator": {
                "last_update_success": organization_coordinator.last_update_success,
                "last_exception": (
                    repr(organization_coordinator.last_exception)
                    if organization_coordinator.last_exception is not None
                    else None
                ),
                "update_interval": str(organization_coordinator.update_interval),
            },
            "data": sensors_data_dump,
            "organization_data": organization_data_dump,
        },
        TO_REDACT,
    )
