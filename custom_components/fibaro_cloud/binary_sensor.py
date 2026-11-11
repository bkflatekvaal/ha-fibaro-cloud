"""Motion, opening, smoke, heat, water, gas and generic binary sensor states."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from .capabilities import BINARY_TYPES, boolean
from .entity import FibaroEntity, async_setup_platform_entities


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform_entities(hass, entry, async_add_entities, 'binary_sensor', FibaroBinarySensor)


class FibaroBinarySensor(FibaroEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, device_id):
        super().__init__(coordinator, entry, device_id)
        self._attr_device_class = BINARY_TYPES.get(self.device['type'])

    @property
    def is_on(self):
        return boolean(self.properties.get('value'))
