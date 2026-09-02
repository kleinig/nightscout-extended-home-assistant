from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import NightscoutExtendedCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NightscoutExtendedCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start_socketio()
    hass.data.setdefault("nightscout_extended", {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data.get("nightscout_extended", {}).get(entry.entry_id)
    if coordinator:
        await coordinator.async_stop_socketio()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get("nightscout_extended", {}).pop(entry.entry_id, None)
    return unload_ok
