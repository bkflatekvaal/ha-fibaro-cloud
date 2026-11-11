"""Check a temporary HA configuration using the cross-platform helper API.

This does not start a production instance or configure a cloud connection.
The generated temporary directory is retained for inspection.
"""
import asyncio
from pathlib import Path
import shutil
import tempfile

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.check_config import async_check_ha_config_file


async def check():
    """Use the same validation helper as HA's check_config command."""
    config = Path(tempfile.mkdtemp(prefix="fibaro-cloud-config-check-"))
    (config / "configuration.yaml").write_text("{}\n", encoding="utf-8")
    source = Path(__file__).resolve().parents[1] / "custom_components" / "fibaro_cloud"
    shutil.copytree(source, config / "custom_components" / "fibaro_cloud",
                    ignore=shutil.ignore_patterns("__pycache__"))
    hass = HomeAssistant(str(config))
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    try:
        await hass.config_entries.async_initialize()
        dr.async_setup(hass)
        await ar.async_load(hass)
        await dr.async_load(hass)
        await er.async_load(hass)
        await ir.async_load(hass, read_only=True)
        result = await async_check_ha_config_file(hass)
        print("Isolated HA configuration errors:", result.errors)
        return bool(result.errors)
    finally:
        await hass.async_stop(force=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(check()))
