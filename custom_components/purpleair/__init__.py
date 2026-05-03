"""The PurpleAir integration."""

from __future__ import annotations

from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_LEGACY_SENSOR_INDICES,
    CONF_SENSOR,
    CONF_SENSOR_INDEX,
    DOMAIN,
    LOGGER,
    SCHEMA_VERSION,
    TITLE,
)
from .coordinator import (
    PurpleAirConfigEntry,
    PurpleAirDataUpdateCoordinator,
    PurpleAirOrganizationCoordinator,
    PurpleAirRuntimeData,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# This integration only supports config-entry setup; it does not accept any
# YAML configuration. The helper below tells hassfest + HA's config_validation
# machinery that presence of `purpleair:` in configuration.yaml is not allowed
# (required for the CONFIG_SCHEMA hassfest check since we implement async_setup).
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ISSUE_LEGACY_MIGRATION_NO_SENSORS = "legacy_migration_no_sensors"


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up PurpleAir."""
    await async_migrate_integration(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Set up PurpleAir config entry."""
    sensors_coordinator = PurpleAirDataUpdateCoordinator(hass, entry)
    organization_coordinator = PurpleAirOrganizationCoordinator(hass, entry)
    entry.runtime_data = PurpleAirRuntimeData(
        sensors=sensors_coordinator,
        organization=organization_coordinator,
    )

    await sensors_coordinator.async_setup()
    await sensors_coordinator.async_config_entry_first_refresh()
    # Best-effort: the organization endpoint backs only diagnostic-only
    # sensors and the low-points repair issue. A failure here must not abort
    # config-entry setup — `async_config_entry_first_refresh` raises
    # ConfigEntryNotReady on transient failures, so use `async_refresh`
    # instead, which records the failure on the coordinator and lets the
    # next 24 h cycle retry. Auth errors still propagate via the coordinator's
    # `_async_update_data` and trigger reauth on the next attempt.
    await organization_coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_update_listener(
    hass: HomeAssistant, entry: PurpleAirConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: PurpleAirConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow device removal if the user has deleted the upstream PurpleAir sensor."""
    configured_indices = {
        str(subentry.data[CONF_SENSOR_INDEX])
        for subentry in config_entry.subentries.values()
    }
    device_indices = {
        identifier[1]
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
    }
    # Allow removal when the device no longer backs any configured subentry.
    return device_indices.isdisjoint(configured_indices)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entries."""
    # v1 schema:
    #   Sensor indices in options as a list of integers, duplicates are allowed and
    #   will not be removed during migration
    #   API key in data as a string, no duplicate API keys allowed
    # v2 schema:
    #   One or more config subentries, each subentry has a single sensor index,
    #   no duplicate sensors allowed
    #   API key in data as a string, no duplicate API keys allowed

    # Sort enabled entries first so we pick a stable parent per API key
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda entry: entry.disabled_by is not None,
    )

    if not any(entry.version == 1 for entry in entries):
        # Nothing to migrate, but still reconcile entity defaults: existing
        # registry entries created under older descriptions (or migrated from
        # v1) keep the disabled_by state from first registration, even after
        # the integration's defaults change. The reconciliation pass below
        # re-enables any entity that is INTEGRATION-disabled but whose current
        # description default is True.
        _async_reconcile_entity_defaults(hass)
        return

    # Track the chosen parent entry and whether all siblings are disabled
    api_key_entries: dict[str, tuple[ConfigEntry, bool]] = {}
    # Merge show_on_map across siblings that share the same API key
    show_on_map_by_api_key: dict[str, bool] = {}
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        api_key = entry.data[CONF_API_KEY]
        if api_key not in api_key_entries:
            # Pick the first entry (enabled if present) as parent
            all_disabled = all(
                candidate.disabled_by is not None
                for candidate in entries
                if candidate.data[CONF_API_KEY] == api_key
            )
            api_key_entries[api_key] = (entry, all_disabled)
            show_on_map_by_api_key[api_key] = entry.options.get(CONF_SHOW_ON_MAP, False)
        else:
            show_on_map_by_api_key[api_key] = show_on_map_by_api_key[
                api_key
            ] or entry.options.get(CONF_SHOW_ON_MAP, False)

        # Process every v1 entry (enabled or disabled). Earlier revisions of
        # this function only processed disabled siblings, on the assumption
        # that enabled entries would be migrated later by async_migrate_entry.
        # That left two enabled v1 entries sharing an API key ending up with
        # duplicate unique_ids after independent per-entry migration.
        if entry.version != 1:
            continue

        sensor_indices: list[int] | None = entry.options.get(CONF_LEGACY_SENSOR_INDICES)
        if not sensor_indices:
            _raise_legacy_no_sensors_issue(hass, entry)
            hass.config_entries.async_update_entry(entry, version=SCHEMA_VERSION)
            continue

        parent_entry, all_disabled = api_key_entries[api_key]

        for sensor_index in sensor_indices:
            # Skip if this sensor index already exists as a subentry
            if any(
                int(subentry.data[CONF_SENSOR_INDEX]) == sensor_index
                for subentry in parent_entry.subentries.values()
            ):
                continue

            device = device_registry.async_get_device(
                identifiers={(DOMAIN, str(sensor_index))}
            )
            subentry = ConfigSubentry(
                data=MappingProxyType({CONF_SENSOR_INDEX: sensor_index}),
                subentry_type=CONF_SENSOR,
                title=(
                    f"{device.name} ({sensor_index})"
                    if device and device.name
                    else f"Sensor {sensor_index}"
                ),
                unique_id=str(sensor_index),
            )

            # Create subentry under the chosen parent
            hass.config_entries.async_add_subentry(parent_entry, subentry)

            if device is not None:
                # Move entities tied to the old device to the new subentry
                entity_entries = er.async_entries_for_device(
                    entity_registry,
                    device.id,
                    include_disabled_entities=True,
                )

                for entity_entry in entity_entries:
                    entity_disabled_by = entity_entry.disabled_by
                    if (
                        entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                        and not all_disabled
                    ):
                        entity_disabled_by = er.RegistryEntryDisabler.DEVICE

                    entity_registry.async_update_entity(
                        entity_entry.entity_id,
                        config_entry_id=parent_entry.entry_id,
                        config_subentry_id=subentry.subentry_id,
                        disabled_by=entity_disabled_by,
                    )

                device_disabled_by = device.disabled_by
                if (
                    device_disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                    and not all_disabled
                ):
                    device_disabled_by = dr.DeviceEntryDisabler.USER

                device_registry.async_update_device(
                    device.id,
                    disabled_by=device_disabled_by,
                    add_config_entry_id=parent_entry.entry_id,
                    add_config_subentry_id=subentry.subentry_id,
                )

                if parent_entry.entry_id != entry.entry_id:
                    # Fully detach device from the migrated sibling entry
                    device_registry.async_update_device(
                        device.id,
                        remove_config_entry_id=entry.entry_id,
                    )
                elif None in device.config_entries_subentries.get(
                    parent_entry.entry_id, set()
                ):
                    # Drop only the legacy (parent_entry, None) link
                    device_registry.async_update_device(
                        device.id,
                        remove_config_entry_id=parent_entry.entry_id,
                        remove_config_subentry_id=None,
                    )

        if parent_entry.entry_id != entry.entry_id:
            # Remove the sibling entry after rehoming its sensors
            await hass.config_entries.async_remove(entry.entry_id)
            continue

        title: str = TITLE
        config_list = hass.config_entries.async_entries(
            domain=DOMAIN, include_disabled=True, include_ignore=True
        )
        if len(config_list) > 1:
            title = f"{TITLE} ({entry.title})"

        # Update the parent entry to the new schema
        hass.config_entries.async_update_entry(
            entry,
            title=title,
            unique_id=entry.data[CONF_API_KEY],
            data={CONF_API_KEY: entry.data[CONF_API_KEY]},
            options={
                CONF_SHOW_ON_MAP: show_on_map_by_api_key.get(api_key, False),
            },
            version=SCHEMA_VERSION,
        )

    for api_key, (parent_entry, _) in api_key_entries.items():
        if parent_entry.version > SCHEMA_VERSION:
            continue

        desired_options = {
            CONF_SHOW_ON_MAP: show_on_map_by_api_key.get(api_key, False),
        }

        if parent_entry.version == SCHEMA_VERSION:
            if (
                parent_entry.options.get(CONF_SHOW_ON_MAP, False)
                != desired_options[CONF_SHOW_ON_MAP]
            ):
                # Align options across siblings already on schema v2
                hass.config_entries.async_update_entry(
                    parent_entry,
                    options=desired_options,
                )

    _async_reconcile_entity_defaults(hass)


@callback
def _async_reconcile_entity_defaults(hass: HomeAssistant) -> None:
    """Re-enable entities whose description default flipped from False to True.

    HA's `entity_registry_enabled_default` only takes effect at first
    registration; existing registry entries keep their original `disabled_by`
    state. When the integration later raises an entity from disabled-by-default
    to enabled-by-default, users on pre-existing installs would still see it
    disabled — and with no in-product hint that they should re-enable it.

    This pass runs once per HA startup (cheap registry scan), and only ever
    *enables* — entries with `disabled_by=USER` (user explicitly disabled) and
    `disabled_by=None` (already enabled) are left untouched. The asymmetry is
    deliberate: silently disabling a user's enabled entity would be invasive,
    while re-enabling something the integration originally disabled and now
    wants on by default just delivers the new default.
    """
    # Local import: ``.sensor`` indirectly imports from this module.
    from .sensor import (  # noqa: PLC0415
        DESCRIPTIONS_BY_KEY,
        ORGANIZATION_DESCRIPTIONS_BY_KEY,
    )

    registry = er.async_get(hass)
    scanned_entities = 0
    reenabled_count = 0
    reenabled_by_entry: dict[str, int] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            scanned_entities += 1
            if entity_entry.disabled_by is not er.RegistryEntryDisabler.INTEGRATION:
                LOGGER.debug(
                    "Skipping %s during default reconciliation (disabled_by=%s)",
                    entity_entry.entity_id,
                    entity_entry.disabled_by,
                )
                continue
            # Per-sensor unique IDs are `{sensor_index}-{key}`; org-level are
            # `{entry_id}-organization-{key}`. Splitting on the rightmost `-`
            # yields the description key in both cases.
            key = entity_entry.unique_id.rsplit("-", 1)[-1]
            description = DESCRIPTIONS_BY_KEY.get(
                key
            ) or ORGANIZATION_DESCRIPTIONS_BY_KEY.get(key)
            if description is None:
                LOGGER.debug(
                    "Skipping %s during default reconciliation (unknown key=%s)",
                    entity_entry.entity_id,
                    key,
                )
                continue
            if description.entity_registry_enabled_default:
                registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
                reenabled_count += 1
                reenabled_by_entry[entry.entry_id] = (
                    reenabled_by_entry.get(entry.entry_id, 0) + 1
                )
                LOGGER.debug(
                    "Re-enabled %s during default reconciliation (entry_id=%s, key=%s)",
                    entity_entry.entity_id,
                    entry.entry_id,
                    key,
                )
            else:
                LOGGER.debug(
                    "Skipping %s during default reconciliation (default=False, key=%s)",
                    entity_entry.entity_id,
                    key,
                )

    if reenabled_count:
        per_entry_summary = ", ".join(
            f"{entry_id}={count}"
            for entry_id, count in sorted(reenabled_by_entry.items())
        )
        LOGGER.info(
            (
                "Re-enabled %d entity registry entries after default changes "
                "(%d config entries: %s)"
            ),
            reenabled_count,
            len(reenabled_by_entry),
            per_entry_summary,
        )
    LOGGER.debug(
        "Default reconciliation scanned %d entities and re-enabled %d",
        scanned_entities,
        reenabled_count,
    )


async def async_migrate_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Migrate config entry."""
    if entry.version == SCHEMA_VERSION:
        return True

    if entry.version != 1:
        LOGGER.error("Unsupported schema version %s", entry.version)
        return False

    LOGGER.info("Migrating schema version from %s to %s", entry.version, SCHEMA_VERSION)

    index_list: list[int] | None = entry.options.get(CONF_LEGACY_SENSOR_INDICES)

    if not index_list:
        _raise_legacy_no_sensors_issue(hass, entry)
        return hass.config_entries.async_update_entry(entry, version=SCHEMA_VERSION)

    dev_reg = dr.async_get(hass)
    dev_list = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in dev_list:
        identifiers = (
            int(identifier[1])
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        )
        sensor_index = next(identifiers, None)

        if sensor_index is None:
            LOGGER.debug("Device %s is missing a PurpleAir identifier", device.id)
            continue

        if sensor_index not in index_list:
            LOGGER.debug(
                "Device %s sensor index %s not found in options; skipping",
                device.id,
                sensor_index,
            )
            continue

        # Remove the old device entry; a new one is recreated under the subentry.
        dev_reg.async_remove_device(device.id)

        # Keep subentry logic in sync with config_flow.py:async_step_select_sensor()
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_SENSOR_INDEX: sensor_index}),
                subentry_type=CONF_SENSOR,
                title=f"{device.name} ({sensor_index})",
                unique_id=str(sensor_index),
            ),
        )

    # Keep entry logic in sync with config_flow.py:async_step_api_key()
    title: str = TITLE
    config_list = hass.config_entries.async_entries(
        domain=DOMAIN, include_disabled=True, include_ignore=True
    )
    if len(config_list) > 1:
        title = f"{TITLE} ({entry.title})"

    return hass.config_entries.async_update_entry(
        entry,
        title=title,
        unique_id=entry.data[CONF_API_KEY],
        data={CONF_API_KEY: entry.data[CONF_API_KEY]},
        options={CONF_SHOW_ON_MAP: entry.options.get(CONF_SHOW_ON_MAP, False)},
        version=SCHEMA_VERSION,
    )


@callback
def _raise_legacy_no_sensors_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Raise a repair issue when a v1 entry had no configured sensors."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_LEGACY_MIGRATION_NO_SENSORS}_{entry.entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_MIGRATION_NO_SENSORS,
        translation_placeholders={"title": entry.title},
    )


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
