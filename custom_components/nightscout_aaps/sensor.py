"""Sensors for Nightscout AAPS."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import NightscoutAAPSCoordinator


@dataclass(frozen=True)
class Description:
    key: str
    name: str
    icon: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    value: Callable[[dict], object] = lambda data: None


SENSORS = [
    Description("reservoir", "Insulin Pump Reservoir", "mdi:water", "U", value=lambda d: d["reservoir"]),
    Description("reservoir_percent", "Insulin Pump Reservoir Percent", "mdi:water-percent", PERCENTAGE, value=lambda d: d["reservoir_percent"]),
    Description("pump_battery", "Insulin Pump Battery", "mdi:battery", PERCENTAGE, SensorDeviceClass.BATTERY, lambda d: d["pump_battery"]),
    Description("pump_status", "Insulin Pump Status", "mdi:diabetes", value=lambda d: d["pump_status"]),
    Description("profile", "Insulin Pump Profile", "mdi:account-cog", value=lambda d: d["profile"]),
    Description("base_basal", "Insulin Pump Base Basal", "mdi:water-minus", "U/h", value=lambda d: d["base_basal"]),
    Description("temp_basal", "Insulin Pump Temp Basal", "mdi:water-plus", "U/h", value=lambda d: d["temp_basal"]),
    Description("temp_basal_remaining", "Insulin Pump Temp Basal Remaining", "mdi:timer-outline", "min", value=lambda d: d["temp_basal_remaining"]),
    Description("last_bolus", "Insulin Pump Last Bolus", "mdi:needle", "U", value=lambda d: d["last_bolus"]),
    Description("aaps_phone_battery", "AAPS Phone Battery", "mdi:cellphone", PERCENTAGE, SensorDeviceClass.BATTERY, lambda d: d["aaps_phone_battery"]),
    Description("data_age", "Nightscout Pump Data Age", "mdi:clock-alert-outline", "min", value=lambda d: d["data_age"]),
    Description("daily_usage", "Insulin Pump Average Daily Usage", "mdi:chart-line", "U/day", value=lambda d: d["daily_usage"]),
    Description("estimated_days", "Insulin Pump Estimated Remaining Days", "mdi:calendar-clock", "d", value=lambda d: d["estimated_days"]),
    Description("estimated_hours", "Insulin Pump Estimated Remaining Hours", "mdi:clock-outline", "h", value=lambda d: d["estimated_hours"]),
]


class NightscoutSensor(CoordinatorEntity[NightscoutAAPSCoordinator], SensorEntity):
    """A Nightscout AAPS sensor."""

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator, description: Description):
        super().__init__(coordinator)
        self.description = description
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class

        if description.key in {
            "reservoir", "reservoir_percent", "pump_battery", "base_basal",
            "temp_basal", "temp_basal_remaining", "last_bolus",
            "aaps_phone_battery", "data_age", "daily_usage",
            "estimated_days", "estimated_hours",
        }:
            self._attr_state_class = "measurement"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name="Nightscout AAPS",
            manufacturer="Nightscout / AAPS",
            model=self.coordinator.data.get("app", "AAPS"),
            configuration_url=self.coordinator.url,
        )

    @property
    def native_value(self):
        return self.description.value(self.coordinator.data)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NightscoutSensor(coordinator, d) for d in SENSORS])
