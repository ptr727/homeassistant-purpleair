"""PurpleAir init and migration tests."""

import logging
from types import MappingProxyType

import pytest
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
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(TEST_SENSOR_INDEX1)), config_entry.entry_id
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
      - entry.version: 1 (unspecified in manifest -> HA default)
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
    parent_device = device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    sibling_device = device_registry.async_get_or_create(
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

    # Both devices survive the sibling's removal, owned by their sensor's subentry.
    subentry_ids = {
        int(sub.data[CONF_SENSOR_INDEX]): sub.subentry_id
        for sub in survivor.subentries.values()
    }
    for device, sensor_index in (
        (parent_device, TEST_SENSOR_INDEX1),
        (sibling_device, TEST_SENSOR_INDEX2),
    ):
        moved = device_registry.async_get(device.id)
        assert moved is not None
        assert moved.config_entry_id == parent.entry_id
        assert moved.config_subentry_id == subentry_ids[sensor_index]


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


async def test_async_migrate_integration_drops_legacy_device_link(
    hass: HomeAssistant,
) -> None:
    """Migration moves the device off the legacy (parent_entry, None) owner.

    Regression: a v1 device is registered with `config_entry_id=entry.entry_id`
    and no subentry. v2 binds the device to a real subentry instead, so the
    migration must move it to (parent_entry, subentry) - otherwise the device
    stays owned by the entry without any subentry forever.

    This guard exercises the parent-entry branch of async_migrate_integration
    (the case where the migrating entry is itself the chosen parent - i.e. a
    single v1 entry with no API-key siblings).
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
    parent.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    # Pre-condition: the legacy (parent, None) owner is what v1 produced.
    assert device.config_entry_id == parent.entry_id
    assert device.config_subentry_id is None
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    survivor = hass.config_entries.async_get_entry(parent.entry_id)
    assert survivor is not None
    assert survivor.version == SCHEMA_VERSION
    assert len(survivor.subentries) == 1
    sub = next(iter(survivor.subentries.values()))

    # Device is still owned by the parent entry, now via the new subentry.
    refreshed = device_registry.async_get(device.id)
    assert refreshed is not None
    assert refreshed.config_entry_id == parent.entry_id
    assert refreshed.config_subentry_id == sub.subentry_id


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


async def test_async_migrate_integration_rehomes_disabled_sibling_entities(
    hass: HomeAssistant,
) -> None:
    """Sibling entity/device CONFIG_ENTRY disablers remap during merge.

    When at least one sibling is enabled, a migrated sibling's entity/device
    entries should move from CONFIG_ENTRY-disabled to DEVICE/USER semantics.
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
            CONF_SHOW_ON_MAP: False,
        },
        title="sibling",
        disabled_by=ConfigEntryDisabler.USER,
    )
    parent.add_to_hass(hass)
    sibling.add_to_hass(hass)

    device_registry = mock_device_registry(hass)
    # Parent device keeps all_disabled=False for this API key set.
    device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    sibling_device = device_registry.async_get_or_create(
        config_entry_id=sibling.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-temperature",
        config_entry=sibling,
        device_id=sibling_device.id,
        disabled_by=er.RegistryEntryDisabler.CONFIG_ENTRY,
        original_name="Temp",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    migrated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == parent.entry_id
    assert migrated_entity.config_subentry_id is not None
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.DEVICE

    migrated_device = device_registry.async_get(sibling_device.id)
    assert migrated_device is not None
    assert migrated_device.disabled_by is dr.DeviceEntryDisabler.USER


@pytest.mark.parametrize(
    ("parent_disabled_by", "sibling_disabled_by", "entity_disabled_by"),
    [
        (None, ConfigEntryDisabler.USER, er.RegistryEntryDisabler.CONFIG_ENTRY),
        (None, None, er.RegistryEntryDisabler.DEVICE),
        (
            ConfigEntryDisabler.USER,
            ConfigEntryDisabler.USER,
            er.RegistryEntryDisabler.DEVICE,
        ),
    ],
)
async def test_async_migrate_integration_rehomes_shared_sensor_entities(
    hass: HomeAssistant,
    parent_disabled_by: ConfigEntryDisabler | None,
    sibling_disabled_by: ConfigEntryDisabler | None,
    entity_disabled_by: er.RegistryEntryDisabler,
) -> None:
    """A sibling's entities for a sensor the parent also lists survive merge.

    Devices are per config entry, so both entries hold a device for the
    shared sensor. The parent's is rehomed first and has no entities, and
    the sibling's entities must join it rather than be removed along with
    the sibling entry, staying disabled on the parent's enabled device.
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
        disabled_by=parent_disabled_by,
    )
    sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="sibling",
        disabled_by=sibling_disabled_by,
    )
    parent.add_to_hass(hass)
    sibling.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    sibling_device = device_registry.async_get_or_create(
        config_entry_id=sibling.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    parent_device = device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX1}-temperature",
        config_entry=sibling,
        device_id=sibling_device.id,
        disabled_by=entity_disabled_by,
        original_name="Temp",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(sibling.entry_id) is None
    subentries = list(parent.subentries.values())
    assert len(subentries) == 1

    migrated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_entry_id == parent.entry_id
    assert migrated_entity.config_subentry_id == subentries[0].subentry_id
    assert migrated_entity.device_id == parent_device.id
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.USER

    # The disable must survive an update to the enabled parent device
    device_registry.async_update_device(parent_device.id, sw_version="2.0")
    await hass.async_block_till_done()
    migrated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.disabled_by is er.RegistryEntryDisabler.USER


def _add_stale_parent_case(
    hass: HomeAssistant, *, sibling_has_device: bool
) -> tuple[MockConfigEntry, dr.DeviceEntry, dr.DeviceEntry | None, str]:
    """Add a parent holding a stale device for a sensor only a sibling lists.

    The stale device carries one entity of its own.
    Returns the parent, the stale device, the sibling's device, and the stale entity's ID.
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
            CONF_SHOW_ON_MAP: False,
        },
        title="sibling",
    )
    parent.add_to_hass(hass)
    sibling.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    stale_device = device_registry.async_get_or_create(
        config_entry_id=parent.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    sibling_device = (
        device_registry.async_get_or_create(
            config_entry_id=sibling.entry_id,
            identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
            name="TEST_SENSOR_INDEX2",
        )
        if sibling_has_device
        else None
    )

    stale_entity = er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-humidity",
        config_entry=parent,
        device_id=stale_device.id,
        original_name="Humidity",
    )
    return parent, stale_device, sibling_device, stale_entity.entity_id


