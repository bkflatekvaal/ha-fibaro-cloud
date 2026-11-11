"""Capability discovery and real HA services with all device I/O simulated."""
import json
from copy import deepcopy
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.components.climate import HVACMode, HVACAction
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.fibaro_cloud.cloud import CloudClient, ProbeError, AuthenticationError
from custom_components.fibaro_cloud.readings import project_devices
from custom_components.fibaro_cloud.runtime import CloudConnection
from custom_components.fibaro_cloud.climate import FibaroClimate
from custom_components.fibaro_cloud.light import FibaroLight
from custom_components.fibaro_cloud.cover import FibaroCover
from custom_components.fibaro_cloud.coordinator import FibaroCoordinator
from custom_components.fibaro_cloud.selection import device_choices
from test_ha import hass, entry, SNAPSHOT, CONFIG


def raw_devices():
    return [
        {'id': 1, 'type': 'com.fibaro.zwavePrimaryController', 'parentId': 0,
         'actions': {'turnOn': 0, 'turnOff': 0}, 'properties': {'value': False}},
        {'id': 10, 'name': 'Physical module', 'parentId': 1, 'properties': {}},
        {'id': 11, 'name': 'Room', 'parentId': 10, 'type': 'com.fibaro.temperatureSensor',
         'properties': {'value': 15, 'unit': 'C'}},
        {'id': 12, 'name': 'Relay', 'parentId': 10, 'type': 'com.fibaro.binarySwitch',
         'actions': {'turnOn': 0, 'turnOff': 0}, 'properties': {'value': False}},
        {'id': 13, 'name': 'Light', 'parentId': 10, 'type': 'com.fibaro.multilevelSwitch',
         'actions': {'turnOn': 0, 'turnOff': 0, 'setValue': 1}, 'properties': {'value': 50, 'isLight': True}},
        {'id': 14, 'name': 'Motion', 'parentId': 10, 'type': 'com.fibaro.motionSensor',
         'properties': {'value': True}},
        {'id': 15, 'name': 'Shutter', 'parentId': 10,
         'actions': {'open': 0, 'close': 0, 'stop': 0, 'setValue': 1}, 'properties': {'value': 99}},
        {'id': 144, 'name': 'Thermostat', 'parentId': 0, 'type': 'com.fibaro.hvacSystem',
         'actions': {'setHeatingThermostatSetpoint': 1, 'setThermostatMode': 1},
         'properties': {'unit': 'C', 'devices': [11, 12], 'thermostatMode': 'Heat',
                        'supportedThermostatModes': ['Off', 'Heat'], 'thermostatOperatingState': 'Idle',
                        'heatingThermostatSetpoint': 14, 'heatingThermostatSetpointCapabilitiesMin': 4,
                        'heatingThermostatSetpointCapabilitiesMax': 30, 'heatingThermostatSetpointStep': {'C': 0.5}}},
    ]


def snapshot(raw=None):
    return SNAPSHOT | {'devices': project_devices(raw or raw_devices()), 'device_count': 2}


