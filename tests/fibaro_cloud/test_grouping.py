"""Physical device selection, channel identity and migration with real registries."""
import pytest

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers import area_registry as ar

from custom_components.fibaro_cloud.readings import project_devices
from custom_components.fibaro_cloud.selection import device_choices
from custom_components.fibaro_cloud.config_flow import FibaroCloudConfigFlow
from custom_components.fibaro_cloud.registry import async_group_devices
from custom_components.fibaro_cloud.sensor import FibaroReading
from test_ha import hass, entry, SNAPSHOT


def grouped_snapshot():
    return SNAPSHOT | {"devices": project_devices([
        {"id": 1, "type": "com.fibaro.zwavePrimaryController", "parentId": 0},
        {"id": 21, "name": "21", "type": "com.fibaro.zwaveDevice", "parentId": 1,
         "properties": {"batteryLevel": 90, "zwaveCompany": "Acme"}},
        {"id": 23, "parentId": 21, "name": "Kitchen", "type": "com.fibaro.temperatureSensor",
         "properties": {"value": 21, "unit": "C", "batteryLevel": 90}},
        {"id": 24, "parentId": 21, "name": "Kitchen", "type": "com.fibaro.humiditySensor",
         "properties": {"value": 50, "batteryLevel": 90}},
        {"id": 33, "parentId": 1, "name": "Other", "type": "com.fibaro.zwaveDevice"},
        {"id": 35, "parentId": 33, "name": "Air", "type": "com.fibaro.temperatureSensor",
         "properties": {"value": 7, "unit": "C"}},
        {"id": 36, "parentId": 33, "name": "Sea", "type": "com.fibaro.temperatureSensor",
         "properties": {"value": 4, "unit": "C"}},
    ])}


def test_projection_groups_physical_devices():
    snapshot = grouped_snapshot()
    devices = snapshot['devices']
    assert {devices[i]['main_id'] for i in (21, 23, 24)} == {21}
    assert devices[21]['main_name'] == devices[23]['main_name'] == '21'
    assert devices[23]['manufacturer'] == 'Acme'
    assert devices[35]['main_id'] == devices[36]['main_id'] == 33
    assert set(device_choices(snapshot)) == {'21', '33'}


def test_hidden_controller_plugin_and_missing_parent():
    raw = [
        {'id': 10, 'parentId': 1, 'properties': {}},
        {'id': 11, 'parentId': 10, 'properties': {'power': 1}},
        {'id': 20, 'parentId': 0, 'properties': {}},
        {'id': 21, 'parentId': 20, 'properties': {}},
        {'id': 22, 'parentId': 21, 'properties': {'power': 2}},
        {'id': 30, 'parentId': 999, 'properties': {'power': 3}},
    ]
    devices = project_devices(raw)
    assert devices[11]['main_id'] == 10
    assert devices[22]['main_id'] == 21
    assert devices[30]['main_id'] == 30


@pytest.mark.asyncio
async def test_flow_selects_main_device_and_preserves_child_keys(hass):
    flow = FibaroCloudConfigFlow()
    flow.hass = hass
    flow.handler = 'fibaro_cloud'
    flow._snapshot = grouped_snapshot()
    flow._selected = ['21', '99']
    flow._options = {}
    flow._data = {}
    flow._title = 'Test'
    result = await flow.async_step_devices()
    assert result['data_schema']({}) == {'selected_devices': ['21', '99']}
    result = await flow.async_step_devices({'selected_devices': ['21']})
    assert result['type'] == 'create_entry'
    assert result['options'] == {'selected_devices': ['21']}


@pytest.mark.asyncio
async def test_registry_migration_preserves_entity_ids_and_device_customizations(hass):
    from homeassistant.bootstrap import async_load_base_functionality
    from homeassistant import loader
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    devices, entities = dr.async_get(hass), er.async_get(hass)
    area = ar.async_get(hass).async_create('Kitchen')
    old = []
    for source in (23, 24):
        device = devices.async_get_or_create(config_entry_id=config.entry_id,
                    identifiers={('fibaro_cloud', f'TEST_{source}')}, name=f'Old {source}')
        old.append(device)
        entities.async_get_or_create('sensor', 'fibaro_cloud', f'TEST_{source}_value',
                    config_entry=config, device_id=device.id, suggested_object_id=f'custom_{source}')
    devices.async_update_device(old[0].id, area_id=area.id, name_by_user='My device')
    before = {e.entity_id: e.unique_id for e in entities.entities.values()}
    async_group_devices(hass, config, grouped_snapshot())
    main = devices.async_get_device_by_identifier(('fibaro_cloud', 'TEST_21'), config.entry_id)
    assert main.id == old[0].id
    assert main.area_id == area.id
    assert main.name_by_user == 'My device'
    assert {e.device_id for e in entities.entities.values()} == {main.id}
    assert {e.entity_id: e.unique_id for e in entities.entities.values()} == before
    assert devices.async_get(old[1].id) is None
    async_group_devices(hass, config, grouped_snapshot())
    assert devices.async_get_device_by_identifier(('fibaro_cloud', 'TEST_21'), config.entry_id).id == main.id
    assert len(dr.async_entries_for_config_entry(devices, config.entry_id)) == 2


