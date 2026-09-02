"""Binary sensors for Nightscout AAPS."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PHONE_BATTERY_WARNING,
    CONF_PUMP_BATTERY_WARNING,
    CONF_RESERVOIR_CRITICAL,
    CONF_RESERVOIR_WARNING,
    DOMAIN,
)
from .coordinator import NightscoutAAPSCoordinator


class NightscoutBinarySensor(CoordinatorEntity[NightscoutAAPSCoordinator], BinarySensorEntity):
    """A Nightscout AAPS binary sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, key, name, icon, is_on):
        super().__init__(coordinator)
        self.key = key
        self.is_on_fn = is_on
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

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
    def is_on(self):
        return self.is_on_fn(self.coordinator.data)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entry_data = coordinator.entry.data

    reservoir_warning = float(entry_data[CONF_RESERVOIR_WARNING])
    reservoir_critical = float(entry_data[CONF_RESERVOIR_CRITICAL])
    pump_battery_warning = float(entry_data[CONF_PUMP_BATTERY_WARNING])
    phone_battery_warning = float(entry_data[CONF_PHONE_BATTERY_WARNING])

    async_add_entities([
        NightscoutBinarySensor(
            coordinator,
            "reservoir_low",
            "Insulin Pump Reservoir Low",
            "mdi:alert-circle-outline",
            lambda d: d["reservoir"] <= reservoir_warning,
        ),
        NightscoutBinarySensor(
            coordinator,
            "reservoir_critical",
            "Insulin Pump Reservoir Critical",
            "mdi:alert-octagon-outline",
            lambda d: d["reservoir"] <= reservoir_critical,
        ),
        NightscoutBinarySensor(
            coordinator,
            "pump_battery_low",
            "Insulin Pump Battery Low",
            "mdi:battery-alert",
            lambda d: d["pump_battery"] <= pump_battery_warning,
        ),
        NightscoutBinarySensor(
            coordinator,
            "aaps_phone_battery_low",
            "AAPS Phone Battery Low",
            "mdi:cellphone-alert",
            lambda d: d["aaps_phone_battery"] <= phone_battery_warning,
        ),
        NightscoutBinarySensor(
            coordinator,
            "data_stale",
            "Nightscout Pump Data Stale",
            "mdi:cloud-alert",
            lambda d: d["data_age"] > 15,
        ),
    ])
