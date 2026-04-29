"""PurpleAir init and migration tests."""

from types import MappingProxyType

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_device_registry,
)

from custom_components.purpleair import (
    async_migrate_entry,
    async_migrate_integration,
    async_remove_config_entry_device,
)
from custom_components.purpleair.const import (
    CONF_LEGACY_SENSOR_INDICES,
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    DOMAIN,
    SCHEMA_VERSION,
    TITLE,
)
from homeassistant.config_entries import (
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .const import (
    TEST_API_KEY,
    TEST_NEW_API_KEY,
    TEST_SENSOR_INDEX1,
    TEST_SENSOR_INDEX2,
)


async def test_load_unload(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """Load and unload the integration."""
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads_entry(
    hass: HomeAssistant, config_entry, config_subentry, setup_config_entry
) -> None:
    """Changing options fires the update listener and reloads the entry."""
    assert config_entry.state is ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        config_entry, options={CONF_SHOW_ON_MAP: False}
    )
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.options == {CONF_SHOW_ON_MAP: False}


async def test_remove_config_entry_device_blocks_active_sensor(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Devices for sensors still configured cannot be removed."""
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))}
    )
    assert device is not None
    assert await async_remove_config_entry_device(hass, config_entry, device) is False


async def test_remove_config_entry_device_allows_stale_sensor(
    hass: HomeAssistant,
    config_entry,
    config_subentry,
    setup_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device whose sensor index is no longer configured can be removed."""
    # Craft a device for a sensor index that is not in any subentry.
    stale = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "999999")},
    )
    assert await async_remove_config_entry_device(hass, config_entry, stale) is True


async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Migrate two entries with different API keys to schema v2."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: True,
        },
        title="1234",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_NEW_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX2],
            CONF_SHOW_ON_MAP: False,
        },
        title="5678",
    )
    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)
    await hass.async_block_till_done()

    device_registry = mock_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry1.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    device_registry.async_get_or_create(
        config_entry_id=entry2.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    await hass.async_block_till_done()

    assert await async_migrate_entry(hass, entry1) is True
    assert await async_migrate_entry(hass, entry2) is True
    await hass.async_block_till_done()

    assert entry1.title == f"{TITLE} (1234)"
    assert entry2.title == f"{TITLE} (5678)"
    assert entry1.unique_id == TEST_API_KEY
    assert entry2.unique_id == TEST_NEW_API_KEY
    assert entry1.version == SCHEMA_VERSION
    assert entry2.version == SCHEMA_VERSION

    assert len(entry1.subentries) == 1
    assert len(entry2.subentries) == 1
    sub1 = next(iter(entry1.subentries.values()))
    sub2 = next(iter(entry2.subentries.values()))
    assert sub1.unique_id == str(TEST_SENSOR_INDEX1)
    assert sub1.title == f"TEST_SENSOR_INDEX1 ({TEST_SENSOR_INDEX1})"
    assert sub1.data == {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1}
    assert sub2.unique_id == str(TEST_SENSOR_INDEX2)


async def test_migrate_entry_matches_core_v1_schema(hass: HomeAssistant) -> None:
    """Migration succeeds against the exact schema the built-in integration writes.

    The upgrade path from HA core's built-in ``purpleair`` integration relies on
    the built-in's v1 config-entry shape matching what our migration expects.
    This test pins that contract so a silent drift in core's schema (before
    home-assistant/core#140901 ships) breaks the build loudly.

    v1 shape sourced from ``homeassistant/components/purpleair/__init__.py``
    and ``config_flow.py`` on the ``dev`` branch:
      - entry.data: {"api_key": <string>}
      - entry.options: {"sensor_indices": [<int>, ...], "show_on_map": <bool>}
      - entry.version: 1 (unspecified in manifest → HA default)
    The literal string keys below are deliberate; do NOT substitute the local
    constants. If core renames the options key, this test must fail.
    """
    core_v1_data = {"api_key": TEST_API_KEY}
    core_v1_options = {
        "sensor_indices": [TEST_SENSOR_INDEX1],
        "show_on_map": True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=core_v1_data,
        options=core_v1_options,
        title="core-v1",
    )
    entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="Sensor from core",
    )
    await hass.async_block_till_done()

    assert await async_migrate_entry(hass, entry) is True
    await hass.async_block_till_done()

    assert entry.version == SCHEMA_VERSION
    assert entry.unique_id == TEST_API_KEY
    assert entry.data == {CONF_API_KEY: TEST_API_KEY}
    assert entry.options == {CONF_SHOW_ON_MAP: True}
    assert len(entry.subentries) == 1
    sub = next(iter(entry.subentries.values()))
    assert sub.data == {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1}


async def test_migrate_entry_current_schema(hass: HomeAssistant) -> None:
    """Entries already on the current schema are a no-op."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)


async def test_migrate_entry_unknown_schema(hass: HomeAssistant) -> None:
    """Future schemas refuse to migrate."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=10,
        data={},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is False