def _subentry_ids(entry: MockConfigEntry) -> dict[int, str]:
    """Map each subentry's sensor index to its subentry ID."""
    return {
        int(sub.data[CONF_SENSOR_INDEX]): sub.subentry_id
        for sub in entry.subentries.values()
    }


async def test_async_migrate_integration_replaces_stale_parent_device(
    hass: HomeAssistant,
) -> None:
    """A sibling's live device replaces a stale parent device for its sensor.

    Moving the sibling's device onto the parent would collide with the stale one.
    The live device carries the user's settings and the ID automations reference, so it survives.
    Entities on either device end up on it, in the subentry for that sensor.
    A stale entity the disabled stale device disabled stays disabled on the enabled live device.
    """
    parent, stale_device, sibling_device, stale_entity_id = _add_stale_parent_case(
        hass, sibling_has_device=True
    )
    assert sibling_device is not None
    sibling = next(
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != parent.entry_id
    )

    area = ar.async_get(hass).async_create("Garden")
    device_registry = dr.async_get(hass)
    device_registry.async_update_device(
        sibling_device.id, area_id=area.id, name_by_user="Backyard"
    )
    device_registry.async_update_device(
        stale_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    entity_registry = er.async_get(hass)
    sibling_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-temperature",
        config_entry=sibling,
        device_id=sibling_device.id,
        original_name="Temp",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(sibling.entry_id) is None
    subentry_ids = _subentry_ids(parent)
    assert set(subentry_ids) == {TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2}

    assert device_registry.async_get(stale_device.id) is None
    live = device_registry.async_get(sibling_device.id)
    assert live is not None
    assert live.config_entry_id == parent.entry_id
    assert live.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]
    assert live.area_id == area.id
    assert live.name_by_user == "Backyard"
    assert live.disabled_by is None

    for entity_id, disabled_by in (
        (sibling_entity.entity_id, None),
        (stale_entity_id, er.RegistryEntryDisabler.USER),
    ):
        migrated = entity_registry.async_get(entity_id)
        assert migrated is not None
        assert migrated.config_entry_id == parent.entry_id
        assert migrated.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]
        assert migrated.device_id == sibling_device.id
        assert migrated.disabled_by is disabled_by


