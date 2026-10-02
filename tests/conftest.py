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
    it, so a deprecated call would otherwise pass every test until then.
    """
    yield
    reports = [
        record.getMessage()
        for when in ("setup", "call")
        for record in caplog.get_records(when)
        if "Detected that custom integration 'purpleair'" in record.getMessage()
    ]
    assert not reports
