from __future__ import annotations

from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NightscoutCoordinator


SPECS = [
    # Core glucose
    ("bg_mgdl", "Blood Glucose (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, None),
    ("bg_mmol", "Blood Glucose (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, None),
    ("delta_mgdl", "Glucose Delta (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("delta_mmol", "Glucose Delta (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("avg_bg_mgdl", "Average BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("avg_bg_mmol", "Average BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bg_sd_mgdl", "BG Standard Deviation", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bg_cv", "BG Coefficient of Variation", PERCENTAGE, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("glucose_age", "Glucose Data Age", UnitOfTime.SECONDS, SensorDeviceClass.DURATION, None, EntityCategory.DIAGNOSTIC),
    ("direction", "Glucose Direction", None, None, None, None),

    # AAPS / algorithm
    ("eventual_bg_mgdl", "Eventual BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("eventual_bg_mmol", "Eventual BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("target_mgdl", "Target BG (mg/dL)", "mg/dL", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("target_mmol", "Target BG (mmol/L)", "mmol/L", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("iob", "Insulin On Board", "U", None, SensorStateClass.MEASUREMENT, None),
    ("basaliob", "Basal IOB", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("activity", "Insulin Activity", "U/min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("cob", "Carbs On Board", "g", None, SensorStateClass.MEASUREMENT, None),
    ("insulin_req", "Insulin Required", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("dynamic_isf", "Dynamic ISF Active", None, None, None, EntityCategory.DIAGNOSTIC),
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
    ("carbs_req", "Carbs Required", "g", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("requested_rate", "Requested Basal Rate", "U/h", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("requested_duration", "Requested Temp Basal Duration", "min", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("smb", "SMB Amount", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("decision", "AAPS Decision", None, None, None, EntityCategory.DIAGNOSTIC),

    # Pump
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

    # Uploader / Nightscout
    ("phone_battery", "AAPS Phone Battery", PERCENTAGE, None, SensorStateClass.MEASUREMENT, None),
    ("aaps_device", "AAPS Device", None, None, None, EntityCategory.DIAGNOSTIC),
    ("last_aaps_update", "Last AAPS Update", None, SensorDeviceClass.TIMESTAMP, None, EntityCategory.DIAGNOSTIC),
    ("status_version", "Nightscout Version", None, None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_version", "AAPS Version", None, None, None, EntityCategory.DIAGNOSTIC),

    # Daily / history
    ("insulin_total_today", "Insulin Total Today", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("bolus_total_today", "Bolus Total Today", "U", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("carbs_total_today", "Carbs Total Today", "g", None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("glucose_count", "Glucose Entries", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),
    ("treatment_count", "Treatments", None, None, SensorStateClass.MEASUREMENT, EntityCategory.DIAGNOSTIC),

    # Configuration / limits
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
            "name": "Nightscout",
            "manufacturer": "Nightscout",
            "configuration_url": coordinator.base_url,
            "sw_version": coordinator.data.get("status_version"),
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if self._key == "bg_mmol":
            return {
                "direction": data.get("direction"),
                "delta_mmol_l": data.get("delta_mmol"),
                "data_age_seconds": data.get("glucose_age"),
            }
        if self._key == "decision":
            return {
                "reason": data.get("decision_reason"),
                "algorithm": data.get("algorithm"),
                "insulin_required_u": data.get("insulin_req"),
                "requested_rate_u_h": data.get("requested_rate"),
                "requested_duration_min": data.get("requested_duration"),
                "smb_u": data.get("smb"),
                "sensitivity_ratio": data.get("sensitivity_ratio"),
                "dynamic_isf": data.get("dynamic_isf"),
                "eventual_bg_mmol_l": data.get("eventual_bg_mmol"),
                "target_bg_mmol_l": data.get("target_mmol"),
                "min_predicted_bg_mmol_l": data.get("min_pred_bg_mmol"),
            }
        if self._key == "pump_status":
            return {
                "reservoir_u": data.get("pump_reservoir"),
                "battery_percent": data.get("pump_battery"),
                "firmware": data.get("pump_firmware"),
                "active_profile": data.get("active_profile"),
                "last_bolus_amount_u": data.get("last_bolus_amount"),
            }
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        NightscoutSensor(
            coordinator, entry.entry_id, *spec
        )
        for spec in SPECS
    )