async def test_async_migrate_integration_live_device_wins_in_any_order(
    hass: HomeAssistant,
) -> None:
    """A live device replaces a stale parent device even after a deviceless sibling.

    The first sibling lists the sensor but holds no device for it, so it leaves the stale device for the second.
    """
    parent, stale_device, _, stale_entity_id = _add_stale_parent_case(
        hass, sibling_has_device=False
    )
    late_sibling = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX2],
            CONF_SHOW_ON_MAP: False,
        },
        title="late sibling",
    )
    late_sibling.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    live_device = device_registry.async_get_or_create(
        config_entry_id=late_sibling.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX2))},
        name="TEST_SENSOR_INDEX2",
    )
    entity_registry = er.async_get(hass)
    live_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX2}-temperature",
        config_entry=late_sibling,
        device_id=live_device.id,
        original_name="Temp",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries(DOMAIN) == [parent]
    subentry_ids = _subentry_ids(parent)
    assert device_registry.async_get(stale_device.id) is None
    live = device_registry.async_get(live_device.id)
    assert live is not None
    assert live.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]
    for entity_id in (live_entity.entity_id, stale_entity_id):
        migrated = entity_registry.async_get(entity_id)
        assert migrated is not None
        assert migrated.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]
        assert migrated.device_id == live_device.id


async def test_async_migrate_integration_adopts_stale_parent_device(
    hass: HomeAssistant,
) -> None:
    """A stale parent device joins the new subentry when the sibling has no device.

    Its own entity moves with it rather than being dropped by the device move.
    Another integration's entity on the device keeps its own entry and no subentry.
    """
    parent, stale_device, _, stale_entity_id = _add_stale_parent_case(
        hass, sibling_has_device=False
    )
    helper_entry = MockConfigEntry(domain="utility_meter")
    helper_entry.add_to_hass(hass)
    helper_entity = er.async_get(hass).async_get_or_create(
        "sensor",
        "utility_meter",
        "daily-humidity",
        config_entry=helper_entry,
        device_id=stale_device.id,
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    subentry_ids = _subentry_ids(parent)
    assert set(subentry_ids) == {TEST_SENSOR_INDEX1, TEST_SENSOR_INDEX2}

    adopted = dr.async_get(hass).async_get(stale_device.id)
    assert adopted is not None
    assert adopted.config_entry_id == parent.entry_id
    assert adopted.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]

    migrated = er.async_get(hass).async_get(stale_entity_id)
    assert migrated is not None
    assert migrated.config_subentry_id == subentry_ids[TEST_SENSOR_INDEX2]
    assert migrated.device_id == stale_device.id

    helper = er.async_get(hass).async_get(helper_entity.entity_id)
    assert helper is not None
    assert helper.config_entry_id == helper_entry.entry_id
    assert helper.config_subentry_id is None


async def test_async_migrate_integration_keeps_enabled_entities_enabled(
    hass: HomeAssistant,
) -> None:
    """An enabled entity moves with its device and stays enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="entry",
    )
    entry.add_to_hass(hass)

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(TEST_SENSOR_INDEX1))},
        name="TEST_SENSOR_INDEX1",
    )
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{TEST_SENSOR_INDEX1}-temperature",
        config_entry=entry,
        device_id=device.id,
        original_name="Temp",
    )
    await hass.async_block_till_done()

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    subentries = list(entry.subentries.values())
    assert len(subentries) == 1
    migrated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert migrated_entity is not None
    assert migrated_entity.config_subentry_id == subentries[0].subentry_id
    assert migrated_entity.device_id == device.id
    assert migrated_entity.disabled_by is None


async def test_async_migrate_integration_skips_future_parent_alignment(
    hass: HomeAssistant,
) -> None:
    """A parent entry above SCHEMA_VERSION is skipped in option alignment."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={
            CONF_LEGACY_SENSOR_INDICES: [TEST_SENSOR_INDEX1],
            CONF_SHOW_ON_MAP: False,
        },
        title="legacy",
    )
    future_parent = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION + 1,
        unique_id=TEST_NEW_API_KEY,
        data={CONF_API_KEY: TEST_NEW_API_KEY},
        options={CONF_SHOW_ON_MAP: False},
        title="future-parent",
    )
    future_parent.add_to_hass(hass)
    legacy_entry.add_to_hass(hass)

    # Distinct API keys: future_parent only exercises the second-pass
    # api_key_entries loop where version > SCHEMA_VERSION should be skipped.
    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    assert future_parent.version == SCHEMA_VERSION + 1
    assert future_parent.options[CONF_SHOW_ON_MAP] is False