@pytest.mark.asyncio
async def test_channels_keep_names_unique_ids_and_shared_device(hass):
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
    import logging
    config = entry()
    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name='test', config_entry=config)
    coordinator.hub_device_id = 'hub_uuid'
    coordinator.async_set_updated_data(grouped_snapshot())
    air, sea = (FibaroReading(coordinator, config, i, 'value') for i in (35, 36))
    assert air.unique_id == 'TEST_35_value'
    assert sea.unique_id == 'TEST_36_value'
    assert air.device_info == sea.device_info
    assert air.device_info['via_device_id'] == 'hub_uuid'
    assert air.name == 'Air Temperature'
    assert sea.name == 'Sea Temperature'
    await coordinator.async_shutdown()


def test_one_battery_per_main_device_with_stable_fallback():
    raw = [
        {'id': 10, 'parentId': 1, 'name': 'Fibaro main name', 'properties': {}},
        {'id': 11, 'parentId': 10, 'name': 'Temperature', 'properties': {'batteryLevel': 80}},
        {'id': 12, 'parentId': 10, 'name': 'Humidity', 'properties': {'batteryLevel': 80}},
    ]
    first = project_devices(raw)
    assert [(i, p) for i, d in first.items() for p in d['readings']] == [(10, 'batteryLevel')]
    assert first[10]['main_name'] == 'Fibaro main name'
    second = project_devices([raw[0], raw[2]])
    assert second[10]['readings']['batteryLevel']['value'] == 80
    raw[0]['properties']['batteryLevel'] = 255
    assert project_devices(raw)[10]['readings']['batteryLevel']['value'] == 80
    raw[0]['properties']['batteryLevel'] = 70
    assert project_devices(raw)[10]['readings']['batteryLevel']['value'] == 70


@pytest.mark.asyncio
async def test_battery_registry_migration_keeps_one_existing_entity_id(hass):
    from homeassistant import loader
    from homeassistant.bootstrap import async_load_base_functionality
    from custom_components.fibaro_cloud.registry import async_migrate_batteries
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    registry, devices = er.async_get(hass), dr.async_get(hass)
    old_entities = []
    old_devices = []
    for source in (23, 24):
        device = devices.async_get_or_create(config_entry_id=config.entry_id,
                    identifiers={('fibaro_cloud', f'TEST_{source}')})
        old_devices.append(device)
        old_entities.append(registry.async_get_or_create('sensor', 'fibaro_cloud', f'TEST_{source}_batteryLevel',
                    config_entry=config, device_id=device.id, suggested_object_id=f'battery_{source}'))
    registry.async_update_entity(old_entities[0].entity_id, name='Custom battery')
    async_migrate_batteries(hass, config, grouped_snapshot())
    assert registry.async_get(old_entities[1].entity_id) is None
    kept = registry.async_get(old_entities[0].entity_id)
    assert kept.unique_id == 'TEST_21_batteryLevel'
    assert kept.name == 'Custom battery'
    assert devices.async_get(old_devices[1].id) is None
    async_group_devices(hass, config, grouped_snapshot())
    main = devices.async_get_device_by_identifier(('fibaro_cloud', 'TEST_21'), config.entry_id)
    assert registry.async_get(kept.entity_id).device_id == main.id
    async_migrate_batteries(hass, config, grouped_snapshot())
    assert len(er.async_entries_for_config_entry(registry, config.entry_id)) == 1


@pytest.mark.asyncio
async def test_fibaro_device_names_refresh_without_overwriting_ha_override(hass):
    from homeassistant import loader
    from homeassistant.bootstrap import async_load_base_functionality
    from custom_components.fibaro_cloud.registry import async_sync_device_names
    loader.async_setup(hass)
    assert await async_load_base_functionality(hass)
    config = entry()
    hass.config_entries._entries[config.entry_id] = config
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(config_entry_id=config.entry_id,
                 identifiers={('fibaro_cloud', 'TEST_21')}, name='Old name')
    devices.async_update_device(device.id, name_by_user='My override')
    async_sync_device_names(hass, config, grouped_snapshot())
    assert devices.async_get(device.id).name == '21'
    assert devices.async_get(device.id).name_by_user == 'My override'
