"""Fibaro covers with open/close, optional stop and position."""
from homeassistant.components.cover import ATTR_POSITION, CoverEntity, CoverEntityFeature
from homeassistant.exceptions import ServiceValidationError
from .entity import FibaroEntity, async_setup_platform_entities
from .readings import number


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform_entities(hass, entry, async_add_entities, 'cover', FibaroCover)


class FibaroCover(FibaroEntity, CoverEntity):
    @property
    def supported_features(self):
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        if 'stop' in self.actions:
            features |= CoverEntityFeature.STOP
        if 'setValue' in self.actions:
            features |= CoverEntityFeature.SET_POSITION
        return features

    @property
    def current_cover_position(self):
        value = number(self.properties.get('value'))
        return (0 if value <= 5 else 100 if value >= 95 else round(value)) if value is not None else None

    @property
    def is_closed(self):
        return self.current_cover_position == 0 if self.current_cover_position is not None else None

    async def async_open_cover(self, **kwargs):
        await self.async_action('open')

    async def async_close_cover(self, **kwargs):
        await self.async_action('close')

    async def async_stop_cover(self, **kwargs):
        await self.async_action('stop')

    async def async_set_cover_position(self, **kwargs):
        position = kwargs[ATTR_POSITION]
        if not 0 <= position <= 100:
            raise ServiceValidationError('Cover position must be between 0 and 100')
        await self.async_action('setValue', position)
