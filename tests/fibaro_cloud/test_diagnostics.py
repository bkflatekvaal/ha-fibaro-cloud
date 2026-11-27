"""Diagnostics must remain safe when configuration gains new private fields."""
import json
from types import SimpleNamespace

import pytest

from custom_components.fibaro_cloud.diagnostics import SENSITIVE_KEYS, async_get_config_entry_diagnostics


@pytest.mark.asyncio
async def test_diagnostics_redacts_all_configuration_and_omits_payloads():
    entry = SimpleNamespace(
        data={key: "PRIVATE_SENTINEL" for key in SENSITIVE_KEYS | {"future_field", "ACCOUNT_ID"}},
        options={"selected_devices": ["PRIVATE_SENTINEL"], "future_option": {"nested": "PRIVATE_SENTINEL"}},
        runtime_data=SimpleNamespace(last_update_success=True, data={
            "device_count": 2, "fibaro_object_count": 3,
            "info": {"serialNumber": "PRIVATE_SENTINEL"},
            "devices": {"PRIVATE_SENTINEL": {"name": "PRIVATE_SENTINEL"}},
        }),
    )
    result = await async_get_config_entry_diagnostics(None, entry)
    assert "PRIVATE_SENTINEL" not in json.dumps(result)
    assert result["coordinator"] == {"last_update_success": True, "device_count": 2, "fibaro_object_count": 3}
    assert entry.data["cloud_password"] == "PRIVATE_SENTINEL"


@pytest.mark.asyncio
async def test_diagnostics_before_setup():
    result = await async_get_config_entry_diagnostics(None, SimpleNamespace(data={}, options={}))
    assert result["coordinator"]["last_update_success"] is None


def test_sensitive_keys_cover_authentication_and_account_identifiers():
    assert {"cloud_username", "cloud_password", "hub_username", "hub_password",
            "hub_serial", "account_id", "user", "tempKey", "refresh_token",
            "authorization", "cookie", "XSRF-TOKEN"} <= SENSITIVE_KEYS
