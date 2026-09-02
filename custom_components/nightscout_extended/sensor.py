"""Sensors for Nightscout Extended."""
from __future__ import annotations

from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN
from .coordinator import NightscoutCoordinator

MMOL = "mmol/L"
MGDL = "mg/dL"
U = "U"
U_H = "U/h"
U_MIN = "U/min"
G = "g"

SENSORS = [
    ("bg", "Blood Glucose (mg/dL)", MGDL, None, None),
    ("bg_mmol", "Blood Glucose (mmol/L)", MMOL, None, None),
    ("delta", "Glucose Delta (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("direction", "Glucose Direction", None, None, None),
    ("glucose_age", "Glucose Data Age", UnitOfTime.SECONDS, None, EntityCategory.DIAGNOSTIC),
    ("eventual_bg", "Eventual BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("target_bg", "Target BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("iob", "Insulin On Board", U, None, None),
    ("basaliob", "Basal IOB", U, None, EntityCategory.DIAGNOSTIC),
    ("activity", "Insulin Activity", U_MIN, None, EntityCategory.DIAGNOSTIC),
    ("cob", "Carbs On Board", G, None, None),
    ("insulin_req", "Insulin Required", U, None, EntityCategory.DIAGNOSTIC),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, EntityCategory.DIAGNOSTIC),
    ("current_isf", "Current ISF", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("isf_for_carbs", "ISF for Carbs", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("carb_sensitivity", "Carb Sensitivity", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("carb_ratio", "Carb Ratio", G, None, EntityCategory.DIAGNOSTIC),
    ("profile_sens", "Profile Sensitivity", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("profile_basal", "Profile Basal Rate", U_H, None, EntityCategory.DIAGNOSTIC),
    ("profile_target_low", "Profile Target Low (mmol/L)", MMOL, None, EntityCategory.DIAGNOSTIC),
    ("profile_target_high", "Profile Target High (mmol/L)", MMOL, None, EntityCategory.DIAGNOSTIC),
    ("avg_pred", "Average Predicted BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("min_pred", "Minimum Predicted BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("min_iob_pred", "Minimum IOB Predicted BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("min_guard", "Minimum Guard BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("min_uam_pred", "Minimum UAM Predicted BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("naive_eventual", "Naive Eventual BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("bg_undershoot", "BG Undershoot", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("carb_impact", "Carb Impact", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("carb_impact_duration", "Carb Impact Duration", UnitOfTime.MINUTES, None, EntityCategory.DIAGNOSTIC),
    ("uam_impact", "UAM Impact", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("uam_duration", "UAM Duration", UnitOfTime.MINUTES, None, EntityCategory.DIAGNOSTIC),
    ("carbs_required", "Carbs Required", G, None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_duration", "Zero Temp Duration", UnitOfTime.MINUTES, None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_effect", "Zero Temp Effect", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("temp_basal_rate", "Temp Basal Rate", U_H, None, None),
    ("temp_basal_remaining", "Temp Basal Remaining", UnitOfTime.MINUTES, None, None),
    ("base_basal", "Base Basal Rate", U_H, None, EntityCategory.DIAGNOSTIC),
    ("last_bolus_amount", "Last Bolus Amount", U, None, EntityCategory.DIAGNOSTIC),
    ("pump_reservoir", "Pump Reservoir", U, None, None),
    ("pump_battery", "Pump Battery", PERCENTAGE, None, None),
    ("phone_battery", "AAPS Phone Battery", PERCENTAGE, None, None),
    ("avg_bg", "Average BG (mg/dL)", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("sd_bg", "BG Standard Deviation", MGDL, None, EntityCategory.DIAGNOSTIC),
    ("cv", "BG Coefficient of Variation", PERCENTAGE, None, EntityCategory.DIAGNOSTIC),
    ("tir", "Time in Range", PERCENTAGE, None, EntityCategory.DIAGNOSTIC),
    ("tbr", "Time Below Range", PERCENTAGE, None, EntityCategory.DIAGNOSTIC),
    ("tar", "Time Above Range", PERCENTAGE, None, EntityCategory.DIAGNOSTIC),
    ("very_high", "Time Very High", PERCENTAGE, None, EntityCategory.DIAGNOSTIC),
    ("gmi", "Glucose Management Indicator", None, None, EntityCategory.DIAGNOSTIC),
    ("insulin_today", "Insulin Total Today", U, None, EntityCategory.DIAGNOSTIC),
    ("bolus_today", "Bolus Total Today", U, None, EntityCategory.DIAGNOSTIC),
    ("carbs_today", "Carbs Total Today", G, None, EntityCategory.DIAGNOSTIC),
    ("glucose_entries", "Glucose Entries", None, None, EntityCategory.DIAGNOSTIC),
    ("treatments_count", "Treatments", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_low_mark", "AAPS Low Mark", MMOL, None, EntityCategory.CONFIG),
    ("aaps_high_mark", "AAPS High Mark", MMOL, None, EntityCategory.CONFIG),
    ("aaps_max_bolus", "AAPS Max Bolus", U, None, EntityCategory.CONFIG),
    ("aaps_max_carbs", "AAPS Max Carbs", G, None, EntityCategory.CONFIG),
    ("autosens_min", "Autosens Minimum", None, None, EntityCategory.CONFIG),
    ("autosens_max", "Autosens Maximum", None, None, EntityCategory.CONFIG),
    ("carb_absorption_cutoff", "Carb Absorption Cutoff", UnitOfTime.HOURS, None, EntityCategory.CONFIG),
    ("minimum_carb_impact", "Minimum Carb Impact", MGDL, None, EntityCategory.CONFIG),
    ("dynamic_isf_adjustment", "Dynamic ISF Adjustment", None, None, EntityCategory.CONFIG),
    ("reservoir_warning", "Reservoir Warning", U, None, EntityCategory.CONFIG),
    ("reservoir_critical", "Reservoir Critical", U, None, EntityCategory.CONFIG),
    ("pump_battery_warning", "Pump Battery Warning", PERCENTAGE, None, EntityCategory.CONFIG),
    ("pump_battery_critical", "Pump Battery Critical", PERCENTAGE, None, EntityCategory.CONFIG),
]

class NightscoutExtendedSensor(CoordinatorEntity[NightscoutCoordinator], SensorEntity):
    """A normalized Nightscout sensor."""

    def __init__(self, coordinator, key, name, unit, device_class, category):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_entity_category = category
        self._attr_has_entity_name = False

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        attrs = {}
        if self.key in {"direction", "bg", "bg_mmol", "delta"}:
            attrs["source"] = "Nightscout entries.json"
        elif self.key in {"aaps_low_mark", "aaps_high_mark", "aaps_max_bolus", "aaps_max_carbs",
                          "autosens_min", "autosens_max", "carb_absorption_cutoff",
                          "minimum_carb_impact", "dynamic_isf_adjustment", "reservoir_warning",
                          "reservoir_critical", "pump_battery_warning", "pump_battery_critical"}:
            attrs["source"] = "Nightscout devicestatus.json → AAPS configuration"
        elif self.key in {"profile_sens", "profile_basal", "profile_cr", "profile_target_low", "profile_target_high"}:
            attrs["source"] = "Nightscout profile.json"
        elif self.key in {"nightscout_version", "nightscout_units"}:
            attrs["source"] = "Nightscout status.json"
        else:
            attrs["source"] = "Nightscout devicestatus.json / treatments.json"
        if self.key == "gmi":
            attrs["note"] = "Calculated from recent glucose values; informational only."
        if self.key == "carbs_required":
            attrs["note"] = "Read-only AAPS diagnostic value."
        return attrs

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        NightscoutExtendedSensor(coordinator, key, name, unit, dc, cat)
        for key, name, unit, dc, cat in SENSORS
    ])
