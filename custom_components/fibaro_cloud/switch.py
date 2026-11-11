"""Fibaro on/off switches."""
from homeassistant.components.switch import SwitchEntity
from .capabilities import boolean
from .entity import FibaroEntity, async_setup_platform_entities


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform_entities(hass, entry, async_add_entities, 'switch', FibaroSwitch)


class FibaroSwitch(FibaroEntity, SwitchEntity):
    @property
    def is_on(self):
        return boolean(self.properties.get('value', self.properties.get('state')))

    async def async_turn_on(self, **kwargs):
        await self.async_action('turnOn')

    async def async_turn_off(self, **kwargs):
        await self.async_action('turnOff')
