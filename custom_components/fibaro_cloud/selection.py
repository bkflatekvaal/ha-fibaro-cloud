"""Select complete physical devices; retain legacy entity keys during migration."""
from .capabilities import has_entities

SELECTED_ENTITIES = "selected_entities"  # Legacy option, migrated on setup.
SELECTED_DEVICES = "selected_devices"
DEVICE_COUNT = "device_count"


def entity_key(device_id, prop):
    return f"{device_id}:{prop}"


def unique_id(serial, key):
    if key == DEVICE_COUNT:
        return f"{serial}_device_count"
    device_id, prop = key.split(":", 1)
    return f"{serial}_{device_id}_{prop}"


def group_id(snapshot, key):
    source = key.split(":", 1)[0]
    device = snapshot.get("devices", {}).get(int(source), {})
    return str(device.get("main_id", source))


def selected_device_ids(snapshot, options):
    if SELECTED_DEVICES in options:
        return sorted(set(options[SELECTED_DEVICES]))
    if SELECTED_ENTITIES in options:
        return sorted({group_id(snapshot, key) for key in options[SELECTED_ENTITIES]
                       if key != DEVICE_COUNT})
    return sorted(device_choices(snapshot))


def device_choices(snapshot, selected=()):
    choices = {}
    for source, device in snapshot.get("devices", {}).items():
        if not has_entities(device):
            continue
        main = str(device.get("main_id", source))
        choices[main] = f"{device.get('main_name', device['name'])} (#{main})"
    for main in selected:
        choices.setdefault(main, f"#{main} — Not currently reported")
    return choices


def async_migrate_selection(hass, entry, snapshot):
    """Expand the old allowlist to whole devices, including temporarily absent ones."""
    from homeassistant.helpers import entity_registry as er, device_registry as dr
    from .const import DOMAIN, HUB_SERIAL

    if SELECTED_DEVICES in entry.options:
        return
    selected = set(selected_device_ids(snapshot, entry.options))
    serial = entry.data[HUB_SERIAL]
    entities, devices = er.async_get(hass), dr.async_get(hass)
    for key in entry.options.get(SELECTED_ENTITIES, []):
        if key == DEVICE_COUNT or int(key.split(":", 1)[0]) in snapshot.get("devices", {}):
            continue
        entity_id = entities.async_get_entity_id("sensor", DOMAIN, unique_id(serial, key))
        entity = entities.async_get(entity_id) if entity_id else None
        device = devices.async_get(entity.device_id) if entity and entity.device_id else None
        if device:
            for domain, identifier in device.identifiers:
                if domain == DOMAIN and identifier.startswith(serial + "_"):
                    main = identifier[len(serial) + 1:]
                    if main.isdigit():
                        selected.discard(key.split(":", 1)[0])
                        selected.add(main)
    options = {key: value for key, value in entry.options.items() if key != SELECTED_ENTITIES}
    options[SELECTED_DEVICES] = sorted(selected)
    hass.config_entries.async_update_entry(entry, options=options)


async def async_remove_unselected(hass, entry):
    """Remove deselected devices' entities, keeping missing readings of selected devices."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from .const import DOMAIN, HUB_SERIAL

    if SELECTED_DEVICES not in entry.options:
        return
    selected = set(entry.options[SELECTED_DEVICES])
    serial = entry.data[HUB_SERIAL]
    entities, devices = er.async_get(hass), dr.async_get(hass)
    snapshot = entry.runtime_data.data
    removed_devices = set()
    for entity in er.async_entries_for_config_entry(entities, entry.entry_id):
        if entity.platform != DOMAIN or entity.unique_id == f"{serial}_device_count":
            continue
        source = entity.unique_id.removeprefix(serial + "_").split("_", 1)[0]
        if not source.isdigit():
            continue
        main = group_id(snapshot, source)
        device = devices.async_get(entity.device_id) if entity.device_id else None
        if device:
            for domain, identifier in device.identifiers:
                if domain == DOMAIN and identifier.startswith(serial + "_"):
                    candidate = identifier[len(serial) + 1:]
                    if candidate.isdigit() and int(source) not in snapshot.get("devices", {}):
                        main = candidate
        if main not in selected:
            if entity.device_id:
                removed_devices.add(entity.device_id)
            entities.async_remove(entity.entity_id)
    for device_id in removed_devices:
        if not er.async_entries_for_device(entities, device_id, include_disabled_entities=True):
            device = devices.async_get(device_id)
            if device and device.config_entry_id == entry.entry_id:
                devices.async_remove_device(device_id)