@pytest.mark.asyncio
async def test_actual_ha_services_control_and_confirm_reported_state(hass):
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    config._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    hass.config_entries._entries[config.entry_id] = config
    hass.config_entries.async_update_entry(config, options={'selected_devices': ['10', '144']})
    raw = raw_devices()
    byid = {d['id']: d for d in raw}

    def command(source, action, args):
        props = byid[source]['properties']
        if action == 'turnOn': props['value'] = True
        elif action == 'turnOff': props['value'] = False
        elif action == 'setHeatingThermostatSetpoint': props['heatingThermostatSetpoint'] = args[0]
        elif action == 'setThermostatMode': props['thermostatMode'] = args[0]
        elif action == 'setValue': props['value'] = args[0]

    with patch('custom_components.fibaro_cloud.runtime.CloudConnection') as cls:
        connection = cls.return_value
        connection.snapshot.side_effect = lambda: snapshot(raw)
        connection.action.side_effect = command
        assert await async_setup_component(hass, 'fibaro_cloud', {})
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        def entity(domain, source):
            return registry.async_get_entity_id(domain, 'fibaro_cloud', f'TEST_{source}_{domain}')
        climate, switch, light, cover = entity('climate', 144), entity('switch', 12), entity('light', 13), entity('cover', 15)
        assert all((climate, switch, light, cover, entity('binary_sensor', 14)))
        state = hass.states.get(climate)
        assert state.state == 'heat'
        assert state.attributes['current_temperature'] == 15
        assert state.attributes['temperature'] == 14
        assert state.attributes['min_temp'] == 4
        assert state.attributes['max_temp'] == 30
        await hass.services.async_call('climate', 'set_temperature', {'entity_id': climate, 'temperature': 17.5}, blocking=True)
        connection.action.assert_called_with(144, 'setHeatingThermostatSetpoint', [17.5])
        assert hass.states.get(climate).attributes['temperature'] == 17.5
        await hass.services.async_call('climate', 'set_hvac_mode', {'entity_id': climate, 'hvac_mode': 'off'}, blocking=True)
        assert hass.states.get(climate).state == 'off'
        await hass.services.async_call('switch', 'turn_on', {'entity_id': switch}, blocking=True)
        connection.action.assert_called_with(12, 'turnOn', [])
        assert hass.states.get(switch).state == 'on'
        await hass.services.async_call('light', 'turn_on', {'entity_id': light, 'brightness': 128}, blocking=True)
        connection.action.assert_called_with(13, 'setValue', [50])
        await hass.services.async_call('cover', 'set_cover_position', {'entity_id': cover, 'position': 50}, blocking=True)
        connection.action.assert_called_with(15, 'setValue', [50])
        calls = connection.action.call_count
        with pytest.raises((ServiceValidationError, ValueError)):
            await hass.services.async_call('climate', 'set_temperature', {'entity_id': climate, 'temperature': 99}, blocking=True)
        assert connection.action.call_count == calls
        # No optimistic state and no automatic command replay on timeout.
        connection.action.side_effect = ProbeError('Network/TLS connection failed or timed out.')
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call('switch', 'turn_off', {'entity_id': switch}, blocking=True)
        assert connection.action.call_count == calls + 1
        assert hass.states.get(switch).state == 'on'
        coordinator = config.runtime_data
        assert await hass.config_entries.async_unload(config.entry_id)
        assert coordinator._cancel_confirmation is None
        assert not coordinator._listeners


def test_all_capabilities_are_selectable_but_controllers_are_not():
    devices = snapshot()['devices']
    assert 1 not in devices
    assert {d['platform'] for d in devices.values()} >= {'climate', 'switch', 'light', 'cover', 'binary_sensor'}
    assert set(device_choices(snapshot())) == {'10', '144'}
    assert devices[144]['properties']['devices'] == [11, 12]


@pytest.mark.asyncio
async def test_climate_units_limits_and_unlinked_temperature(hass):
    config = entry()
    connection = Mock()
    coordinator = FibaroCoordinator(hass, config, connection)
    data = snapshot()
    coordinator.async_set_updated_data(data)
    climate = FibaroClimate(coordinator, config, 144)
    assert climate.native_current_temperature == 15
    assert climate.native_target_temperature == 14
    assert climate.hvac_action == HVACAction.IDLE
    assert climate.hvac_modes == [HVACMode.OFF, HVACMode.HEAT]
    data['devices'][144]['properties']['unit'] = 'F'
    assert climate.native_current_temperature == 59
    data['devices'][144]['properties'].pop('devices')
    assert climate.native_current_temperature is None  # Never substitute the setpoint.
    with pytest.raises(ServiceValidationError):
        await climate.async_set_hvac_mode(HVACMode.COOL)
    data['devices'][144]['properties']['unit'] = 'unknown'
    assert not climate.available
    with pytest.raises(ServiceValidationError):
        await climate.async_set_temperature(temperature=15)
    connection.action.assert_not_called()
    await coordinator.async_shutdown()


def test_action_transport_encodes_post_body_and_handles_empty_ack():
    client = CloudClient()
    client.session = {'user': 'a&b', 'tempKey': 'x+y'}
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b''
    client.opener.open = Mock(return_value=response)
    client.call_action('TEST', 144, 'setHeatingThermostatSetpoint', [14.5], basic_token='dummy')
    request = client.opener.open.call_args.args[0]
    assert request.get_method() == 'POST'
    assert parse_qs(urlsplit(request.full_url).query)['req'] == ['/api/devices/144/action/setHeatingThermostatSetpoint']
    assert json.loads(request.data) == {'args': [14.5]}
    assert request.get_header('Content-type') == 'application/json'
    assert request.get_header('Authorization') == 'Basic dummy'
    response.read.return_value = b'<html>Sign in</html>'
    with pytest.raises(ProbeError):
        client.call_action('TEST', 144, 'setHeatingThermostatSetpoint', [14.5])
    response.read.return_value = b'{"error":"rejected"}'
    with pytest.raises(ProbeError):
        client.call_action('TEST', 144, 'setHeatingThermostatSetpoint', [14.5])


