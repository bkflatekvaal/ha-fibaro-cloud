"""Synchronous auth lifecycle; callable from HA's executor or standalone tests."""
from threading import RLock

from .cloud import AuthenticationError, CloudClient, ProbeError, basic_auth
from .readings import project_devices
from .capabilities import ACTIONS, has_entities
from .const import CLOUD_PASSWORD, CLOUD_USERNAME, HUB_PASSWORD, HUB_SERIAL, HUB_USERNAME


class CloudConnection:
    def __init__(self, config, client=None):
        self._config = dict(config)
        self._client = client or CloudClient()
        self._lock = RLock()
        self._devices = {}
        self._token = basic_auth(config[HUB_USERNAME], config[HUB_PASSWORD])

    def snapshot(self):
        with self._lock:
            self._ensure_session()
            serial = self._config[HUB_SERIAL]
            info = self._client.read_api(serial, "/api/settings/info", basic_token=self._token)
            devices = self._client.read_api(serial, "/api/devices", basic_token=self._token)
            if not isinstance(info, dict) or not isinstance(devices, list):
                raise ProbeError("Unexpected hub response schema.")
            if info.get("serialNumber") != serial:
                raise ProbeError("Returned hub does not match the selected hub.")
            projected = project_devices(devices)
            self._devices = projected
            main_ids = {device["main_id"] for device in projected.values() if has_entities(device)}
            return {"info": info, "device_count": len(main_ids),
                    "fibaro_object_count": len(devices), "devices": projected}

    def _ensure_session(self):
        if self._client.session:
            try:
                self._client.refresh_session()
            except AuthenticationError:
                self._client.session = {}
        if not self._client.session:
            self._client.login(self._config[CLOUD_USERNAME], self._config[CLOUD_PASSWORD])

    def action(self, device_id, action, args):
        """Check advertised capabilities, authenticate, and send a single command."""
        with self._lock:
            if not isinstance(args, list):
                raise ProbeError("Invalid action arguments.")
            device = self._devices.get(device_id, {})
            if action not in ACTIONS or action not in device.get("actions", {}):
                raise ProbeError("Device does not support this action.")
            expected = device["actions"][action]
            if type(expected) is int and len(args) != expected:
                raise ProbeError("Invalid number of action arguments.")
            self._ensure_session()
            return self._client.call_action(self._config[HUB_SERIAL], device_id, action,
                                            args, basic_token=self._token)
