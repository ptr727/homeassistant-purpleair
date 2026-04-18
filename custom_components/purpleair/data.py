"""Custom types for purpleair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import PurpleAirApiClient
    from .coordinator import PurpleAirDataUpdateCoordinator


type PurpleAirConfigEntry = ConfigEntry[PurpleAirData]


@dataclass
class PurpleAirData:
    """Data for the PurpleAir integration."""

    client: PurpleAirApiClient
    coordinator: PurpleAirDataUpdateCoordinator
    integration: Integration