@pytest.mark.parametrize('error', [AuthenticationError('Rejected'), ProbeError('Timeout')])
def test_write_failure_is_never_replayed(error):
    client = Mock(session={'user': 'dummy', 'tempKey': 'dummy'})
    client.read_api.side_effect = [{'serialNumber': 'TEST'}, raw_devices()]
    connection = CloudConnection(CONFIG, client)
    connection.snapshot()
    client.call_action.side_effect = error
    with pytest.raises(ProbeError):
        connection.action(144, 'setHeatingThermostatSetpoint', [14.5])
    client.call_action.assert_called_once()
    client.login.assert_not_called()
    with pytest.raises(ProbeError):
        connection.action(144, 'setHeatingThermostatSetpoint', [])
    with pytest.raises(ProbeError):
        connection.action(144, 'removeDevice', [])
    assert client.call_action.call_count == 1


@pytest.mark.asyncio
async def test_unselected_and_unavailable_devices_cannot_be_controlled(hass):
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    hass.config_entries.async_update_entry(config, options={'selected_devices': ['10']})
    connection = Mock()
    coordinator = FibaroCoordinator(hass, config, connection)
    coordinator.async_set_updated_data(snapshot())
    with pytest.raises(HomeAssistantError):
        await coordinator.async_action(144, 'setThermostatMode', ['Off'])
    coordinator.data['devices'][12]['available'] = False
    with pytest.raises(HomeAssistantError):
        await coordinator.async_action(12, 'turnOn', [])
    connection.action.assert_not_called()
    await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_light_color_low_brightness_and_cover_endpoints(hass):
    config = entry()
    connection = Mock()
    coordinator = FibaroCoordinator(hass, config, connection)
    coordinator.async_set_updated_data(snapshot())
    coordinator.async_action = Mock()
    from unittest.mock import AsyncMock
    coordinator.async_action = AsyncMock()
    light = FibaroLight(coordinator, config, 13)
    await light.async_turn_on(brightness=1)
    coordinator.async_action.assert_awaited_with(13, 'setValue', [1])
    cover = FibaroCover(coordinator, config, 15)
    assert cover.current_cover_position == 100
    await cover.async_set_cover_position(position=100)
    coordinator.async_action.assert_awaited_with(15, 'setValue', [100])
    raw = raw_devices()
    raw[4]['actions']['setColor'] = 4
    raw[4]['type'] = 'com.fibaro.RGBWController'
    raw[4]['properties']['color'] = '10,20,30,40'
    coordinator.async_set_updated_data(snapshot(raw))
    assert light.rgbw_color == (10, 20, 30, 40)
    await light.async_turn_on(rgbw_color=(50, 60, 70, 80))
    coordinator.async_action.assert_awaited_with(13, 'setColor', [50, 60, 70, 80])
    await coordinator.async_shutdown()


@pytest.mark.parametrize('args', [[float('nan')], [float('inf')], {'args': []}, [object()]])
def test_invalid_action_arguments_never_reach_transport(args):
    client = CloudClient()
    client.session = {'user': 'dummy', 'tempKey': 'dummy'}
    client.request = Mock()
    with pytest.raises(ProbeError):
        client.call_action('TEST', 144, 'setHeatingThermostatSetpoint', args)
    client.request.assert_not_called()


@pytest.mark.asyncio
async def test_command_auth_failure_starts_reauthentication_once(hass):
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    hass.config_entries.async_update_entry(config, options={'selected_devices': ['144']})
    connection = Mock()
    connection.action.side_effect = AuthenticationError('Rejected')
    coordinator = FibaroCoordinator(hass, config, connection)
    coordinator.async_set_updated_data(snapshot())
    with patch.object(type(config), 'async_start_reauth') as reauth:
        with pytest.raises(HomeAssistantError):
            await coordinator.async_action(144, 'setThermostatMode', ['Heat'])
        reauth.assert_called_once_with(hass)
    connection.action.assert_called_once_with(144, 'setThermostatMode', ['Heat'])
    assert coordinator._cancel_confirmation is None
    await coordinator.async_shutdown()
