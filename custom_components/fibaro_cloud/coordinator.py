"""Cloud polling and serialized device actions with post-command confirmation."""
from datetime import timedelta
import logging

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloud import AuthenticationError, ProbeError
from .selection import selected_device_ids


class FibaroCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, connection):
        super().__init__(hass, logging.getLogger(__name__), name='Fibaro Cloud',
                         update_interval=timedelta(seconds=60), config_entry=entry)
        self.connection = connection
        self.entry = entry
        self._cancel_confirmation = None

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self.connection.snapshot)
        except AuthenticationError:
            raise ConfigEntryAuthFailed('Cloud or hub credentials need verification') from None
        except ProbeError as exc:
            raise UpdateFailed(str(exc)) from None

    async def async_action(self, device_id, action, args):
        device = self.data.get('devices', {}).get(device_id, {})
        main = str(device.get('main_id', device_id))
        if main not in selected_device_ids(self.data, self.entry.options):
            raise HomeAssistantError('This Fibaro device is not selected')
        if not device.get('available', False) or not self.last_update_success:
            raise HomeAssistantError('This Fibaro device is unavailable')
        try:
            await self.hass.async_add_executor_job(self.connection.action, device_id, action, args)
        except AuthenticationError:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError('Fibaro authentication failed; reauthentication is required') from None
        except ProbeError as exc:
            # A timed-out action may already have happened. Never replay it.
            raise HomeAssistantError(str(exc)) from None
        # Display only hub-confirmed state, and poll again after propagation delay.
        if self._cancel_confirmation:
            self._cancel_confirmation()
        self._cancel_confirmation = async_call_later(self.hass, 2, self._confirm)
        await self.async_refresh()

    async def _confirm(self, _now):
        self._cancel_confirmation = None
        await self.async_refresh()

    async def async_shutdown(self):
        if self._cancel_confirmation:
            self._cancel_confirmation()
            self._cancel_confirmation = None
        await super().async_shutdown()
