"""Recognized capabilities and the device properties used by entity platforms."""
CONTROLLERS = {
    'com.fibaro.zwavePrimaryController', 'com.fibaro.zigbeePrimaryController',
    'com.fibaro.niceEngine', 'com.fibaro.knxEngine',
}
ACTIONS = {
    'turnOn', 'turnOff', 'setValue', 'setBrightness', 'setColor',
    'open', 'close', 'stop', 'setValue2',
    'setHeatingThermostatSetpoint', 'setCoolingThermostatSetpoint',
    'setTargetLevel', 'setThermostatSetpoint', 'setThermostatMode',
}
BINARY_TYPES = {
    'com.fibaro.motionSensor': 'motion',
    'com.fibaro.doorSensor': 'door', 'com.fibaro.doorWindowSensor': 'opening',
    'com.fibaro.windowSensor': 'window', 'com.fibaro.floodSensor': 'moisture',
    'com.fibaro.waterSensor': 'moisture', 'com.fibaro.smokeSensor': 'smoke',
    'com.fibaro.heatDetector': 'heat', 'com.fibaro.gasDetector': 'gas',
    'com.fibaro.coSensor': 'carbon_monoxide', 'com.fibaro.binarySensor': None,
}
STATE_PROPERTIES = {
    'value', 'value2', 'state', 'brightness', 'color', 'unit', 'isLight',
    'thermostatMode', 'supportedThermostatModes', 'thermostatOperatingState',
    'temperature', 'currentTemperature', 'heatingThermostatSetpoint',
    'coolingThermostatSetpoint', 'heatingThermostatSetpointFuture',
    'heatingThermostatSetpointCapabilitiesMin', 'heatingThermostatSetpointCapabilitiesMax',
    'heatingThermostatSetpointStep', 'coolingThermostatSetpointCapabilitiesMin',
    'coolingThermostatSetpointCapabilitiesMax', 'mainTemperatureSensor', 'temperatureSensorID',
    'temperatureSensor', 'devices', 'targetLevel', 'endPointId',
}


def boolean(value):
    if value in (True, 1, 'true', '1'):
        return True
    if value in (False, 0, 'false', '0'):
        return False
    return None


def platform_for(device):
    kind = device.get('type', '')
    if kind in CONTROLLERS or kind == 'com.fibaro.zwaveDevice':
        return None
    props = device.get('properties') or {}
    actions = device.get('actions') or {}
    if kind in {'com.fibaro.hvac', 'com.fibaro.hvacSystem', 'com.fibaro.setpoint',
                'com.fibaro.thermostatDanfoss', 'com.fibaro.FGT001'} or any(
                    a in actions for a in ('setHeatingThermostatSetpoint', 'setThermostatSetpoint')):
        return 'climate'
    if 'open' in actions and 'close' in actions:
        return 'cover'
    if 'turnOn' in actions and 'turnOff' in actions:
        if props.get('isLight') is True or kind in {'com.fibaro.colorController', 'com.fibaro.FGD212'} or 'setBrightness' in actions:
            return 'light'
        return 'switch'
    if kind in BINARY_TYPES or (device.get('baseType') in {
            'com.fibaro.binarySensor', 'com.fibaro.securitySensor', 'com.fibaro.lifeDangerSensor'}
            and boolean(props.get('value')) is not None):
        return 'binary_sensor'
    return None


def has_entities(device):
    return bool(device.get('readings') or device.get('platform'))