async def test_migrate_entry_no_sensors_raises_repair(hass: HomeAssistant) -> None:
    """A v1 entry with no sensors migrates and raises a repair issue."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={},
        title=TITLE,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    await hass.async_block_till_done()
    assert entry.version == SCHEMA_VERSION

    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"legacy_migration_no_sensors_{entry.entry_id}"
        )
        is not None
    )


async def test_async_migrate_integration_merges_sibling_entries(
    hass: HomeAssistant,
) -> None:
    """Two v1 entries sharing an API key are merged under one parent."""
    parent = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="parent",
        disabled_by=ConfigEntryDisabler.USER,
    )
    sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX2],
            CONF_SHOW_ON_MAP: True,
        },
        title="sibling",
        disabled_by=ConfigEntryDisabler.USER,
    )
    parent.add_to_hass(hass)
    sibling.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    device_registry.async_get_or_create(
        config_entry_id=sibling.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    # Sibling has been absorbed and removed.
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    survivor = entries[0]
    assert survivor.entry_id == parent.entry_id
    assert survivor.version == SCHEMA_VERSION
    assert survivor.options[CONF_SHOW_ON_MAP] is True  # OR across siblings
    assert len(survivor.subentries) == 2
    sensor_indices = {
        int(sub.data[CONF_SENSOR_INDEX]) for sub in survivor.subentries.values()
    }
    assert sensor_indices == {TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2}


async def test_async_migrate_integration_merges_enabled_siblings(
    hass: HomeAssistant,
) -> None:
    """Two ENABLED v1 entries sharing an API key are merged under one parent.

    Regression: an earlier revision of async_migrate_integration skipped
    enabled v1 entries on the assumption that async_migrate_entry would
    handle them one at a time. That left the second of a duplicate-API-key
    pair migrating independently to v2 with the same unique_id, producing
    two v2 entries that both claim the same API key.
    """
    parent = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="parent",
    )
    sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX2],
            CONF_SHOW_ON_MAP: True,
        },
        title="sibling",
    )
    parent.add_to_hass(hass)
    sibling.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    device_registry.async_get_or_create(
        config_entry_id=sibling.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1, "enabled v1 siblings must be merged, not left separate"
    survivor = entries[0]
    assert survivor.entry_id == parent.entry_id
    assert survivor.version == SCHEMA_VERSION
    assert survivor.unique_id == TEST_API_KEY
    assert survivor.options[CONF_SHOW_ON_MAP] is True  # OR across siblings
    sensor_indices = {
        int(sub.data[CONF_SENSOR_INDEX]) for sub in survivor.subentries.values()
    }
    assert sensor_indices == {TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2}


async def test_async_migrate_integration_noop_when_no_v1(
    hass: HomeAssistant,
) -> None:
    """No v1 entries means nothing changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        options={CONF_SHOW_ON_MAP: True},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    await async_migrate_integration(hass)
    # Entry is untouched.
    assert entry.version == SCHEMA_VERSION
    assert entry.options[CONF_SHOW_ON_MAP] is True


async def test_migrate_entry_skips_unknown_and_orphan_devices(
    hass: HomeAssistant,
) -> None:
    """async_migrate_entry must skip devices missing a domain identifier or outside the options list."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title=TITLE,
    )
    entry.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    # Device with no PurpleAir identifier.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other_domain", "123")},
    )
    # Device for a sensor index that is NOT in the options list.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "999999")},
        name="TEST_ORPHAN",
    )
    # Valid device.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    await hass.async_block_till_done()

    assert await async_migrate_entry(hass, entry) is True
    await hass.async_block_till_done()
    # Only the matching device was migrated into a subentry.
    assert len(entry.subentries) == 1
    sub = next(iter(entry.subentries.values()))
    assert int(sub.data[CONF_SENSOR_INDEX]) == TEST_SENSOR_INDEX1


async def test_async_migrate_integration_absorbs_disabled_sibling_no_sensors(
    hass: HomeAssistant,
) -> None:
    """A disabled sibling with no sensors migrates and raises a repair issue."""
    parent = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="parent",
    )
    disabled_sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={CONF_SHOW_ON_MAP: False},
        title="sibling",
        disabled_by=ConfigEntryDisabler.USER,
    )
    parent.add_to_hass(hass)
    disabled_sibling.add_to_hass(hass)
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            f"legacy_migration_no_sensors_{disabled_sibling.entry_id}",
        )
        is not None
    )


async def test_async_migrate_integration_aligns_v2_show_on_map(
    hass: HomeAssistant,
) -> None:
    """After a sibling migration, other v2 entries sharing a key get their options aligned."""
    # A v1 disabled sibling with show_on_map=True, and a v2 parent with show_on_map=False.
    # Post-migration, the v2 parent should have show_on_map=True to reflect the merge.
    v2_parent = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        unique_id=TEST_API_KEY,
        data={CONF_API_KEY: TEST_API_KEY},
        options={CONF_SHOW_ON_MAP: False},
        title=TITLE,
    )
    v1_sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: True,
        },
        title="sibling",
        disabled_by=ConfigEntryDisabler.USER,
    )
    v2_parent.add_to_hass(hass)
    v1_sibling.add_to_hass(hass)
    # Attach a subentry to the v2 parent so the sensor exists already.
    hass.config_entries.async_add_subentry(
        v2_parent,
        ConfigSubentry(
            data=MappingProxyType({CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1}),
            subentry_type=CONF_SENSOR,
            title="existing",
            unique_id=str(TEST_SENSOR_INDEX1),
        ),
    )

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    assert v2_parent.options[CONF_SHOW_ON_MAP] is True
