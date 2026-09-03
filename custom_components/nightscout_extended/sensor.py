from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, NAME, VERSION
from .coordinator import NightscoutExtendedCoordinator


DEVICE = DeviceInfo(
    identifiers={(DOMAIN, "nightscout_extended")},
    name=NAME,
    manufacturer="Nightscout",
    model="Nightscout Extended",
    sw_version=VERSION,
)


SENSORS = [
    # Device age sensors populated from the Nightscout Socket.IO event stream.
    ("cannula_age", "Cannula Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("sensor_age", "CGM Sensor Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("insulin_age", "Insulin Cartridge Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("battery_age", "Pump Battery Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("last_cannula_change", "Last Cannula Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_sensor_change", "Last Sensor Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_insulin_change", "Last Insulin Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_battery_change", "Last Pump Battery Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    # Preferred display sensors follow Options > Display preferences.
    ("preferred_bg", "Blood Glucose", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("preferred_delta", "BG Delta", None, None, EntityCategory.DIAGNOSTIC),
    ("preferred_eventual_bg", "Eventual BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_target_bg", "Target BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_average_bg", "Average BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_isf", "Current ISF", None, None, None),
    # Core glucose
    ("bg_mgdl", "Blood Glucose (display)", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("bg_mmol", "Blood Glucose (mmol/L)", "mmol/L", None, None),
    ("delta_mgdl", "BG Delta (display)", None, None, None),
    ("delta_mmol", "BG Delta (mmol/L)", "mmol/L", None, None),
    ("direction", "BG Direction", None, None, None),
    ("glucose_age", "Glucose Age", "s", None, EntityCategory.DIAGNOSTIC),
    # AAPS / insulin
    ("iob", "Insulin on Board", "U", None, None),
    ("cob", "Carbs on Board", "g", None, None),
    ("eventual_bg", "Eventual BG (display)", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("eventual_bg_mmol", "Eventual BG (mmol/L)", "mmol/L", None, None),
    ("target_bg", "Target BG (display)", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("target_bg_mmol", "Target BG (mmol/L)", "mmol/L", None, None),
    ("insulin_required", "Insulin Required", "U", None, None),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, None),
    ("current_isf", "Current ISF", None, None, None),
    ("carb_ratio", "Carb Ratio", "g/U", None, None),
    ("profile_sens", "Profile Sensitivity", None, None, EntityCategory.DIAGNOSTIC),
    ("profile_name", "Active Profile", None, None, None),
    ("dia", "Insulin DIA", "h", None, None),
    ("profile_target_low", "Profile Target Low (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("profile_target_high", "Profile Target High (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("algorithm", "AAPS Algorithm", None, None, EntityCategory.DIAGNOSTIC),
    ("decision_state", "AAPS Decision", None, None, EntityCategory.DIAGNOSTIC),
    ("decision_reason", "AAPS Decision Reason", None, None, EntityCategory.DIAGNOSTIC),
    ("requested_rate", "Requested Basal Rate", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("requested_duration", "Requested Temp Basal Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("smb_amount", "SMB Amount", "U", None, EntityCategory.DIAGNOSTIC),
    # Predictions / diagnostics
    ("average_pred", "Average Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("minimum_pred", "Minimum Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("min_iob_pred", "Minimum IOB Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("min_guard", "Minimum Guard BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("min_uam", "Minimum UAM Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("naive_eventual", "Naive Eventual BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("bg_undershoot", "BG Undershoot", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("carb_impact", "Carb Impact", None, None, EntityCategory.DIAGNOSTIC),
    ("carb_impact_duration", "Carb Impact Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("uam_impact", "UAM Impact", None, None, EntityCategory.DIAGNOSTIC),
    ("uam_duration", "UAM Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("carbs_required", "Carbs Required", "g", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_duration", "Zero Temp Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_effect", "Zero Temp Effect", None, None, EntityCategory.DIAGNOSTIC),
    # Statistics
    ("average_bg_mgdl", "Average BG (display)", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("average_bg_mmol", "Average BG (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("bg_sd", "BG Standard Deviation", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("bg_cv", "BG Coefficient of Variation", "%", None, EntityCategory.DIAGNOSTIC),
    ("tir", "Time in Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tbr", "Time Below Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tar", "Time Above Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("very_high", "Time Very High", "%", None, EntityCategory.DIAGNOSTIC),
    ("gmi", "Glucose Management Indicator", "%", None, EntityCategory.DIAGNOSTIC),
    # Pump
    ("reservoir", "Pump Reservoir", "U", None, None),
    ("pump_battery", "Pump Battery", "%", None, None),
    ("pump_status", "Pump Status", None, None, None),
    ("pump_firmware", "Pump Firmware", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_clock", "Pump Clock", None, None, EntityCategory.DIAGNOSTIC),
    ("base_basal", "Base Basal Rate", "U/h", None, None),
    ("temp_basal_rate", "Temp Basal Rate", "U/h", None, None),
    ("temp_basal_remaining", "Temp Basal Remaining", "min", None, None),
    ("temp_basal_start", "Temp Basal Start", None, None, EntityCategory.DIAGNOSTIC),
    ("last_bolus_amount", "Last Bolus Amount", "U", None, None),
    ("last_bolus_time", "Last Bolus Time", None, None, EntityCategory.DIAGNOSTIC),
    # Phone / service
    ("phone_battery", "AAPS Phone Battery", "%", None, None),
    ("nightscout_version", "Nightscout Version", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_version", "AAPS Version", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_device", "AAPS Device", None, None, EntityCategory.DIAGNOSTIC),
    # Configuration
    ("low_mark", "AAPS Low Mark", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("high_mark", "AAPS High Mark", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("max_bolus", "AAPS Max Bolus", "U", None, EntityCategory.DIAGNOSTIC),
    ("max_carbs", "AAPS Max Carbs", "g", None, EntityCategory.DIAGNOSTIC),
    ("autosens_min", "Autosens Minimum", None, None, EntityCategory.DIAGNOSTIC),
    ("autosens_max", "Autosens Maximum", None, None, EntityCategory.DIAGNOSTIC),
    ("absorption_cutoff", "Carb Absorption Cutoff", "h", None, EntityCategory.DIAGNOSTIC),
    ("min_carb_impact", "Minimum Carb Impact", None, None, EntityCategory.DIAGNOSTIC),
    ("dyn_isf_adjust", "Dynamic ISF Adjustment", None, None, EntityCategory.DIAGNOSTIC),
    ("reservoir_warning", "Reservoir Warning", "U", None, EntityCategory.DIAGNOSTIC),
    ("reservoir_critical", "Reservoir Critical", "U", None, EntityCategory.DIAGNOSTIC),
    ("pump_battery_warning", "Pump Battery Warning", "%", None, EntityCategory.DIAGNOSTIC),
    ("pump_battery_critical", "Pump Battery Critical", "%", None, EntityCategory.DIAGNOSTIC),
    ("entry_count", "Glucose Entries", None, None, EntityCategory.DIAGNOSTIC),
    ("treatment_count", "Treatments", None, None, EntityCategory.DIAGNOSTIC),
]


def _value(data: dict[str, Any], key: str) -> Any:
    glucose_unit = data.get("glucose_unit", "mmol/L")
    isf_unit = data.get("isf_unit", "mmol/L/U")

    def glucose(value):
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value / 18 if glucose_unit == "mmol/L" else value

    def isf(value):
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value / 18 if isf_unit == "mmol/L/U" else value

    # Preferred entities.
    if key == "preferred_bg":
        return glucose(data.get("bg"))
    if key == "preferred_delta":
        return glucose(data.get("delta"))
    if key == "preferred_eventual_bg":
        return glucose(data.get("eventual_bg"))
    if key == "preferred_target_bg":
        return glucose(data.get("target_bg"))
    if key == "preferred_average_bg":
        return glucose(data.get("average_bg"))
    if key == "preferred_isf":
        return isf(data.get("variable_sens"))

    # Dynamic glucose-display entities.
    if key in {
        "bg_mgdl", "delta_mgdl", "eventual_bg", "target_bg",
        "average_bg_mgdl", "average_pred", "minimum_pred", "min_iob_pred",
        "min_guard", "min_uam", "naive_eventual", "bg_undershoot",
        "carb_impact", "uam_impact", "zero_temp_effect", "bg_sd",
        "min_carb_impact",
    }:
        source = {
            "bg_mgdl": "bg",
            "delta_mgdl": "delta",
            "eventual_bg": "eventual_bg",
            "target_bg": "target_bg",
            "average_bg_mgdl": "average_bg",
            "average_pred": "average_pred",
            "minimum_pred": "minimum_pred",
            "min_iob_pred": "min_iob_pred",
            "min_guard": "min_guard",
            "min_uam": "min_uam",
            "naive_eventual": "naive_eventual",
            "bg_undershoot": "bg_undershoot",
            "carb_impact": "carb_impact",
            "uam_impact": "uam_impact",
            "zero_temp_effect": "zero_temp_effect",
            "bg_sd": "bg_sd",
            "min_carb_impact": "min_carb_impact",
        }[key]
        return glucose(data.get(source))

    # Fixed mmol/L reference entities.
    if key == "bg_mmol":
        return glucose(data.get("bg")) if data.get("bg") is not None else None
    if key == "delta_mmol":
        return glucose(data.get("delta")) if data.get("delta") is not None else None
    if key == "eventual_bg_mmol":
        return glucose(data.get("eventual_bg")) if data.get("eventual_bg") is not None else None
    if key == "target_bg_mmol":
        return glucose(data.get("target_bg")) if data.get("target_bg") is not None else None
    if key == "average_bg_mmol":
        return glucose(data.get("average_bg")) if data.get("average_bg") is not None else None

    # Dynamic ISF entities.
    if key in {"current_isf", "profile_sens"}:
        return isf(data.get("variable_sens" if key == "current_isf" else "profile_sens"))

    if key in {"profile_target_low", "profile_target_high", "profile_name", "dia"}:
        return data.get(key)
    if key == "phone_battery":
        return data.get("uploader_battery")
    if key == "decision_state":
        return data.get("decision_state", "Unknown")
    if key == "decision_reason":
        reason = data.get("decision_reason")
        return "Available" if reason else "Unavailable"
    if key in {"requested_rate", "requested_duration", "smb_amount"}:
        return data.get(key)
    return data.get(key)


class NightscoutExtendedSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NightscoutExtendedCoordinator, key: str, name: str, unit, device_class, category):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"

        if key in {
            "preferred_bg", "preferred_delta", "preferred_eventual_bg",
            "preferred_target_bg", "preferred_average_bg",
            "bg_mgdl", "delta_mgdl", "eventual_bg", "target_bg",
            "average_bg_mgdl", "average_pred", "minimum_pred", "min_iob_pred",
            "min_guard", "min_uam", "naive_eventual", "bg_undershoot",
            "carb_impact", "uam_impact", "zero_temp_effect", "bg_sd",
            "min_carb_impact",
        }:
            self._attr_native_unit_of_measurement = coordinator.glucose_unit
        elif key in {"preferred_isf", "current_isf", "profile_sens"}:
            self._attr_native_unit_of_measurement = coordinator.isf_unit
        else:
            self._attr_native_unit_of_measurement = unit

        self._attr_device_class = device_class
        self._attr_entity_category = category
        self._attr_device_info = DEVICE


    @property
    def native_value(self):
        value = _value(self.coordinator.data, self.key)
        return value

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        attrs = {}
        if self.key in {"algorithm", "decision_reason", "eventual_bg", "target_bg", "iob"}:
            decision = data.get("decision", {})
            if decision:
                attrs.update({
                    "decision_source": decision.get("source"),
                    "decision_timestamp": decision.get("timestamp"),
                    "requested_rate": decision.get("rate"),
                    "requested_duration": decision.get("duration"),
                    "SMB": decision.get("smb"),
                })
                if self.key in {"decision_state", "decision_reason"}:
                    # Keep the complete AAPS explanation as an attribute. Unlike
                    # an entity state, attribute values are not subject to HA's
                    # 255-character state limit.
                    attrs["full_reason"] = decision.get("reason")
                    attrs["decision_reason"] = decision.get("reason")
                    attrs["decision_source"] = decision.get("source")
                    attrs["bg"] = decision.get("bg")
                    attrs["dosing_sensitivity"] = decision.get("dosing_sensitivity")
                    attrs["cob"] = decision.get("cob")
                    attrs["deviation"] = decision.get("deviation")
                    attrs["bgi"] = decision.get("bgi")
                    attrs["isf"] = decision.get("isf")
                    attrs["carb_ratio"] = decision.get("carb_ratio")
                    attrs["target_bg"] = decision.get("target_bg")
                    attrs["min_pred_bg"] = decision.get("min_pred_bg")
                    attrs["min_guard_bg"] = decision.get("min_guard_bg")
                    attrs["iob_pred_bg"] = decision.get("min_iob_pred")
                    attrs["uam_pred_bg"] = decision.get("min_uam_pred")
                    attrs["eventual_bg"] = decision.get("eventual_bg")
                    attrs["insulin_required"] = decision.get("insulin_required")
                    attrs["sensitivity_ratio"] = decision.get("sensitivity_ratio")
                    attrs["iob"] = decision.get("iob")
                    attrs["basal_iob"] = decision.get("basaliob")
                    attrs["requested_rate"] = decision.get("rate")
                    attrs["requested_duration"] = decision.get("duration")
                    attrs["smb_amount"] = decision.get("smb")
        if self.key == "average_pred":
            attrs["prediction_series_available"] = list((data.get("decision", {}).get("pred_bgs") or {}).keys())
        if self.key == "aaps_device":
            attrs["last_update"] = data.get("entry_time")
        age_meta = {
            "cannula_age": ("cage_warning", "cage_critical"),
            "sensor_age": ("sage_warning", "sage_critical"),
            "insulin_age": ("iage_warning", "iage_critical"),
            "battery_age": ("bage_warning", "bage_critical"),
        }
        if self.key in age_meta:
            warning_key, critical_key = age_meta[self.key]
            age = data.get(self.key)
            warning = data.get(warning_key)
            critical = data.get(critical_key)
            attrs.update({
                "warning_hours": warning,
                "critical_hours": critical,
            })
            if age is None:
                attrs["status"] = "unknown"
            elif critical is not None and age >= critical:
                attrs["status"] = "critical"
            elif warning is not None and age >= warning:
                attrs["status"] = "warning"
            else:
                attrs["status"] = "ok"
            attrs["last_change"] = data.get({
                "cannula_age": "last_cannula_change",
                "sensor_age": "last_sensor_change",
                "insulin_age": "last_insulin_change",
                "battery_age": "last_battery_change",
            }[self.key])
            attrs["event_type"] = data.get(f"{self.key}_event_type")
        return attrs or None

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id] if entry.entry_id in hass.data.get(DOMAIN, {}) else hass.data["nightscout_extended"][entry.entry_id]
    async_add_entities(
        [
            NightscoutExtendedSensor(coordinator, key, name, unit, device_class, category)
            for key, name, unit, device_class, category in SENSORS
        ]
    )
