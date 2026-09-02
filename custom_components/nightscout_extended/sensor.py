from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NightscoutCoordinator


SPECS = [
    ("bg_mgdl", "Blood Glucose (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, None),
    ("bg_mmol", "Blood Glucose (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, None),
    ("delta_mgdl", "Glucose Delta (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("delta_mmol", "Glucose Delta (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("direction", "Glucose Direction", None, None, None, None),
    ("glucose_age", "Glucose Data Age", UnitOfTime.SECONDS, SensorDeviceClass.DURATION, None, EntityCategory.DIAGNOSTIC),

    ("avg_bg_mgdl", "Average BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("avg_bg_mmol", "Average BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bg_sd_mgdl", "BG Standard Deviation", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bg_cv", "BG Coefficient of Variation", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("tir_percent", "Time in Range", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("tbr_percent", "Time Below Range", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("tar_percent", "Time Above Range", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("very_high_percent", "Time Very High", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("gmi", "Glucose Management Indicator", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("glucose_count", "Glucose Entries", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),

    ("eventual_bg_mgdl", "Eventual BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("eventual_bg_mmol", "Eventual BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("target_mgdl", "Target BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("target_mmol", "Target BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("iob", "Insulin On Board", "U", None, SensorStateClass.MEASUREMENT, None),
    ("basaliob", "Basal IOB", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("activity", "Insulin Activity", "U/min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("cob", "Carbs On Board", "g", None, SensorStateClass.MEASUREMENT, None),
    ("insulin_req", "Insulin Required", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("carbs_req", "Carbs Required", "g", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("isf_mgdl_for_carbs", "ISF for Carbs", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("current_isf", "Current ISF", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("profile_sens", "Profile Sensitivity", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("csf", "Carb Sensitivity", "mg/dL/g", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("carb_impact", "Carb Impact", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("carb_impact_duration", "Carb Impact Duration", "min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("uam_impact", "UAM Impact", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("uam_duration", "UAM Duration", "min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),

    ("avg_pred_bg_mgdl", "Average Predicted BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("avg_pred_bg_mmol", "Average Predicted BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_pred_bg_mgdl", "Minimum Predicted BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_pred_bg_mmol", "Minimum Predicted BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_guard_bg_mgdl", "Minimum Guard BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_guard_bg_mmol", "Minimum Guard BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_iob_pred_bg_mgdl", "Minimum IOB Predicted BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("min_iob_pred_bg_mmol", "Minimum IOB Predicted BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("naive_eventual_bg_mgdl", "Naive Eventual BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("naive_eventual_bg_mmol", "Naive Eventual BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),

    ("pump_reservoir", "Pump Reservoir", "U", None, SensorStateClass.MEASUREMENT, None),
    ("pump_battery", "Pump Battery", PERCENTAGE, None, SensorStateClass.MEASUREMENT, None),
    ("pump_status", "Pump Status", None, None, None, None),
    ("pump_clock", "Pump Clock", None, SensorDeviceClass.TIMESTAMP, None, EntityCategory.DIAGNOSTIC),
    ("pump_firmware", "Pump Firmware", None, None, None, EntityCategory.DIAGNOSTIC),
    ("last_bolus_amount", "Last Bolus Amount", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("last_bolus_time", "Last Bolus Time", None, SensorDeviceClass.TIMESTAMP, None, EntityCategory.DIAGNOSTIC),
    ("base_basal", "Base Basal Rate", "U/h", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("temp_basal_rate", "Temp Basal Rate", "U/h", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("temp_basal_start", "Temp Basal Start", None, SensorDeviceClass.TIMESTAMP, None, EntityCategory.DIAGNOSTIC),
    ("temp_basal_remaining", "Temp Basal Remaining", "min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("active_profile", "Active Pump Profile", None, None, None, None),

    ("phone_battery", "AAPS Phone Battery", PERCENTAGE, None, SensorStateClass.MEASUREMENT, None),
    ("aaps_device", "AAPS Device", None, None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_version", "AAPS Version", None, None, None, EntityCategory.DIAGNOSTIC),
    ("last_aaps_update", "Last AAPS Update", None, SensorDeviceClass.TIMESTAMP, None, EntityCategory.DIAGNOSTIC),
    ("nightscout_version", "Nightscout Version", None, None, None, EntityCategory.DIAGNOSTIC),

    ("insulin_total_today", "Insulin Total Today", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bolus_total_today", "Bolus Total Today", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("carbs_total_today", "Carbs Total Today", "g", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("treatment_count", "Treatments", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),

    ("max_bolus", "AAPS Max Bolus", "U", None, None, EntityCategory.CONFIG),
    ("max_carbs", "AAPS Max Carbs", "g", None, None, EntityCategory.CONFIG),
    ("low_mark_mmol", "AAPS Low Mark", "mmol/L", None, None, EntityCategory.CONFIG),
    ("high_mark_mmol", "AAPS High Mark", "mmol/L", None, None, EntityCategory.CONFIG),
    ("res_warning", "Reservoir Warning", "U", None, None, EntityCategory.CONFIG),
    ("res_critical", "Reservoir Critical", "U", None, None, EntityCategory.CONFIG),
    ("bat_warning", "Pump Battery Warning", PERCENTAGE, None, None, EntityCategory.CONFIG),
    ("bat_critical", "Pump Battery Critical", PERCENTAGE, None, None, EntityCategory.CONFIG),
    ("autosens_min", "Autosens Minimum", None, None, None, EntityCategory.CONFIG),
    ("autosens_max", "Autosens Maximum", None, None, None, EntityCategory.CONFIG),
    ("min_carb_impact", "Minimum Carb Impact", "mg/dL", None, None, EntityCategory.CONFIG),
    ("absorption_cutoff", "Carb Absorption Cutoff", "h", None, None, EntityCategory.CONFIG),
    ("dynamic_isf_adjust", "Dynamic ISF Adjustment", None, None, None, EntityCategory.CONFIG),
]


class NightscoutSensor(CoordinatorEntity[NightscoutCoordinator], SensorEntity):
    def __init__(self, coordinator, entry_id, key, name, unit, device_class, state_class, category):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = category
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Nightscout Extended",
            "manufacturer": "Nightscout",
            "configuration_url": coordinator.base_url,
            "sw_version": coordinator.data.get("nightscout_version"),
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        if self._key == "bg_mmol":
            return {
                "direction": d.get("direction"),
                "delta_mmol_l": d.get("delta_mmol"),
                "data_age_seconds": d.get("glucose_age"),
            }
        if self._key == "decision":
            return {
                "algorithm": d.get("algorithm"),
                "reason": d.get("decision_reason"),
                "insulin_required_u": d.get("insulin_req"),
                "carbs_required_g": d.get("carbs_req"),
                "requested_rate_u_h": d.get("requested_rate"),
                "requested_duration_min": d.get("requested_duration"),
                "requested_temp": d.get("requested_temp"),
                "requested_smb_u": d.get("requested_smb"),
                "smb_u": d.get("smb"),
                "smb_enabled": d.get("smb_enabled"),
                "dynamic_isf": d.get("dynamic_isf"),
                "sensitivity_ratio": d.get("sensitivity_ratio"),
                "eventual_bg_mmol_l": d.get("eventual_bg_mmol"),
                "target_bg_mmol_l": d.get("target_mmol"),
                "iob_u": d.get("iob"),
                "cob_g": d.get("cob"),
                "prediction_arrays": d.get("prediction_arrays"),
            }
        if self._key == "pump_status":
            return {
                "reservoir_u": d.get("pump_reservoir"),
                "battery_percent": d.get("pump_battery"),
                "firmware": d.get("pump_firmware"),
                "active_profile": d.get("active_profile"),
                "last_bolus_amount_u": d.get("last_bolus_amount"),
                "last_bolus_time": d.get("last_bolus_time"),
                "temp_basal_rate_u_h": d.get("temp_basal_rate"),
                "temp_basal_remaining_min": d.get("temp_basal_remaining"),
            }
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NightscoutSensor(coordinator, entry.entry_id, *spec) for spec in SPECS)
