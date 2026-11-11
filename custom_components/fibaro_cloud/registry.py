"""Register the hub and migrate child devices without renaming entities."""
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, HUB_SERIAL
from .selection import entity_key, unique_id


@callback
def async_group_devices(hass, entry, snapshot):
    """Reuse a source device where possible, preserving its user customizations."""
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    serial = entry.data[HUB_SERIAL]
    info = snapshot["info"]
    hub = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, serial)},
        name=entry.title, serial_number=serial, manufacturer="Fibaro / Nice",
        model=info.get("platform"), sw_version=info.get("softVersion"),
    )
    registered = {e.unique_id: e for e in er.async_entries_for_config_entry(entities, entry.entry_id)
                  if e.platform == DOMAIN}
    groups = {}
    for source, device in snapshot.get("devices", {}).items():
        main = device.get("main_id", source)
        group = groups.setdefault(main, [])
        keys = [entity_key(source, prop) for prop in device["readings"]]
        if device.get("platform"):
            keys.append(entity_key(source, device["platform"]))
        for key in keys:
            entity = registered.get(unique_id(serial, key))
            if entity:
                group.append(entity)
    for main, members in groups.items():
        if not members:
            continue
        identifier = (DOMAIN, f"{serial}_{main}")
        target = devices.async_get_device_by_identifier(identifier, entry.entry_id)
        old_ids = {e.device_id for e in members if e.device_id}
        if target is None:
            # Prefer the oldest existing device, retaining its UUID, area and labels.
            candidates = [devices.async_get(i) for i in old_ids]
            candidates = [d for d in candidates if d is not None
                          and d.config_entry_id == entry.entry_id
                          and all(e.unique_id in {m.unique_id for m in members}
                                  for e in er.async_entries_for_device(entities, d.id, include_disabled_entities=True))]
            if candidates:
                source = min(candidates, key=lambda d: (d.created_at, d.id))
                target = devices.async_update_device(source.id, new_identifiers={identifier})
            else:
                target = devices.async_get_or_create(
                    config_entry_id=entry.entry_id, identifiers={identifier})
        for entity in members:
            if entity.device_id != target.id:
                entities.async_update_entity(entity.entity_id, device_id=target.id)
        for old in old_ids - {target.id}:
            if not er.async_entries_for_device(entities, old, include_disabled_entities=True):
                old_device = devices.async_get(old)
                if old_device and old_device.config_entry_id == entry.entry_id:
                    devices.async_remove_device(old)
    return hub.id


@callback
def async_migrate_batteries(hass, entry, snapshot):
    """Keep one existing entity ID when repeated endpoint batteries are combined."""
    entities = er.async_get(hass)
    serial = entry.data[HUB_SERIAL]
    prefix = serial + "_"
    groups = {}
    for entity in er.async_entries_for_config_entry(entities, entry.entry_id):
        if entity.platform != DOMAIN or not entity.unique_id.startswith(prefix):
            continue
        suffix = entity.unique_id[len(prefix):]
        source, _, prop = suffix.partition("_")
        if prop != "batteryLevel" or not source.isdigit():
            continue
        device = snapshot.get("devices", {}).get(int(source))
        if device is None:
            continue
        main = device.get("main_id", int(source))
        if "batteryLevel" in snapshot["devices"].get(main, {}).get("readings", {}):
            groups.setdefault(main, []).append(entity)
    removed_devices = set()
    for main, members in groups.items():
        canonical = f"{serial}_{main}_batteryLevel"
        keep = min(members, key=lambda e: (e.unique_id != canonical, e.created_at, e.entity_id))
        for entity in members:
            if entity.entity_id != keep.entity_id:
                if entity.device_id:
                    removed_devices.add(entity.device_id)
                entities.async_remove(entity.entity_id)
        if keep.unique_id != canonical:
            entities.async_update_entity(keep.entity_id, new_unique_id=canonical)
    devices = dr.async_get(hass)
    for device_id in removed_devices:
        if not er.async_entries_for_device(entities, device_id, include_disabled_entities=True):
            device = devices.async_get(device_id)
            if device and device.config_entry_id == entry.entry_id:
                devices.async_remove_device(device_id)


@callback
def async_sync_device_names(hass, entry, snapshot):
    """Follow Fibaro main-device names while retaining HA user overrides."""
    devices = dr.async_get(hass)
    serial = entry.data[HUB_SERIAL]
    names = {d.get("main_id", source): d.get("main_name", d["name"])
             for source, d in snapshot.get("devices", {}).items()}
    for main, name in names.items():
        device = devices.async_get_device_by_identifier((DOMAIN, f"{serial}_{main}"), entry.entry_id)
        if device and device.name != name:
            devices.async_update_device(device.id, name=name)
