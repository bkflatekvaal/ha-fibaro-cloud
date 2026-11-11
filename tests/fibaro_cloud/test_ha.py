"""Compatibility tests using real Home Assistant 2026.11 classes."""
from types import MappingProxyType
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from custom_components.fibaro_cloud import async_setup_entry, async_unload_entry
from custom_components.fibaro_cloud.cloud import AuthenticationError, ProbeError
from custom_components.fibaro_cloud.config_flow import FibaroCloudConfigFlow, credentials_schema
from custom_components.fibaro_cloud.sensor import async_setup_entry as setup_sensors
from custom_components.fibaro_cloud.readings import project_devices

CONFIG = dict(cloud_username="cloud", cloud_password="dummy", hub_username="local", hub_password="dummy", hub_serial="TEST")
SNAPSHOT = {"info": {"serialNumber": "TEST", "platform": "HC3L"}, "device_count": 1, "devices": {}}


def entry():
    return ConfigEntry(domain="fibaro_cloud", title="Test", data=CONFIG, options={}, source="user", unique_id="TEST", version=1, minor_version=1, discovery_keys=MappingProxyType({}), subentries_data=[], state=ConfigEntryState.SETUP_IN_PROGRESS)


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    yield instance
    await instance.async_stop(force=True)


@pytest.mark.asyncio
async def test_user_and_hub_flow(hass):
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = "fibaro_cloud"
    flow.context = {"source": "user"}
    with patch("custom_components.fibaro_cloud.config_flow.CloudClient") as client, patch("custom_components.fibaro_cloud.config_flow.CloudConnection") as connection:
        client.return_value.hubs.return_value = [{"serial": "TEST", "name": "Test"}]
        connection.return_value.snapshot.return_value = SNAPSHOT
        result = await flow.async_step_user({k: CONFIG[k] for k in ("cloud_username", "cloud_password")})
        assert result["step_id"] == "hub"
        result = await flow.async_step_hub({k: CONFIG[k] for k in ("hub_serial", "hub_username", "hub_password")})
        assert result["step_id"] == "devices"
        result = await flow.async_step_devices({"selected_devices": []})
        assert result["type"] == "create_entry"
        assert result["data"] == CONFIG
        assert result["options"] == {"selected_devices": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("error,expected", [(AuthenticationError("Rejected"), "invalid_auth"), (ProbeError("Network"), "cannot_connect")])
async def test_flow_errors(hass, error, expected):
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = "fibaro_cloud"
    with patch("custom_components.fibaro_cloud.config_flow.CloudClient") as client:
        client.return_value.login.side_effect = error
        result = await flow.async_step_user(CONFIG)
    assert result["errors"]["base"] == expected


def test_password_masking():
    import probatio
    schema = credentials_schema()
    secrets = {key.schema.schema for key in schema.schema if isinstance(key.schema, probatio.Secret)}
    assert secrets == {"cloud_password", "hub_password"}
    for key, value in schema.schema.items():
        if isinstance(key.schema, probatio.Secret):
            assert value.config["type"] == "password"


@pytest.mark.asyncio
async def test_setup_unload(hass):
    from homeassistant.bootstrap import async_load_base_functionality
    from homeassistant import loader
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    with patch("custom_components.fibaro_cloud.runtime.CloudConnection") as connection, patch.object(ConfigEntries, "async_forward_entry_setups", new_callable=AsyncMock) as forward, patch.object(ConfigEntries, "async_unload_platforms", new_callable=AsyncMock, return_value=True) as unload:
        connection.return_value.snapshot.return_value = SNAPSHOT
        assert await async_setup_entry(hass, config)
        assert config.runtime_data.data == SNAPSHOT
        forward.assert_awaited_once()
        assert await async_unload_entry(hass, config)
        unload.assert_awaited_once()
        await config.runtime_data.async_shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("error,expected", [(AuthenticationError("Rejected"), ConfigEntryAuthFailed), (ProbeError("Network"), ConfigEntryNotReady)])
async def test_setup_errors(hass, error, expected):
    with patch("custom_components.fibaro_cloud.runtime.CloudConnection") as connection:
        connection.return_value.snapshot.side_effect = error
        with pytest.raises(expected):
            await async_setup_entry(hass, entry())


@pytest.mark.asyncio
async def test_sensors_discover_update_and_remove(hass):
    import logging
    config = entry()
    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="test", config_entry=config)
    config.runtime_data = coordinator
    device = dict(id=1, name="Test", type="com.fibaro.temperatureSensor", properties={"value": "20.5", "unit": "C"})
    coordinator.async_set_updated_data(SNAPSHOT | {"devices": project_devices([device])})
    added = []
    await setup_sensors(hass, config, added.extend)
    assert len(added) == 2
    sensor = added[1]
    assert sensor.native_value == 20.5
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor.unique_id == "TEST_1_value"
    assert sensor.available
    device["properties"].update(value="72", unit="F", dead=True)
    coordinator.async_set_updated_data(SNAPSHOT | {"devices": project_devices([device])})
    assert sensor.native_value == 72
    assert sensor.native_unit_of_measurement == "°F"
    assert not sensor.available
    coordinator.async_set_updated_data(SNAPSHOT)
    assert not sensor.available
    assert sensor.native_value is None
    device["id"] = 2
    coordinator.async_set_updated_data(SNAPSHOT | {"devices": project_devices([device])})
    assert len(added) == 2  # A new, unselected physical device is not imported.
    await config._async_process_on_unload(hass)
    assert not coordinator._listeners
    await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_duplicate_hub(hass):
    from homeassistant.data_entry_flow import AbortFlow
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = "fibaro_cloud"
    flow.context = {"source": "user"}
    flow._hubs = [{"serial": "TEST"}]
    flow._cloud_data = {k: CONFIG[k] for k in ("cloud_username", "cloud_password")}
    flow._client = Mock()
    with patch("custom_components.fibaro_cloud.config_flow.CloudConnection") as connection:
        connection.return_value.snapshot.return_value = SNAPSHOT
        with pytest.raises(AbortFlow) as error:
            await flow.async_step_hub({k: CONFIG[k] for k in ("hub_serial", "hub_username", "hub_password")})
    assert error.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_reauth(hass):
    config = entry()
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = "fibaro_cloud"
    flow.context = {"source": "reauth"}
    with patch.object(flow, "_get_reauth_entry", return_value=config), patch("custom_components.fibaro_cloud.config_flow.CloudConnection") as connection, patch.object(flow, "async_update_reload_and_abort", return_value={"type": "abort", "reason": "reauth_successful"}) as update:
        connection.return_value.snapshot.side_effect = AuthenticationError("Rejected")
        result = await flow.async_step_reauth_confirm(CONFIG)
        assert result["errors"] == {"base": "invalid_auth"}
        update.assert_not_called()
        connection.return_value.snapshot.side_effect = None
        connection.return_value.snapshot.return_value = SNAPSHOT
        result = await flow.async_step_reauth_confirm(CONFIG)
        assert result["reason"] == "reauth_successful"
        update.assert_called_once_with(config, data_updates=CONFIG)


