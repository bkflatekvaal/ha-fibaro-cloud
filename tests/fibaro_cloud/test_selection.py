"""Whole-device options, migration, discovery and cleanup using real HA registries."""
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.setup import async_setup_component

from custom_components.fibaro_cloud.config_flow import FibaroCloudConfigFlow
from custom_components.fibaro_cloud.readings import project_devices
from custom_components.fibaro_cloud.cloud import ProbeError
from test_ha import hass, entry, SNAPSHOT


def snapshot():
    return SNAPSHOT | {"devices": project_devices([
        {"id": 1, "name": "Kitchen", "type": "com.fibaro.temperatureSensor", "properties": {"value": 21, "unit": "C", "batteryLevel": 80}},
        {"id": 2, "name": "Cabin", "properties": {"power": 20}},
    ])}


@pytest.mark.asyncio
async def test_initial_selection_and_validation(hass):
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = "fibaro_cloud"
    flow.context = {"source": "user"}
    flow._snapshot = snapshot()
    flow._selected = []
    flow._options = {}
    flow._data = {}
    flow._title = "Test"
    result = await flow.async_step_devices()
    assert result["data_schema"]({}) == {"selected_devices": []}
    result = await flow.async_step_devices({"selected_devices": ["999"]})
    assert result["reason"] == "invalid_selection"
    result = await flow.async_step_devices({"selected_devices": ["1"]})
    assert result['type'] == 'create_entry'
    assert result["options"] == {"selected_devices": ["1"]}


@pytest.mark.asyncio
async def test_options_preserve_missing_and_handle_failure(hass):
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    hass.config_entries.async_update_entry(config, options={"selected_entities": ["1:value", "9:power"]})
    flow = FibaroCloudConfigFlow.async_get_options_flow(config)
    flow.hass = hass
    flow.handler = config.entry_id
    with patch("custom_components.fibaro_cloud.config_flow.CloudConnection") as connection:
        connection.return_value.snapshot.side_effect = ProbeError("Network")
        result = await flow.async_step_init()
        assert result["reason"] == "cannot_connect"
        assert config.options["selected_entities"] == ["1:value", "9:power"]
        connection.return_value.snapshot.side_effect = None
        connection.return_value.snapshot.return_value = snapshot()
        result = await flow.async_step_init()
        assert result["data_schema"]({}) == {"selected_devices": ["1", "9"]}
        result = await flow.async_step_devices({"selected_devices": ["9"]})
        assert result["data"] == {"selected_devices": ["9"]}


@pytest.mark.asyncio
async def test_options_reload_removes_devices_and_adds_new_readings(hass):
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    config._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    hass.config_entries._entries[config.entry_id] = config
    hass.config_entries.async_update_entry(config, options={"selected_entities": ["1:value", "2:power"]})
    with patch("custom_components.fibaro_cloud.runtime.CloudConnection") as connection, patch("custom_components.fibaro_cloud.config_flow.CloudConnection") as flow_connection:
        connection.return_value.snapshot.return_value = snapshot()
        flow_connection.return_value.snapshot.return_value = snapshot()
        assert await async_setup_component(hass, "fibaro_cloud", {})
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        def ids():
            return {e.unique_id for e in er.async_entries_for_config_entry(registry, config.entry_id)}
        assert config.options == {"selected_devices": ["1", "2"]}
        assert ids() == {"TEST_device_count", "TEST_1_value", "TEST_1_batteryLevel", "TEST_2_power"}
        # Saving the device selection finishes immediately and reloads the integration.
        result = await hass.config_entries.options.async_init(config.entry_id)
        assert result['step_id'] == 'devices'
        result = await hass.config_entries.options.async_configure(result['flow_id'], {"selected_devices": ["1"]})
        assert result['type'] == 'create_entry'
        await hass.async_block_till_done()
        assert ids() == {"TEST_device_count", "TEST_1_value", "TEST_1_batteryLevel"}
        devices = dr.async_entries_for_config_entry(dr.async_get(hass), config.entry_id)
        assert len(devices) == 2
        # New readings of a selected physical device are included automatically.
        changed = snapshot()
        changed['devices'][1]['readings']['power'] = {'kind': 'power', 'value': 10, 'unit': None}
        config.runtime_data.async_set_updated_data(changed)
        await hass.async_block_till_done()
        assert ids() == {"TEST_device_count", "TEST_1_value", "TEST_1_batteryLevel", "TEST_1_power"}
        # Missing readings stay registered, and unselected devices stay excluded.
        config.runtime_data.async_set_updated_data(snapshot())
        await hass.async_block_till_done()
        assert 'TEST_1_power' in ids()
        assert 'TEST_2_power' not in ids()
        # Empty is an explicit selection; hub diagnostics remain.
        result = await hass.config_entries.options.async_init(config.entry_id)
        await hass.config_entries.options.async_configure(result['flow_id'], {"selected_devices": []})
        await hass.async_block_till_done()
        assert ids() == {'TEST_device_count'}
        assert len(dr.async_entries_for_config_entry(dr.async_get(hass), config.entry_id)) == 1
        assert await hass.config_entries.async_unload(config.entry_id)
