"""Fibaro lights with on/off, brightness and RGBW where advertised."""
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_RGBW_COLOR, ColorMode, LightEntity
from homeassistant.exceptions import ServiceValidationError
from .capabilities import boolean
from .entity import FibaroEntity, async_setup_platform_entities
from .readings import number


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform_entities(hass, entry, async_add_entities, 'light', FibaroLight)


class FibaroLight(FibaroEntity, LightEntity):
    @property
    def supported_color_modes(self):
        if 'setColor' in self.actions:
            return {ColorMode.RGBW if self.device.get("rgbw") else ColorMode.RGB}
        if 'setBrightness' in self.actions or 'setValue' in self.actions:
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def color_mode(self):
        return next(iter(self.supported_color_modes))

    @property
    def is_on(self):
        value = self.properties.get('value', self.properties.get('state'))
        if (parsed := number(value)) is not None:
            return parsed > 0
        return boolean(value)

    @property
    def brightness(self):
        value = number(self.properties.get('brightness', self.properties.get('value')))
        return round((100 if value > 98 else max(0, value)) * 2.55) if value is not None else None

    @property
    def rgbw_color(self):
        try:
            color = tuple(int(v) for v in self.properties.get('color', '').split(','))
        except (ValueError, AttributeError):
            return None
        return color if len(color) == 4 and all(0 <= v <= 255 for v in color) else None

    @property
    def rgb_color(self):
        color = self.rgbw_color
        return color[:3] if color else None

    async def async_turn_on(self, **kwargs):
        if ATTR_RGB_COLOR in kwargs:
            if 'setColor' not in self.actions:
                raise ServiceValidationError('This Fibaro light does not support RGB')
            await self.async_action('setColor', *kwargs[ATTR_RGB_COLOR], 0)
        if ATTR_RGBW_COLOR in kwargs:
            if 'setColor' not in self.actions:
                raise ServiceValidationError('This Fibaro light does not support RGBW')
            await self.async_action('setColor', *kwargs[ATTR_RGBW_COLOR])
        if ATTR_BRIGHTNESS in kwargs:
            action = 'setBrightness' if 'setBrightness' in self.actions else 'setValue'
            if action not in self.actions:
                raise ServiceValidationError('This Fibaro light does not support brightness')
            await self.async_action(action, max(1 if kwargs[ATTR_BRIGHTNESS] > 0 else 0, min(99, round(kwargs[ATTR_BRIGHTNESS] / 2.55))))
        elif ATTR_RGBW_COLOR not in kwargs and ATTR_RGB_COLOR not in kwargs:
            await self.async_action('turnOn')

    async def async_turn_off(self, **kwargs):
        await self.async_action('turnOff')