@pytest.mark.asyncio
async def test_manifest_and_platform_imports(hass):
    import homeassistant.loader as loader
    loader.async_setup(hass)
    integration = await loader.async_get_integration(hass, "fibaro_cloud")
    assert integration.domain == "fibaro_cloud"
    assert integration.version == "0.1.0"
    assert integration.config_flow
    assert not integration.requirements
    assert await integration.async_get_platform("sensor")
    assert await integration.async_get_platform("config_flow")


@pytest.mark.asyncio
async def test_full_platform_setup_unload_reload(hass):
    """Exercise real entity registration and platform teardown with fake cloud I/O."""
    from homeassistant import loader
    from homeassistant.setup import async_setup_component
    loader.async_setup(hass)
    from homeassistant.bootstrap import async_load_base_functionality
    from homeassistant import loader
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    config._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    hass.config_entries._entries[config.entry_id] = config
    with patch("custom_components.fibaro_cloud.runtime.CloudConnection") as connection:
        device = dict(id=1, name="Test", type="com.fibaro.temperatureSensor", properties={"value": "20.5", "unit": "C"})
        connection.return_value.snapshot.return_value = SNAPSHOT | {"devices": project_devices([device])}
        assert await async_setup_component(hass, "fibaro_cloud", {})
        await hass.async_block_till_done()
        assert config.state is ConfigEntryState.LOADED
        states = hass.states.async_all("sensor")
        assert {s.state for s in states} == {"1", "20.5"}
        coordinator = config.runtime_data
        assert await hass.config_entries.async_unload(config.entry_id)
        await hass.async_block_till_done()
        assert not coordinator._listeners
        assert await hass.config_entries.async_setup(config.entry_id)
        await hass.async_block_till_done()
        assert {s.state for s in hass.states.async_all("sensor")} == {"1", "20.5"}
        assert await hass.config_entries.async_unload(config.entry_id)