def _add_entity(hass, entry, unique_id, disabled_by):
    return er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        config_entry=entry,
        disabled_by=disabled_by,
        original_name=unique_id,
    )


async def test_async_migrate_integration_reenables_default_true_entities(
    hass: HomeAssistant,
) -> None:
    """INTEGRATION-disabled entries flip to None when the current default is True.

    Covers the upgrade gap: PR #87 raised four diagnostics from disabled-by-
    default to enabled-by-default, but `entity_registry_enabled_default` only
    applies at first registration. Pre-existing installs would keep the
    disabled state without this reconciliation.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    sensor_entity = _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-last_seen",
        er.RegistryEntryDisabler.INTEGRATION,
    )
    org_entity = _add_entity(
        hass,
        entry,
        f"{entry.entry_id}-organization-consumption_rate",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    await async_migrate_integration(hass)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    sensor_after = registry.async_get(sensor_entity.entity_id)
    org_after = registry.async_get(org_entity.entity_id)
    assert sensor_after is not None
    assert org_after is not None
    assert sensor_after.disabled_by is None
    assert org_after.disabled_by is None


async def test_async_migrate_integration_preserves_user_disabled(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """USER-disabled entries are never re-enabled, even if current default is True."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    user_entity = _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-confidence",
        er.RegistryEntryDisabler.USER,
    )

    with caplog.at_level(logging.DEBUG, logger="custom_components.purpleair"):
        await async_migrate_integration(hass)
        await hass.async_block_till_done()

    user_after = er.async_get(hass).async_get(user_entity.entity_id)
    assert user_after is not None
    assert user_after.disabled_by is er.RegistryEntryDisabler.USER
    assert any("disabled_by=" in record.message for record in caplog.records)


async def test_async_migrate_integration_preserves_default_false_entities(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """INTEGRATION-disabled entries whose current default is False stay disabled.

    `rssi` and unknown-key orphans must not be touched by the reconciliation.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    rssi_entity = _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-rssi",
        er.RegistryEntryDisabler.INTEGRATION,
    )
    orphan_entity = _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-removed_from_code_long_ago",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    with caplog.at_level(logging.DEBUG, logger="custom_components.purpleair"):
        await async_migrate_integration(hass)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    rssi_after = registry.async_get(rssi_entity.entity_id)
    orphan_after = registry.async_get(orphan_entity.entity_id)
    assert rssi_after is not None
    assert orphan_after is not None
    assert rssi_after.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert orphan_after.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert any("unknown key=" in record.message for record in caplog.records)


async def test_async_migrate_integration_logs_info_on_reenable(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Re-enabling at least one entity emits an INFO summary.

    Pins the logging contract: operators must be able to see which entries
    were affected and how many were re-enabled without enabling DEBUG.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-last_seen",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    with caplog.at_level(logging.INFO, logger="custom_components.purpleair"):
        await async_migrate_integration(hass)
        await hass.async_block_till_done()

    assert any(
        "Re-enabled 1 entity registry entries" in record.message
        for record in caplog.records
    )


async def test_async_migrate_integration_logs_debug_on_skip_default_false(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """INTEGRATION-disabled entity whose default is still False emits a DEBUG skip.

    Pins the tracing contract: operators can identify why an entity was not
    re-enabled by setting the logger to DEBUG.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-rssi",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    with caplog.at_level(logging.DEBUG, logger="custom_components.purpleair"):
        await async_migrate_integration(hass)
        await hass.async_block_till_done()

    assert any("default=False" in record.message for record in caplog.records)


async def test_async_migrate_integration_logs_debug_scan_summary(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Reconciliation always emits a DEBUG scan-summary regardless of re-enable count.

    Pins the tracing contract: the total-scanned / total-re-enabled counts
    must be logged on every run so operators can confirm the pass executed.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=SCHEMA_VERSION,
        data={CONF_API_KEY: TEST_API_KEY},
        title=TITLE,
    )
    entry.add_to_hass(hass)
    _add_entity(
        hass,
        entry,
        f"{TEST_SENSOR_INDEX1}-last_seen",
        er.RegistryEntryDisabler.INTEGRATION,
    )

    with caplog.at_level(logging.DEBUG, logger="custom_components.purpleair"):
        await async_migrate_integration(hass)
        await hass.async_block_till_done()

    assert any(
        "Default reconciliation scanned" in record.message for record in caplog.records
    )
