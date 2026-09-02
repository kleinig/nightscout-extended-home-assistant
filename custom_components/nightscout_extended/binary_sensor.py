"""Binary sensors for Nightscout Extended."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

BINARY = [
    ("phone_charging", "AAPS Phone Charging", EntityCategory.DIAGNOSTIC),
    ("dynamic_isf", "Dynamic ISF Active", None),
    ("active_smb", "SMB Enabled", None),
    ("delivery_received", "AAPS Delivery Received", EntityCategory.DIAGNOSTIC),
    ("pump_connected", "Pump Connected", None),
    ("glucose_stale", "Glucose Data Stale", EntityCategory.DIAGNOSTIC),
    ("glucose_low", "Glucose Low", None),
    ("glucose_high", "Glucose High", None),
    ("glucose_rising", "Glucose Rising", None),
    ("glucose_falling", "Glucose Falling", None),
    ("glucose_rapid_rising", "Glucose Rapidly Rising", None),
    ("glucose_rapid_falling", "Glucose Rapidly Falling", None),
    ("closed_loop", "Closed Loop", None),
    ("reservoir_warning_state", "Reservoir Warning", EntityCategory.DIAGNOSTIC),
    ("reservoir_critical_state", "Reservoir Critical", EntityCategory.DIAGNOSTIC),
    ("pump_battery_warning_state", "Pump Battery Warning", EntityCategory.DIAGNOSTIC),
    ("pump_battery_critical_state", "Pump Battery Critical", EntityCategory.DIAGNOSTIC),
]

class NightscoutExtendedBinary(CoordinatorEntity, BinarySensorEntity):
    """Binary status sensor."""

    def __init__(self, coordinator, key, name, category):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_entity_category = category
        self._attr_has_entity_name = False

    @property
    def is_on(self):
        d = self.coordinator.data
        if self.key == "glucose_stale":
            return (d.get("glucose_age") or 0) > 600
        if self.key == "glucose_low":
            return d.get("bg") is not None and d["bg"] < (d.get("bg_low_threshold") or 70)
        if self.key == "glucose_high":
            return d.get("bg") is not None and d["bg"] >= (d.get("bg_high_threshold") or 180)
        if self.key == "glucose_rising":
            return str(d.get("direction", "")).lower() in {"singleup", "doubleup", "fortyfiveup", "rising"}
        if self.key == "glucose_falling":
            return str(d.get("direction", "")).lower() in {"singledown", "doubledown", "fortyfivedown", "falling"}
        if self.key == "glucose_rapid_rising":
            return str(d.get("direction", "")).lower() == "doubleup"
        if self.key == "glucose_rapid_falling":
            return str(d.get("direction", "")).lower() == "doubledown"
        if self.key == "closed_loop":
            return str(d.get("pump_status", "")).lower() == "closed loop"
        if self.key == "reservoir_warning_state":
            v, t = d.get("pump_reservoir"), d.get("reservoir_warning")
            return v is not None and t is not None and v <= t
        if self.key == "reservoir_critical_state":
            v, t = d.get("pump_reservoir"), d.get("reservoir_critical")
            return v is not None and t is not None and v <= t
        if self.key == "pump_battery_warning_state":
            v, t = d.get("pump_battery"), d.get("pump_battery_warning")
            return v is not None and t is not None and v <= t
        if self.key == "pump_battery_critical_state":
            v, t = d.get("pump_battery"), d.get("pump_battery_critical")
            return v is not None and t is not None and v <= t
        return bool(d.get(self.key))

    @property
    def extra_state_attributes(self):
        if self.key == "closed_loop":
            return {"pump_status": self.coordinator.data.get("pump_status")}
        return {}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        NightscoutExtendedBinary(coordinator, key, name, cat)
        for key, name, cat in BINARY
    ])
