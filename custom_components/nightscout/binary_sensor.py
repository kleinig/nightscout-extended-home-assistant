from __future__ import annotations

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
            "sw_version": coordinator.data.get("status_version"),
        }

    @property
    def is_on(self):
        data = self.coordinator.data
        if self._key == "glucose_low":
            bg = data.get("bg_mmol")
            low = data.get("low_mark_mmol") or 4.0
            return bg is not None and bg < low
        if self._key == "glucose_high":
            bg = data.get("bg_mmol")
            high = data.get("high_mark_mmol") or 10.0
            return bg is not None and bg > high
        if self._key == "closed_loop":
            return str(data.get("pump_status") or "").lower() in {"closed loop", "closed_loop"}
        if self._key == "pump_connected":
            status = str(data.get("pump_status") or "").lower()
            return bool(status) and data.get("last_aaps_update") is not None
        if self._key == "phone_charging":
            return bool(data.get("phone_charging"))
        if self._key == "stale_glucose":
            age = data.get("glucose_age")
            return age is None or age > 600
        if self._key == "reservoir_warning":
            r = data.get("pump_reservoir")
            threshold = data.get("res_warning")
            return r is not None and threshold is not None and r <= threshold
        if self._key == "reservoir_critical":
            r = data.get("pump_reservoir")
            threshold = data.get("res_critical")
            return r is not None and threshold is not None and r <= threshold
        if self._key == "pump_battery_warning":
            b = data.get("pump_battery")
            threshold = data.get("bat_warning")
            return b is not None and threshold is not None and b <= threshold
        if self._key == "pump_battery_critical":
            b = data.get("pump_battery")
            threshold = data.get("bat_critical")
            return b is not None and threshold is not None and b <= threshold
        return bool(data.get(self._key))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NightscoutBinarySensor(
            coordinator, entry.entry_id, *spec
        )
        for spec in SPECS
    )
