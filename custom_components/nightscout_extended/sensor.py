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
    # Preferred display sensors follow Options > Display preferences.
    ("preferred_bg", "Blood Glucose", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("preferred_delta", "BG Delta", None, None, EntityCategory.DIAGNOSTIC),
    ("preferred_eventual_bg", "Eventual BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_target_bg", "Target BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_average_bg", "Average BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("preferred_isf", "Current ISF", None, None, None),
    # Core glucose
    ("bg_mgdl", "Blood Glucose (mg/dL)", "mg/dL", None, None),
    ("bg_mmol", "Blood Glucose (mmol/L)", "mmol/L", None, None),
    ("delta_mgdl", "BG Delta (mg/dL)", "mg/dL", None, None),
    ("delta_mmol", "BG Delta (mmol/L)", "mmol/L", None, None),
    ("direction", "BG Direction", None, None, None),
    ("glucose_age", "Glucose Age", "s", None, EntityCategory.DIAGNOSTIC),
    # AAPS / insulin
    ("iob", "Insulin on Board", "U", None, None),
    ("cob", "Carbs on Board", "g", None, None),
    ("eventual_bg", "Eventual BG (mg/dL)", "mg/dL", None, None),
    ("eventual_bg_mmol", "Eventual BG (mmol/L)", "mmol/L", None, None),
    ("target_bg", "Target BG (mg/dL)", "mg/dL", None, None),
    ("target_bg_mmol", "Target BG (mmol/L)", "mmol/L", None, None),
    ("insulin_required", "Insulin Required", "U", None, None),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, None),
    ("current_isf", "Current ISF (mg/dL/U)", "mg/dL/U", None, None),
    ("carb_ratio", "Carb Ratio", "g/U", None, None),
    ("profile_sens", "Profile Sensitivity (mg/dL/U)", "mg/dL/U", None, None),
    ("profile_name", "Active Profile", None, None, None),
    ("dia", "Insulin DIA", "h", None, None),
    ("profile_target_low", "Profile Target Low (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("profile_target_high", "Profile Target High (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("algorithm", "AAPS Algorithm", None, None, EntityCategory.DIAGNOSTIC),
    ("decision_reason", "AAPS Decision Reason", None, None, EntityCategory.DIAGNOSTIC),
    ("requested_rate", "Requested Basal Rate", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("requested_duration", "Requested Temp Basal Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("smb_amount", "SMB Amount", "U", None, EntityCategory.DIAGNOSTIC),
    # Predictions / diagnostics
    ("average_pred", "Average Predicted BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("minimum_pred", "Minimum Predicted BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("min_iob_pred", "Minimum IOB Predicted BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("min_guard", "Minimum Guard BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("min_uam", "Minimum UAM Predicted BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("naive_eventual", "Naive Eventual BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("bg_undershoot", "BG Undershoot", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("carb_impact", "Carb Impact", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("carb_impact_duration", "Carb Impact Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("uam_impact", "UAM Impact", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("uam_duration", "UAM Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("carbs_required", "Carbs Required", "g", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_duration", "Zero Temp Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_effect", "Zero Temp Effect", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    # Statistics
    ("average_bg_mgdl", "Average BG (mg/dL)", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("average_bg_mmol", "Average BG (mmol/L)", "mmol/L", None, EntityCategory.DIAGNOSTIC),
    ("bg_sd", "BG Standard Deviation", "mg/dL", None, EntityCategory.DIAGNOSTIC),
    ("bg_cv", "BG Coefficient of Variation", "%", None, EntityCategory.DIAGNOSTIC),
    ("tir", "Time in Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tbr", "Time Below Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tar", "Time Above Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("very_high", "Time Very High", "%", None, EntityCategory.DIAGNOSTIC),
    ("gmi", "Glucose Management Indicator", "%", None, EntityCategory.DIAGNOSTIC),
    # Age / status-light timers
    ("cannula_age", "Cannula Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("sensor_age", "CGM Sensor Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("insulin_age", "Insulin Cartridge Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("battery_age", "Pump Battery Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("cannula_last_change", "Last Cannula Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("sensor_last_change", "Last CGM Sensor Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("insulin_last_change", "Last Insulin Cartridge Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("battery_last_change", "Last Pump Battery Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
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
    ("min_carb_impact", "Minimum Carb Impact", "mg/dL", None, EntityCategory.DIAGNOSTIC),
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

    if key == "preferred_bg":
        value = data.get("bg")
        return value / 18 if value is not None and glucose_unit == "mmol/L" else value
    if key == "preferred_delta":
        value = data.get("delta")
        return value / 18 if value is not None and glucose_unit == "mmol/L" else value
    if key == "preferred_eventual_bg":
        value = data.get("eventual_bg")
        return value / 18 if value is not None and glucose_unit == "mmol/L" else value
    if key == "preferred_target_bg":
        value = data.get("target_bg")
        return value / 18 if value is not None and glucose_unit == "mmol/L" else value
    if key == "preferred_average_bg":
        value = data.get("average_bg")
        return value / 18 if value is not None and glucose_unit == "mmol/L" else value
    if key == "preferred_isf":
        value = data.get("variable_sens")
        return value / 18 if value is not None and isf_unit == "mmol/L/U" else value

    if key == "bg_mgdl":
        return data.get("bg")
    if key == "bg_mmol":
        v = data.get("bg")
        return v / 18 if v is not None else None
    if key == "delta_mgdl":
        return data.get("delta")
    if key == "delta_mmol":
        v = data.get("delta")
        return v / 18 if v is not None else None
    if key == "current_isf":
        value = data.get("variable_sens")
        return value if isf_unit == "mg/dL/U" else (value / 18 if value is not None else None)
    if key == "eventual_bg":
        return data.get("eventual_bg")
    if key == "eventual_bg_mmol":
        v = data.get("eventual_bg")
        return v / 18 if v is not None else None
    if key == "target_bg":
        return data.get("target_bg")
    if key == "target_bg_mmol":
        v = data.get("target_bg")
        return v / 18 if v is not None else None
    if key == "average_bg_mgdl":
        return data.get("average_bg")
    if key == "average_bg_mmol":
        value = data.get("average_bg")
        return value / 18 if value is not None else None
    if key in {"profile_target_low", "profile_target_high", "profile_name", "dia"}:
        return data.get(key)
    if key == "phone_battery":
        return data.get("uploader_battery")
    if key in {"requested_rate", "requested_duration", "smb_amount"}:
        return data.get(key)
    return data.get(key)


class NightscoutExtendedSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NightscoutExtendedCoordinator, key: str, name: str, unit, device_class, category):
        self.coordinator = coordinator
        self.key = key
        preferred_names = {
            "preferred_bg": "Blood Glucose",
            "preferred_delta": "BG Delta",
            "preferred_eventual_bg": "Eventual BG",
            "preferred_target_bg": "Target BG",
            "preferred_average_bg": "Average BG",
            "preferred_isf": "Current ISF",
        }
        self._attr_name = preferred_names.get(key, name)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        if key in {"preferred_bg", "preferred_delta", "preferred_eventual_bg",
                   "preferred_target_bg", "preferred_average_bg"}:
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
        return _value(self.coordinator.data, self.key)

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
        if self.key == "average_pred":
            attrs["prediction_series_available"] = list((data.get("decision", {}).get("pred_bgs") or {}).keys())
        if self.key == "aaps_device":
            attrs["last_update"] = data.get("entry_time")

        age_info = {
            "cannula_age": ("cannula_age_warning", "cannula_age_critical", "cannula_last_change"),
            "sensor_age": ("sensor_age_warning", "sensor_age_critical", "sensor_last_change"),
            "insulin_age": ("insulin_age_warning", "insulin_age_critical", "insulin_last_change"),
            "battery_age": ("battery_age_warning", "battery_age_critical", "battery_last_change"),
        }
        if self.key in age_info:
            warning_key, critical_key, timestamp_key = age_info[self.key]
            attrs.update({
                "warning_hours": data.get(warning_key),
                "critical_hours": data.get(critical_key),
                "last_change": data.get(timestamp_key),
                "source": "Nightscout treatment event",
            })

        timestamp_age_map = {
            "cannula_last_change": "cannula_age",
            "sensor_last_change": "sensor_age",
            "insulin_last_change": "insulin_age",
            "battery_last_change": "battery_age",
        }
        if self.key in timestamp_age_map:
            attrs["age_hours"] = data.get(timestamp_age_map[self.key])
            attrs["source"] = "Nightscout treatment event"

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
