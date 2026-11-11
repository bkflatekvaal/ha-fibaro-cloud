"""Device state projection, independent of Home Assistant.

Device type/property meanings were checked against HA 2026.11's Fibaro
integration. No upstream implementation is copied.
"""
from math import isfinite

from .capabilities import ACTIONS, STATE_PROPERTIES, platform_for

MAIN_TYPES = {
    "com.fibaro.temperatureSensor": "temperature",
    "com.fibaro.humiditySensor": "humidity",
    "com.fibaro.lightSensor": "illuminance",
    "com.fibaro.energyMeter": "energy",
    "com.fibaro.CO2Sensor": "carbon_dioxide",
    "com.fibaro.co2Sensor": "carbon_dioxide",
    "com.fibaro.voltageSensor": "voltage",
    "com.fibaro.currentSensor": "current",
    "com.fibaro.pressureSensor": "pressure",
    "com.fibaro.powerMeter": "power",

}


def number(value):
    """Reject booleans, empty values and non-finite device readings."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if isfinite(result) else None


def project_devices(devices):
    """Keep only entity metadata and recognized numeric readings in memory."""
    result = {}
    objects = {d["id"]: d for d in devices
               if isinstance(d, dict) and type(d.get("id")) is int and d["id"] > 0}
    controllers = {i for i, d in objects.items() if d.get("type") in {
        "com.fibaro.zwavePrimaryController", "com.fibaro.zigbeePrimaryController",
        "com.fibaro.niceEngine",
    }}
    if not any(d.get("type") == "com.fibaro.zwavePrimaryController" for d in objects.values()):
        controllers.add(1)  # Controllers can be hidden from non-admin users.
    children = {}
    for i, d in objects.items():
        children.setdefault(d.get("parentId", 0), []).append(i)
    masters = set()
    for i, d in objects.items():
        if i in controllers:
            continue
        if d.get("parentId", 0) in controllers or d.get("parentId", 0) == 0:
            direct = children.get(i, [])
            # Plugin containers may add a level above the physical devices.
            if any(children.get(child) for child in direct):
                masters.update(direct)
            else:
                masters.add(i)
    for device in devices:
        if not isinstance(device, dict):
            continue
        device_id = device.get("id")
        if type(device_id) is not int or device_id <= 0 or device.get("enabled") is False:
            continue
        props = device.get("properties")
        if not isinstance(props, dict):
            continue
        readings = {}
        platform = platform_for(device)
        kind = MAIN_TYPES.get(device.get("type"))
        if kind and "value" in props:
            unit = props.get("unit") if kind in {"pressure", "voltage", "current", "carbon_dioxide"} else None
            if kind == "temperature":
                unit = {"C": "°C", "F": "°F", "°C": "°C", "°F": "°F"}.get(props.get("unit"))
                # Never assume Celsius when the hub has not supplied a unit.
                if unit is None:
                    kind = None
            if kind:
                readings["value"] = {"kind": kind, "value": number(props["value"]), "unit": unit}
        if not kind and platform is None and "value" in props and device.get("type") == "com.fibaro.multilevelSensor" and props.get("unit"):
            unit = str(props["unit"])
            unit_kind = {"C": "temperature", "F": "temperature", "%": "humidity", "lux": "illuminance", "lx": "illuminance", "V": "voltage", "A": "current", "W": "power", "ppm": "carbon_dioxide", "hPa": "pressure"}.get(unit)
            if unit_kind:
                readings["value"] = {"kind": unit_kind, "value": number(props["value"]),
                                     "unit": {"C": "°C", "F": "°F", "lux": "lx"}.get(unit, unit)}
        for prop, kind in (("power", "power"), ("energy", "energy"), ("batteryLevel", "battery"),
                           ("voltage", "voltage"), ("current", "current"), ("frequency", "frequency")):
            if prop not in props:
                continue
            value = number(props[prop])
            if kind == "battery" and value is not None and not 0 <= value <= 100:
                value = None  # Fibaro's 255 sentinel is not a percentage.
            readings[prop] = {"kind": kind, "value": value, "unit": None}
        if readings or platform:
            result[device_id] = {
                "platform": platform,
                "rgbw": "rgbw" in str(device.get("type", "")).lower() or "setW" in (device.get("actions") or {}),
                "properties": {key: value for key, value in props.items() if key in STATE_PROPERTIES},
                "actions": {key: value for key, value in (device.get("actions") or {}).items() if key in ACTIONS},
                "parent_id": device.get("parentId", 0),
                "visible": device.get("visible", True),
                "main_id": device_id if device_id in masters else (
                    device.get("parentId") if device.get("parentId") in masters else device_id),
                "name": str(device.get("name") or f"Device {device_id}"),
                "type": str(device.get("type") or ""),
                "available": props.get("dead") not in (True, "true", "1", 1),
                "readings": readings,
            }
    for device in result.values():
        main = objects[device["main_id"]]
        props = main.get("properties") or {}
        device["main_name"] = str(main.get("name") or f"Device {device['main_id']}")
        device["manufacturer"] = props.get("zwaveCompany")
        device["main_type"] = str(main.get("type") or "")
    # Battery properties are repeated on endpoints; expose one stable main-device key.
    batteries = {}
    for source, device in list(result.items()):
        if "batteryLevel" in device["readings"]:
            reading = device["readings"].pop("batteryLevel")
            batteries.setdefault(device["main_id"], []).append((source, device, reading))
    for main_id, candidates in batteries.items():
        # Prefer a valid main reading, then a valid endpoint, in stable ID order.
        source, source_device, reading = min(candidates, key=lambda item: (
            item[2]["value"] is None, item[0] != main_id, item[0]))
        if main_id not in result:
            main = objects[main_id]
            props = main.get("properties") or {}
            result[main_id] = {
                **source_device, "platform": None, "properties": {}, "actions": {},
                "name": source_device["main_name"],
                "type": source_device["main_type"], "parent_id": main.get("parentId", 0),
                "available": props.get("dead") not in (True, "true", "1", 1),
                "readings": {},
            }
        result[main_id]["readings"]["batteryLevel"] = reading
    return result
