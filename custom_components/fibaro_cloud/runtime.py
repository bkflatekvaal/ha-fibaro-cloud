"""Synchronous auth lifecycle; callable from HA's executor or standalone tests."""
from threading import RLock
from time import monotonic

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
        self._auth_failed = False
        self._login_retry_at = 0.0
        self._token = basic_auth(config[HUB_USERNAME], config[HUB_PASSWORD])

    def snapshot(self):
        with self._lock:
            logged_in = self._ensure_session()
            try:
                return self._read_snapshot()
            except AuthenticationError:
                # Expiry can race the session check. Retry only this read,
                # with at most one credential submission per operation.
                if logged_in:
                    self._auth_failed = True
                    raise
            self._login()
            try:
                return self._read_snapshot()
            except AuthenticationError:
                self._auth_failed = True
                raise

    def _read_snapshot(self):
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
        if self._auth_failed:
            raise AuthenticationError("Cloud or hub credentials need verification.")
        if self._client.session:
            try:
                self._client.refresh_session()
            except AuthenticationError:
                self._client.session = {}
        if not self._client.session:
            self._login()
            return True
        return False

    def _login(self):
        if monotonic() < self._login_retry_at:
            raise ProbeError("Login temporarily unavailable; waiting before retry.")
        self._login_retry_at = monotonic() + 60
        try:
            self._client.login(self._config[CLOUD_USERNAME], self._config[CLOUD_PASSWORD])
        except AuthenticationError:
            # Queued executor jobs must not repeatedly submit rejected credentials.
            self._auth_failed = True
            self._client.session = {}
            raise
        except ProbeError:
            self._client.session = {}
            self._login_retry_at = monotonic() + 60
            raise
        self._login_retry_at = 0.0

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
            logged_in = self._ensure_session()
            previous = dict(self._client.session)
            try:
                return self._client.call_action(self._config[HUB_SERIAL], device_id, action,
                                                args, basic_token=self._token)
            except AuthenticationError:
                if logged_in:
                    self._auth_failed = True
                    raise
                # Diagnose expiry without ever replaying a potentially executed
                # command. A still-valid session suggests a hub permission error.
                renewed = self._ensure_session()
                if not renewed and self._client.session == previous:
                    self._auth_failed = True
                    raise
                raise ProbeError("Cloud session renewed; command was not retried. Check device state.") from None
