"""Constants for the PurpleAir tests."""

from typing import Final

TEST_API_KEY: Final[str] = "abcde12345"
TEST_NEW_API_KEY: Final[str] = "new_api_key"
TEST_SENSOR_INDEX1: Final[int] = 123456
TEST_SENSOR_INDEX2: Final[int] = 567890
TEST_SENSOR_INDEX_NO_LOCATION: Final[int] = 678901
TEST_SENSOR_READ_KEY: Final[str] = "ACDEF123"
TEST_LATITUDE: Final[float] = 51.5285582
TEST_LONGITUDE: Final[float] = -0.2416796
TEST_RADIUS: Final[int] = 5000

# The CONF_* constants below intentionally use a *bare* `Final` rather than
# `Final[str]`: ruff PYI064 flags `Final[Literal["x"]] = "x"` as redundant,
# and `Final[str]` widens the value to plain `str`, which breaks pyright's
# structural match of dict literals like `context={CONF_SOURCE: CONF_SOURCE_USER}`
# against HA's `ConfigFlowContext` / `SubentryFlowContext` TypedDicts. The
# bare form preserves the Literal narrow that those TypedDict keys need.
CONF_CONTEXT: Final = "context"
CONF_DATA: Final = "data"
CONF_ERRORS: Final = "errors"
CONF_FLOW_ID: Final = "flow_id"
CONF_HANDLER: Final = "handler"
CONF_NEXT_STEP_ID: Final = "next_step_id"
CONF_OPTIONS: Final = "options"
CONF_REASON: Final = "reason"
CONF_SENSOR_DEVICE_ID: Final = "sensor_device_id"
CONF_SOURCE: Final = "source"
CONF_STEP_ID: Final = "step_id"
CONF_TITLE: Final = "title"
CONF_TYPE: Final = "type"
CONF_SOURCE_USER: Final = "user"
