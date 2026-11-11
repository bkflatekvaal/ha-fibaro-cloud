"""Numeric device readings and hub diagnostics."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HUB_SERIAL
from .selection import selected_device_ids


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    selected = set(selected_device_ids(coordinator.data, entry.options))
    async_add_entities([FibaroDeviceCount(coordinator, entry)])
    known = set()

    @callback
    def discover():
        entities = []
        for device_id, device in coordinator.data.get("devices", {}).items():
            for prop in device["readings"]:
                if str(device.get("main_id", device_id)) not in selected:
                    continue
                key = (device_id, prop)
                if key not in known:
                    known.add(key)
                    entities.append(FibaroReading(coordinator, entry, device_id, prop))
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class FibaroDeviceCount(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "device_count"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "devices"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        serial = entry.data[HUB_SERIAL]
        info = coordinator.data["info"]
        self._attr_unique_id = f"{serial}_device_count"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)}, name=entry.title,
            manufacturer="Fibaro / Nice", model=info.get("platform"),
            sw_version=info.get("softVersion"),
        )

    @property
    def native_value(self):
        return self.coordinator.data["device_count"]


    @property
    def extra_state_attributes(self):
        return {
            "selected_devices": len(selected_device_ids(self.coordinator.data, self._entry.options)),
            "fibaro_api_objects": self.coordinator.data.get("fibaro_object_count"),
        }


# Numeric measurements use separate entities from actuator and alarm states.
READING_TYPES = {
    "temperature": (SensorDeviceClass.TEMPERATURE, None, SensorStateClass.MEASUREMENT),
    "humidity": (SensorDeviceClass.HUMIDITY, "%", SensorStateClass.MEASUREMENT),
    "illuminance": (SensorDeviceClass.ILLUMINANCE, "lx", SensorStateClass.MEASUREMENT),
    "power": (SensorDeviceClass.POWER, "W", SensorStateClass.MEASUREMENT),
    "energy": (SensorDeviceClass.ENERGY, "kWh", SensorStateClass.TOTAL_INCREASING),
    "battery": (SensorDeviceClass.BATTERY, "%", SensorStateClass.MEASUREMENT),
    "voltage": (SensorDeviceClass.VOLTAGE, "V", SensorStateClass.MEASUREMENT),
    "current": (SensorDeviceClass.CURRENT, "A", SensorStateClass.MEASUREMENT),
    "frequency": (SensorDeviceClass.FREQUENCY, "Hz", SensorStateClass.MEASUREMENT),
    "pressure": (SensorDeviceClass.PRESSURE, "hPa", SensorStateClass.MEASUREMENT),
    "carbon_dioxide": (SensorDeviceClass.CO2, "ppm", SensorStateClass.MEASUREMENT),
}


class FibaroReading(CoordinatorEntity, SensorEntity):
    """A numeric property from the coordinator's sanitized device snapshot."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, device_id, prop):
        super().__init__(coordinator)
        self._device_id = device_id
        self._prop = prop
        device = coordinator.data["devices"][device_id]
        reading = device["readings"][prop]
        self._kind = reading["kind"]
        device_class, unit, state_class = READING_TYPES[self._kind]
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_translation_key = self._kind
        serial = entry.data[HUB_SERIAL]
        self._attr_unique_id = f"{serial}_{device_id}_{prop}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{serial}_{device.get('main_id', device_id)}")},
            name=device.get("main_name", device["name"]),
            model=device.get("main_type", device["type"]),
            manufacturer=device.get("manufacturer"),
            via_device_id=getattr(coordinator, "hub_device_id", None),
        )
        self._attr_entity_registry_visible_default = device.get("visible", True)
        # Multiple endpoints of one device must remain distinguishable.
        self._attr_name = f"{device['name']} {self._kind.capitalize()}"
        self._attr_has_entity_name = False
        if self._kind == "battery":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_visible_default = True
            self._attr_name = "Battery"
            self._attr_has_entity_name = True

    @property
    def extra_state_attributes(self):
        return {"fibaro_id": self._device_id}

    @property
    def _device(self):
        return self.coordinator.data.get("devices", {}).get(self._device_id, {})

    @property
    def _reading(self):
        return self._device.get("readings", {}).get(self._prop, {})

    @property
    def available(self):
        return (super().available and self._device.get("available", False)
                and self._reading.get("kind") == self._kind)

    @property
    def native_value(self):
        return self._reading.get("value")

    @property
    def native_unit_of_measurement(self):
        return self._reading.get("unit") or self._attr_native_unit_of_measurement
