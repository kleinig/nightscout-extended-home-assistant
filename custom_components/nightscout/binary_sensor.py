from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

SENSORS = [
    ("closed_loop","Closed Loop","mdi:robot"),
    ("pump_connected","Pump Connected","mdi:pump"),
    ("aaps_charging","AAPS Phone Charging","mdi:cellphone-charging"),
    ("glucose_stale","Glucose Data Stale","mdi:clock-alert"),
    ("low_reservoir","Low Pump Reservoir","mdi:water-alert"),
    ("critical_reservoir","Critical Pump Reservoir","mdi:water-alert"),
    ("low_pump_battery","Low Pump Battery","mdi:battery-alert"),
    ("critical_pump_battery","Critical Pump Battery","mdi:battery-alert"),
    ("glucose_low","Glucose Low","mdi:arrow-down-bold"),
    ("glucose_high","Glucose High","mdi:arrow-up-bold"),
    ("glucose_rising","Glucose Rising","mdi:trending-up"),
    ("glucose_falling","Glucose Falling","mdi:trending-down"),
    ("dynamic_isf","Dynamic ISF Running","mdi:scale-balance"),
    ("smb_enabled","SMB Enabled","mdi:needle"),
    ("delivery_received","AAPS Delivery Received","mdi:check-circle"),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data["nightscout"][entry.entry_id]
    async_add_entities([NightscoutBinary(c, *x) for x in SENSORS])


class NightscoutBinary(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_icon = icon

    @property
    def is_on(self):
        d = self.coordinator.data
        if self.key == "closed_loop": return str(d.get("pump_status","")).lower() == "closed loop"
        if self.key == "pump_connected": return d.get("pump_status") is not None
        if self.key == "aaps_charging": return d.get("uploader_charging", False)
        if self.key == "glucose_stale": return d.get("bg_age") is None or d["bg_age"] > 900
        if self.key == "low_reservoir": return d.get("reservoir") is not None and d["reservoir"] <= d.get("res_warning",80)
        if self.key == "critical_reservoir": return d.get("reservoir") is not None and d["reservoir"] <= d.get("res_critical",10)
        if self.key == "low_pump_battery": return d.get("pump_battery") is not None and d["pump_battery"] <= d.get("pump_bat_warning",25)
        if self.key == "critical_pump_battery": return d.get("pump_battery") is not None and d["pump_battery"] <= d.get("pump_bat_critical",5)
        bg = d.get("bg_mmol")
        if self.key == "glucose_low": return bg is not None and bg < d.get("low_mark",4)
        if self.key == "glucose_high": return bg is not None and bg > d.get("high_mark",10)
        direction = str(d.get("direction","")).lower()
        if self.key == "glucose_rising": return any(x in direction for x in ("up","rising"))
        if self.key == "glucose_falling": return any(x in direction for x in ("down","falling"))
        if self.key == "dynamic_isf": return bool(d.get("dynamic_isf"))
        if self.key == "smb_enabled": return bool(d.get("smb_always")) or d.get("algorithm") == "SMB"
        if self.key == "delivery_received": return bool(d.get("delivery_received"))
        return False
