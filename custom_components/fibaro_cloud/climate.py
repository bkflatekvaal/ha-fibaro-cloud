"""Fibaro thermostat state, HVAC mode and temperature control."""
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util.unit_conversion import TemperatureConverter

from .entity import FibaroEntity, async_setup_platform_entities
from .readings import number

MODES = {'Off': HVACMode.OFF, 'Heat': HVACMode.HEAT, 'Cool': HVACMode.COOL,
         'Auto': HVACMode.AUTO, 'FanOnly': HVACMode.FAN_ONLY, 'Dry': HVACMode.DRY}
STATES = {'Idle': HVACAction.IDLE, 'Heating': HVACAction.HEATING, 'Cooling': HVACAction.COOLING,
          'FanOnly': HVACAction.FAN}
TARGET_ACTIONS = ('setHeatingThermostatSetpoint', 'setCoolingThermostatSetpoint',
                  'setTargetLevel', 'setThermostatSetpoint')


async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform_entities(hass, entry, async_add_entities, 'climate', FibaroClimate)


class FibaroClimate(FibaroEntity, ClimateEntity):
    _enable_turn_on_off_backwards_compatibility = False

    @property
    def native_temperature_unit(self):
        return UnitOfTemperature.FAHRENHEIT if self.properties.get('unit') in ('F', '°F') else UnitOfTemperature.CELSIUS

    @property
    def available(self):
        return super().available and self.properties.get('unit') in ('C', 'F', '°C', '°F')

    @property
    def supported_features(self):
        features = ClimateEntityFeature(0)
        if any(a in self.actions for a in TARGET_ACTIONS):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if 'setThermostatMode' in self.actions and HVACMode.OFF in self.hvac_modes:
            features |= ClimateEntityFeature.TURN_OFF
            if any(m != HVACMode.OFF for m in self.hvac_modes):
                features |= ClimateEntityFeature.TURN_ON
        return features

    @property
    def hvac_modes(self):
        modes = self.properties.get('supportedThermostatModes') or [self.properties.get('thermostatMode', 'Heat')]
        return list(dict.fromkeys(MODES[m] for m in modes if m in MODES))

    @property
    def hvac_mode(self):
        return MODES.get(self.properties.get('thermostatMode', 'Heat'))

    @property
    def hvac_action(self):
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return STATES.get(self.properties.get('thermostatOperatingState'))

    @property
    def native_target_temperature(self):
        if self.hvac_mode == HVACMode.COOL:
            return number(self.properties.get('coolingThermostatSetpoint'))
        return number(self.properties.get('heatingThermostatSetpointFuture',
                       self.properties.get('heatingThermostatSetpoint', self.properties.get('targetLevel'))))

    @property
    def native_current_temperature(self):
        for prop in ('currentTemperature', 'temperature'):
            if (value := number(self.properties.get(prop))) is not None:
                return value
        # Linked HVAC devices explicitly list their temperature sensor and actuators.
        linked = self.properties.get('devices') or []
        for key in ('mainTemperatureSensor', 'temperatureSensorID', 'temperatureSensor'):
            if type(self.properties.get(key)) is int:
                linked = [self.properties[key], *linked]
        for source in linked:
            device = self.coordinator.data.get('devices', {}).get(source, {})
            reading = device.get('readings', {}).get('value', {})
            if reading.get('kind') == 'temperature' and device.get('available') and reading.get('value') is not None:
                return TemperatureConverter.convert(reading['value'], reading['unit'], self.native_temperature_unit)
        return None

    @property
    def min_temp(self):
        value = number(self.properties.get('heatingThermostatSetpointCapabilitiesMin'))
        return value if value is not None else (39.2 if self.native_temperature_unit == '°F' else 4)

    @property
    def max_temp(self):
        value = number(self.properties.get('heatingThermostatSetpointCapabilitiesMax'))
        return value if value is not None else (86 if self.native_temperature_unit == '°F' else 30)

    @property
    def target_temperature_step(self):
        step = self.properties.get('heatingThermostatSetpointStep')
        value = number(step.get('F' if self.native_temperature_unit == '°F' else 'C')) if isinstance(step, dict) else number(step)
        return value if value is not None and value > 0 else 0.5

    async def async_set_temperature(self, **kwargs):
        temperature = number(kwargs.get(ATTR_TEMPERATURE))
        if not self.available or temperature is None or not self.min_temp <= temperature <= self.max_temp:
            raise ServiceValidationError('Temperature is unavailable or outside the thermostat limits')
        selected_mode = kwargs.get('hvac_mode', self.hvac_mode)
        if 'hvac_mode' in kwargs and kwargs['hvac_mode'] != self.hvac_mode:
            await self.async_set_hvac_mode(kwargs['hvac_mode'])
        if selected_mode == HVACMode.COOL and 'setCoolingThermostatSetpoint' in self.actions:
            await self.async_action('setCoolingThermostatSetpoint', temperature)
        elif 'setHeatingThermostatSetpoint' in self.actions:
            await self.async_action('setHeatingThermostatSetpoint', temperature)
        elif 'setThermostatSetpoint' in self.actions:
            await self.async_action('setThermostatSetpoint', self.properties.get('thermostatMode', 'Heat'), temperature)
        elif 'setTargetLevel' in self.actions:
            await self.async_action('setTargetLevel', temperature)
        else:
            raise ServiceValidationError('This thermostat does not support temperature control')

    async def async_set_hvac_mode(self, hvac_mode):
        mode = next((m for m in self.properties.get('supportedThermostatModes', []) if MODES.get(m) == hvac_mode), None)
        if mode is None or 'setThermostatMode' not in self.actions:
            raise ServiceValidationError('Unsupported thermostat mode')
        await self.async_action('setThermostatMode', mode)

    async def async_turn_off(self):
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
        mode = next((m for m in self.hvac_modes if m != HVACMode.OFF), None)
        if mode is None:
            raise ServiceValidationError('No active thermostat mode is supported')
        await self.async_set_hvac_mode(mode)
