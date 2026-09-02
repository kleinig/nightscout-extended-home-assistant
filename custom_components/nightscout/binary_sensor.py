from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NightscoutCoordinator


SPECS = [
    ("glucose_low", "Glucose Low", BinarySensorDeviceClass.PROBLEM, None),
    ("glucose_high", "Glucose High", BinarySensorDeviceClass.PROBLEM, None),
    ("glucose_rising", "Glucose Rising", None, None),
    ("glucose_falling", "Glucose Falling", None, None),
    ("glucose_rapid_rising", "Glucose Rapidly Rising", None, EntityCategory.DIAGNOSTIC),
    ("glucose_rapid_falling", "Glucose Rapidly Falling", None, EntityCategory.DIAGNOSTIC),
    ("closed_loop", "Closed Loop", None, None),
    ("pump_connected", "Pump Connected", None, None),
    ("phone_charging", "AAPS Phone Charging", None, None),
    ("stale_glucose", "Glucose Data Stale", BinarySensorDeviceClass.PROBLEM, None),
    ("reservoir_warning", "Reservoir Warning", BinarySensorDeviceClass.PROBLEM, None),
    ("reservoir_critical", "Reservoir Critical", BinarySensorDeviceClass.PROBLEM, None),
    ("pump_battery_warning", "Pump Battery Warning", BinarySensorDeviceClass.PROBLEM, None),
    ("pump_battery_critical", "Pump Battery Critical", BinarySensorDeviceClass.PROBLEM, None),
    ("dynamic_isf", "Dynamic ISF Active", None, EntityCategory.DIAGNOSTIC),
    ("smb_enabled", "SMB Enabled", None, EntityCategory.DIAGNOSTIC),
    ("delivery_received", "AAPS Delivery Received", None, EntityCategory.DIAGNOSTIC),
]


class NightscoutBinarySensor(CoordinatorEntity[NightscoutCoordinator], BinarySensorEntity):
    def __init__(self, coordinator, entry_id, key, name, device_class, category):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_class = device_class
        self._attr_entity_category = category
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Nightscout",
            "manufacturer": "Nightscout",
            "configuration_url": coordinator.base_url,
            "sw_version": coordinator.data.get("nightscout_version"),
        }

    @property
    def is_on(self):
        d = self.coordinator.data
        if self._key == "glucose_low":
            bg = d.get("bg_mmol")
            return bg is not None and bg < (d.get("low_mark_mmol") or 4.0)
        if self._key == "glucose_high":
            bg = d.get("bg_mmol")
            return bg is not None and bg > (d.get("high_mark_mmol") or 10.0)
        if self._key == "closed_loop":
            return str(d.get("pump_status") or "").lower().replace("_", " ") == "closed loop"
        if self._key == "pump_connected":
            age = d.get("last_aaps_update")
            return bool(d.get("pump_status")) and bool(age) and (
                (datetime.now(timezone.utc) - age).total_seconds() < 900
            )
        if self._key == "stale_glucose":
            age = d.get("glucose_age")
            return age is None or age > 600
        if self._key == "reservoir_warning":
            r, t = d.get("pump_reservoir"), d.get("res_warning")
            return r is not None and t is not None and r <= t
        if self._key == "reservoir_critical":
            r, t = d.get("pump_reservoir"), d.get("res_critical")
            return r is not None and t is not None and r <= t
        if self._key == "pump_battery_warning":
            b, t = d.get("pump_battery"), d.get("bat_warning")
            return b is not None and t is not None and b <= t
        if self._key == "pump_battery_critical":
            b, t = d.get("pump_battery"), d.get("bat_critical")
            return b is not None and t is not None and b <= t
        return bool(d.get(self._key))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NightscoutBinarySensor(coordinator, entry.entry_id, *spec) for spec in SPECS
    )
