"""Cloud login, hub selection, local credentials and reauthentication."""
import probatio

from homeassistant.config_entries import ConfigFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .cloud import AuthenticationError, CloudClient, ProbeError
from .const import CLOUD_PASSWORD, CLOUD_USERNAME, DOMAIN, HUB_PASSWORD, HUB_SERIAL, HUB_USERNAME
from .runtime import CloudConnection
from .selection import SELECTED_DEVICES, SELECTED_ENTITIES, device_choices, selected_device_ids
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode


def read_snapshot(config, client=None):
    """Construct TLS/network clients inside the executor as well as reading data."""
    return CloudConnection(config, client).snapshot()


def credentials_schema():
    return probatio.Schema({
        probatio.Required(CLOUD_USERNAME): str,
        probatio.Required(probatio.Secret(CLOUD_PASSWORD)): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        probatio.Required(HUB_USERNAME): str,
        probatio.Required(probatio.Secret(HUB_PASSWORD)): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    })


class SelectionSteps:
    """Select whole physical devices in a single step."""

    async def async_step_devices(self, user_input=None):
        choices = device_choices(self._snapshot, self._selected)
        if user_input is not None:
            selected = user_input.get(SELECTED_DEVICES, [])
            if not set(selected) <= choices.keys():
                return self.async_abort(reason="invalid_selection")
            options = {key: value for key, value in self._options.items() if key != SELECTED_ENTITIES}
            options[SELECTED_DEVICES] = sorted(set(selected))
            if isinstance(self, OptionsFlowWithReload):
                return self.async_create_entry(title="", data=options)
            return self.async_create_entry(title=self._title, data=self._data, options=options)
        return self.async_show_form(step_id="devices", data_schema=probatio.Schema({
            probatio.Required(SELECTED_DEVICES, default=self._selected): SelectSelector(SelectSelectorConfig(
                options=[{"value": key, "label": label} for key, label in choices.items()],
                multiple=True, mode=SelectSelectorMode.LIST,
            )),
        }))


class FibaroCloudConfigFlow(SelectionSteps, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return FibaroCloudOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._client = await self.hass.async_add_executor_job(CloudClient)
            try:
                await self.hass.async_add_executor_job(
                    self._client.login, user_input[CLOUD_USERNAME], user_input[CLOUD_PASSWORD]
                )
                self._hubs = await self.hass.async_add_executor_job(self._client.hubs)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ProbeError:
                errors["base"] = "cannot_connect"
            else:
                if not self._hubs:
                    return self.async_abort(reason="no_hubs")
                self._cloud_data = dict(user_input)
                return await self.async_step_hub()
        return self.async_show_form(step_id="user", errors=errors, data_schema=probatio.Schema({
            probatio.Required(CLOUD_USERNAME): str,
            probatio.Required(probatio.Secret(CLOUD_PASSWORD)): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }))

    async def async_step_hub(self, user_input=None):
        errors = {}
        choices = {h["serial"]: f"{h.get('name') or h.get('hcName') or 'Hub'} ({h['serial']})" for h in self._hubs}
        if user_input is not None:
            if user_input[HUB_SERIAL] not in choices:
                return self.async_abort(reason="no_hubs")
            data = self._cloud_data | user_input
            try:
                result = await self.hass.async_add_executor_job(read_snapshot, data, self._client)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ProbeError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[HUB_SERIAL])
                self._abort_if_unique_id_configured()
                self._snapshot = result
                self._data = data
                self._title = result["info"].get("hcName") or choices[data[HUB_SERIAL]]
                self._selected = []
                self._options = {}
                return await self.async_step_devices()
        return self.async_show_form(step_id="hub", errors=errors, data_schema=probatio.Schema({
            probatio.Required(HUB_SERIAL): probatio.In(choices),
            probatio.Required(HUB_USERNAME): str,
            probatio.Required(probatio.Secret(HUB_PASSWORD)): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
        }))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(read_snapshot, entry.data | user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ProbeError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", errors=errors, data_schema=credentials_schema())


class FibaroCloudOptionsFlow(SelectionSteps, OptionsFlowWithReload):
    """Edit the allowlist and reload the entry after saving."""

    async def async_step_init(self, user_input=None):
        try:
            self._snapshot = await self.hass.async_add_executor_job(
                read_snapshot, self.config_entry.data
            )
        except AuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except ProbeError:
            return self.async_abort(reason="cannot_connect")
        self._options = dict(self.config_entry.options)
        self._selected = selected_device_ids(self._snapshot, self._options)
        return await self.async_step_devices()
