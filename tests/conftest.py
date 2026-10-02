"""Root test fixtures for the custom integration."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Load custom_components/ during every test."""
    return


@pytest.fixture(autouse=True)
def no_deprecated_usage_reported(
    caplog: pytest.LogCaptureFixture,
) -> Generator[None]:
    """Fail a test whose code path calls an API Home Assistant reports as deprecated.

    HA logs such a call rather than raising until the version that removes
    it, so a deprecated call would otherwise pass every test until then. HA
    reports a deprecated call through helpers.frame and a deprecated constant,
    function, or class through helpers.deprecation, each in its own wording.
    Teardown is read too, since that is where the hass fixture unloads the
    entry.
    """
    yield
    reports = [
        message
        for when in ("setup", "call", "teardown")
        for record in caplog.get_records(when)
        if "Detected that custom integration 'purpleair'"
        in (message := record.getMessage())
        or (message.startswith("The deprecated ") and " from purpleair." in message)
    ]
    assert not reports
