from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, NAME, VERSION
from .coordinator import NightscoutExtendedCoordinator
from .coordinator import _bool


DEVICE = DeviceInfo(
    identifiers={(DOMAIN, "nightscout_extended")},
    name=NAME,
    manufacturer="Nightscout",
    model="Nightscout Extended",
    sw_version=VERSION,
)


BINARY_SENSORS = [
    ("phone_charging", "AAPS Phone Charging", EntityCategory.DIAGNOSTIC),
    ("dynamic_isf", "Dynamic ISF Active", EntityCategory.DIAGNOSTIC),
    ("aaps_dynamic_isf_running", "AAPS Dynamic ISF Running", EntityCategory.DIAGNOSTIC),
    ("smb_enabled", "SMB Enabled", EntityCategory.DIAGNOSTIC),
    ("delivery_received", "AAPS Delivery Received", EntityCategory.DIAGNOSTIC),
    ("pump_connected", "Pump Connected"),
    ("pump_bolusing", "Pump Bolusing"),
    ("pump_suspended", "Pump Suspended"),
    ("socket_connected", "Socket Connected"),
    ("glucose_stale", "Glucose Data Stale"),
    ("glucose_low", "Glucose Low"),
    ("glucose_high", "Glucose High"),
    ("glucose_rising", "Glucose Rising"),
    ("glucose_falling", "Glucose Falling"),
    ("glucose_rapid_rising", "Glucose Rapidly Rising"),
    ("glucose_rapid_falling", "Glucose Rapidly Falling"),
    ("closed_loop", "Closed Loop"),
    ("reservoir_warning_active", "Reservoir Warning Active"),
    ("reservoir_critical_active", "Reservoir Critical Active"),
    ("pump_battery_warning_active", "Pump Battery Warning Active"),
    ("pump_battery_critical_active", "Pump Battery Critical Active"),
]


def _is_on(data, key):
    bg = data.get("bg")
    delta = data.get("delta")
    direction = str(data.get("direction") or "").lower()

    if key == "phone_charging":
        return _bool(data.get("charging")) or False
    if key == "dynamic_isf":
        return _bool(data.get("dynamic_isf")) or False
    if key == "aaps_dynamic_isf_running":
        value = data.get("suggested_running_dynamic_isf")
        return (_bool(data.get("dynamic_isf")) or False) if value is None else (_bool(value) or False)
    if key == "smb_enabled":
        return _bool(data.get("smb_enabled")) or False
    if key == "delivery_received":
        return _bool(data.get("delivery_received")) or False
    if key == "pump_connected":
        return _bool(data.get("pump_connected")) or False
    if key == "pump_bolusing":
        return _bool(data.get("pump_bolusing")) or False
    if key == "pump_suspended":
        return _bool(data.get("pump_suspended")) or False
    if key == "socket_connected":
        return _bool(data.get("socket_connected")) or False
    if key == "glucose_stale":
        return (data.get("glucose_age") or 0) > 600
    if key == "glucose_low":
        return bg is not None and data.get("low_mark") is not None and bg < data["low_mark"]
    if key == "glucose_high":
        return bg is not None and data.get("high_mark") is not None and bg > data["high_mark"]
    if key == "glucose_rising":
        return direction in {"singleup", "doubleup", "fortyfiveup"} or (delta is not None and delta > 0)
    if key == "glucose_falling":
        return direction in {"singledown", "doubledown", "fortyfivedown"} or (delta is not None and delta < 0)
    if key == "glucose_rapid_rising":
        return direction in {"doubleup"} or (delta is not None and delta >= 3)
    if key == "glucose_rapid_falling":
        return direction in {"doubledown"} or (delta is not None and delta <= -3)
    if key == "closed_loop":
        return _bool(data.get("closed_loop")) or False
    if key == "reservoir_warning_active":
        threshold = data.get("reservoir_warning")
        return data.get("reservoir") is not None and threshold is not None and data["reservoir"] <= threshold
    if key == "reservoir_critical_active":
        threshold = data.get("reservoir_critical")
        return data.get("reservoir") is not None and threshold is not None and data["reservoir"] <= threshold
    if key == "pump_battery_warning_active":
        threshold = data.get("pump_battery_warning")
        return data.get("pump_battery") is not None and threshold is not None and data["pump_battery"] <= threshold
    if key == "pump_battery_critical_active":
        threshold = data.get("pump_battery_critical")
        return data.get("pump_battery") is not None and threshold is not None and data["pump_battery"] <= threshold
    return False


class NightscoutExtendedBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, category=None):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DEVICE
        self._attr_entity_category = category

    @property
    def is_on(self):
        return _is_on(self.coordinator.data, self.key)

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data["nightscout_extended"][entry.entry_id]
    async_add_entities(
        [NightscoutExtendedBinarySensor(coordinator, key, name, category) for key, name, category in [(item[0], item[1], item[2] if len(item) > 2 else None) for item in BINARY_SENSORS]]
    )
