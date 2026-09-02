from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HISTORY_DAYS, CONF_SCAN_INTERVAL, DEFAULT_HISTORY_DAYS, DEFAULT_SCAN_INTERVAL
from .coordinator import NightscoutCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NightscoutCoordinator(
        hass,
        entry,
        scan_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        history_days=entry.options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN := "nightscout", {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data["nightscout"].pop(entry.entry_id, None)
    return ok
