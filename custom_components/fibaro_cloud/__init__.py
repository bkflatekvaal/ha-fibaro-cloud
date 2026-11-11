"""Fibaro Cloud devices and authentication lifecycle.

HA imports are deliberately lazy so the independent client also works in the CLI.
"""


PLATFORMS = ['sensor', 'binary_sensor', 'switch', 'light', 'climate', 'cover']

async def async_setup_entry(hass, entry):
    from homeassistant.core import callback
    from .coordinator import FibaroCoordinator
    from .runtime import CloudConnection

    connection = await hass.async_add_executor_job(CloudConnection, entry.data)
    coordinator = FibaroCoordinator(hass, entry, connection)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    from .selection import async_migrate_selection, async_remove_unselected
    from .registry import async_group_devices, async_migrate_batteries, async_sync_device_names
    async_migrate_selection(hass, entry, coordinator.data)
    async_migrate_batteries(hass, entry, coordinator.data)
    coordinator.hub_device_id = async_group_devices(hass, entry, coordinator.data)
    await async_remove_unselected(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def sync_names():
        async_sync_device_names(hass, entry, coordinator.data)

    entry.async_on_unload(coordinator.async_add_listener(sync_names))
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
