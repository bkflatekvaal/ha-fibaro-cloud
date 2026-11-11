"""Shared device metadata and discovery for non-numeric Fibaro entities."""
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HUB_SERIAL
from .selection import selected_device_ids


async def async_setup_platform_entities(hass, entry, async_add_entities, platform, entity_class):
    coordinator = entry.runtime_data
    selected = set(selected_device_ids(coordinator.data, entry.options))
    known = set()

    @callback
    def discover():
        added = []
        for source, device in coordinator.data.get('devices', {}).items():
            if device.get('platform') != platform or str(device.get('main_id', source)) not in selected:
                continue
            if source not in known:
                known.add(source)
                added.append(entity_class(coordinator, entry, source))
        if added:
            async_add_entities(added)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class FibaroEntity(CoordinatorEntity):
    """An entity follows the source endpoint while sharing its physical device."""
    _attr_has_entity_name = False

    def __init__(self, coordinator, entry, device_id):
        super().__init__(coordinator)
        self._device_id = device_id
        device = coordinator.data['devices'][device_id]
        serial = entry.data[HUB_SERIAL]
        self._platform = device['platform']
        self._attr_unique_id = f'{serial}_{device_id}_{self._platform}'
        self._attr_name = device['name']
        self._attr_entity_registry_visible_default = device.get('visible', True)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{serial}_{device.get('main_id', device_id)}")},
            name=device.get('main_name', device['name']),
            model=device.get('main_type', device['type']),
            manufacturer=device.get('manufacturer'),
            via_device_id=getattr(coordinator, 'hub_device_id', None),
        )

    @property
    def device(self):
        return self.coordinator.data.get('devices', {}).get(self._device_id, {})

    @property
    def properties(self):
        return self.device.get('properties', {})

    @property
    def actions(self):
        return self.device.get('actions', {})

    @property
    def available(self):
        return (super().available and self.device.get('available', False)
                and self.device.get('platform') == self._platform)

    @property
    def extra_state_attributes(self):
        return {'fibaro_id': self._device_id}

    async def async_action(self, name, *args):
        await self.coordinator.async_action(self._device_id, name, list(args))
