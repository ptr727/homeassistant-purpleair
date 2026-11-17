"""Fixtures for the dev-loop script tests, which run a script rather than Home Assistant."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> None:
    """Replace the root fixture, since loading the integration needs a hass instance."""
    return
