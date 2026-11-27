"""Minimal diagnostics without credentials, identifiers or raw cloud responses."""
from homeassistant.components.diagnostics import async_redact_data

from .const import CLOUD_PASSWORD, CLOUD_USERNAME, HUB_PASSWORD, HUB_SERIAL, HUB_USERNAME


SENSITIVE_KEYS = {
    CLOUD_USERNAME, CLOUD_PASSWORD, HUB_USERNAME, HUB_PASSWORD, HUB_SERIAL,
    "username", "password", "user", "email", "account_id", "account_name",
    "id", "unique_id", "device_id", "serial", "serialNumber", "serial_number",
    "name", "hcName", "roomID", "room_id", "location", "latitude", "longitude",
    "ip", "mac", "tempKey", "temp", "token", "access_token", "refresh_token",
    "api_key", "authorization", "x-fibaro-auth", "cookie", "cookies", "set-cookie",
    "XSRF-TOKEN", "X-XSRF-TOKEN", "session", "url", "headers",
    "selected_devices", "selected_entities",
}


async def async_get_config_entry_diagnostics(hass, entry):
    """Export only status/counts; new configuration keys are redacted by default."""
    coordinator = getattr(entry, "runtime_data", None)
    data = coordinator.data if coordinator and coordinator.data else {}
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), SENSITIVE_KEYS | set(entry.data)),
            "options": async_redact_data(dict(entry.options), SENSITIVE_KEYS | set(entry.options)),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success if coordinator else None,
            "device_count": data.get("device_count"),
            "fibaro_object_count": data.get("fibaro_object_count"),
        },
    }
