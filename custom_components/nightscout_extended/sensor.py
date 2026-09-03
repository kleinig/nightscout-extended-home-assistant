from __future__ import annotations

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

# One entity per real value. Glucose/ISF values follow the user's Options unit
# selection rather than creating duplicate mg/dL and mmol/L entities.
SENSORS = [
    # Device/change ages
    ("cannula_age", "Cannula Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("sensor_age", "CGM Sensor Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("insulin_age", "Insulin Cartridge Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("battery_age", "Pump Battery Age", "h", None, EntityCategory.DIAGNOSTIC),
    ("last_cannula_change", "Last Cannula Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_sensor_change", "Last Sensor Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_insulin_change", "Last Insulin Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_battery_change", "Last Pump Battery Change", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),

    # Glucose
    ("bg", "Blood Glucose", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, None),
    ("delta", "BG Delta", None, None, EntityCategory.DIAGNOSTIC),
    ("direction", "BG Direction", None, None, None),
    ("glucose_age", "Glucose Age", "s", None, EntityCategory.DIAGNOSTIC),

    # AAPS/OpenAPS decision - raw values where supplied
    ("decision_state", "AAPS Decision", None, None, EntityCategory.DIAGNOSTIC),
    ("decision_reason", "AAPS Decision Reason", None, None, EntityCategory.DIAGNOSTIC),
    ("decision_source", "AAPS Decision Source", None, None, EntityCategory.DIAGNOSTIC),
    ("algorithm", "AAPS Algorithm", None, None, EntityCategory.DIAGNOSTIC),
    ("variable_sens", "Variable Sensitivity", None, None, EntityCategory.DIAGNOSTIC),
    ("cob", "Carbs on Board", "g", None, None),
    ("eventual_bg", "Eventual BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("target_bg", "AAPS Target BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("insulin_required", "Insulin Required", "U", None, None),
    ("sensitivity_ratio", "Sensitivity Ratio", None, None, EntityCategory.DIAGNOSTIC),
    ("snooze_bg", "Snooze BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("aaps_tick", "AAPS Tick", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_temp", "AAPS Temp Type", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_delivery_time", "AAPS Delivery Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("aaps_suggestion_time", "AAPS Suggestion Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),

    # Raw OpenAPS IOB
    ("iob", "Insulin on Board", "U", None, None),
    ("basal_iob", "Basal IOB", "U", None, None),
    ("bolus_iob", "Bolus IOB", "U", None, None),
    ("insulin_activity", "Insulin Activity", "U/min", None, None),
    ("bolus_snooze", "Bolus Snooze", "U", None, EntityCategory.DIAGNOSTIC),
    ("net_basal_insulin", "Net Basal Insulin", "U", None, EntityCategory.DIAGNOSTIC),
    ("high_temp_insulin", "High Temp Insulin", "U", None, EntityCategory.DIAGNOSTIC),
    ("microbolus_insulin", "Microbolus Insulin", "U", None, EntityCategory.DIAGNOSTIC),
    ("microbolus_iob", "Microbolus IOB", "U", None, EntityCategory.DIAGNOSTIC),
    ("iob_last_bolus_time", "IOB Last Bolus Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("iob_timestamp", "IOB Calculation Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),

    # Suggested / enacted raw delivery values
    ("suggested_bg", "AAPS Suggested BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("suggested_snooze_bg", "AAPS Suggested Snooze BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("suggested_tick", "AAPS Suggested Tick", None, None, EntityCategory.DIAGNOSTIC),
    ("suggested_temp", "AAPS Suggested Temp Type", None, None, EntityCategory.DIAGNOSTIC),
    ("suggested_min_pred_bg", "AAPS Suggested Minimum Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("suggested_rate", "AAPS Suggested Basal Rate", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("suggested_duration", "AAPS Suggested Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("suggested_deliver_at", "AAPS Suggested Delivery Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("suggested_timestamp", "AAPS Suggested Calculation Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("suggested_insulin_required", "AAPS Suggested Insulin Required", "U", None, EntityCategory.DIAGNOSTIC),
    ("suggested_target_bg", "AAPS Suggested Target BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("suggested_sensitivity_ratio", "AAPS Suggested Sensitivity Ratio", None, None, EntityCategory.DIAGNOSTIC),
    ("suggested_variable_sens", "AAPS Suggested Variable Sensitivity", None, None, EntityCategory.DIAGNOSTIC),
    ("suggested_algorithm", "AAPS Suggested Algorithm", None, None, EntityCategory.DIAGNOSTIC),
    ("suggested_reservoir", "AAPS Suggested Reservoir", "U", None, EntityCategory.DIAGNOSTIC),
    ("suggested_smb", "AAPS Suggested SMB", "U", None, EntityCategory.DIAGNOSTIC),
    ("suggested_units", "AAPS Suggested Units", "U", None, EntityCategory.DIAGNOSTIC),
    ("suggested_meal_assist", "AAPS Suggested Meal Assist", None, None, EntityCategory.DIAGNOSTIC),
    ("enacted_bg", "AAPS Enacted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("enacted_snooze_bg", "AAPS Enacted Snooze BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("enacted_tick", "AAPS Enacted Tick", None, None, EntityCategory.DIAGNOSTIC),
    ("enacted_temp", "AAPS Enacted Temp Type", None, None, EntityCategory.DIAGNOSTIC),
    ("enacted_min_pred_bg", "AAPS Enacted Minimum Predicted BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("enacted_rate", "AAPS Enacted Basal Rate", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("enacted_duration", "AAPS Enacted Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("enacted_deliver_at", "AAPS Enacted Delivery Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("enacted_timestamp", "AAPS Enacted Calculation Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("enacted_insulin_required", "AAPS Enacted Insulin Required", "U", None, EntityCategory.DIAGNOSTIC),
    ("enacted_target_bg", "AAPS Enacted Target BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("enacted_sensitivity_ratio", "AAPS Enacted Sensitivity Ratio", None, None, EntityCategory.DIAGNOSTIC),
    ("enacted_units", "AAPS Enacted Units", "U", None, EntityCategory.DIAGNOSTIC),
    ("enacted_meal_assist", "AAPS Enacted Meal Assist", None, None, EntityCategory.DIAGNOSTIC),

    # Predictions: native AAPS minima plus useful derived series statistics
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
    ("zero_temp_duration", "Zero Temp Duration", "min", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_effect", "Zero Temp Effect", None, None, EntityCategory.DIAGNOSTIC),
    ("carbs_required", "Carbs Required", "g", None, EntityCategory.DIAGNOSTIC),
    ("autosens_ratio", "Autosens Ratio", None, None, EntityCategory.DIAGNOSTIC),
    ("future_state_sensitivity", "Future State Sensitivity", None, None, EntityCategory.DIAGNOSTIC),
    ("csf", "Carb Sensitivity Factor", None, None, EntityCategory.DIAGNOSTIC),
    ("isf_for_carbs", "ISF for Carbs", None, None, EntityCategory.DIAGNOSTIC),
    ("meal_insulin_required", "Meal Insulin Required", "U", None, EntityCategory.DIAGNOSTIC),
    ("max_uam_smb_basal_minutes", "Maximum UAM SMB Basal Minutes", "min", None, EntityCategory.DIAGNOSTIC),
    ("aaps_current_basal", "AAPS Current Basal", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("last_bolus_age", "AAPS Last Bolus Age", "min", None, EntityCategory.DIAGNOSTIC),
    ("zero_temp_rate", "Zero Temp Required Rate", "U/h", None, EntityCategory.DIAGNOSTIC),
    ("mmtune_frequency", "AAPS MMTune Frequency", None, None, EntityCategory.DIAGNOSTIC),
    ("mmtune_best_rssi", "AAPS MMTune Best RSSI", "dBm", None, EntityCategory.DIAGNOSTIC),
    ("mmtune_timestamp", "AAPS MMTune Timestamp", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),

    # Profile/configuration
    ("profile_name", "Active Profile", None, None, None),
    ("profile_timezone", "Nightscout Profile Timezone", None, None, EntityCategory.DIAGNOSTIC),
    ("current_isf", "Current ISF", None, None, None),
    ("profile_sens", "Profile Sensitivity", None, None, EntityCategory.DIAGNOSTIC),
    ("carb_ratio", "Carb Ratio", "g/U", None, None),
    ("dia", "Insulin DIA", "h", None, None),
    ("profile_target_low", "Profile Target Low", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("profile_target_high", "Profile Target High", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("low_mark", "AAPS Low Mark", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("high_mark", "AAPS High Mark", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("max_bolus", "AAPS Max Bolus", "U", None, EntityCategory.DIAGNOSTIC),
    ("max_carbs", "AAPS Max Carbs", "g", None, EntityCategory.DIAGNOSTIC),
    ("autosens_min", "Autosens Minimum", None, None, EntityCategory.DIAGNOSTIC),
    ("autosens_max", "Autosens Maximum", None, None, EntityCategory.DIAGNOSTIC),
    ("absorption_cutoff", "Carb Absorption Cutoff", "h", None, EntityCategory.DIAGNOSTIC),
    ("min_carb_impact", "Minimum Carb Impact", None, None, EntityCategory.DIAGNOSTIC),
    ("dyn_isf_adjust", "Dynamic ISF Adjustment", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_config_version", "AAPS Configuration Version", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_config_pump", "AAPS Configuration Pump", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_config_insulin", "AAPS Configuration Insulin", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_config_aps", "AAPS Configuration APS", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_config_sensitivity", "AAPS Configuration Sensitivity", None, None, EntityCategory.DIAGNOSTIC),

    # Pump
    ("reservoir", "Pump Reservoir", "U", None, None),
    ("pump_battery", "Pump Battery", "%", None, None),
    ("pump_status", "Pump Status", None, None, None),
    ("pump_battery_status", "Pump Battery Status", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_battery_voltage", "Pump Battery Voltage", "mV", None, EntityCategory.DIAGNOSTIC),
    ("pump_status_timestamp", "Pump Status Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("pump_firmware", "Pump Firmware", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_manufacturer", "Pump Manufacturer", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_model", "Pump Model", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_device", "Pump Device", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_active_profile", "Pump Active Profile", None, None, EntityCategory.DIAGNOSTIC),
    ("pump_clock", "Pump Clock", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("base_basal", "Base Basal Rate", "U/h", None, None),
    ("temp_basal_rate", "Temp Basal Rate", "U/h", None, None),
    ("temp_basal_remaining", "Temp Basal Remaining", "min", None, None),
    ("temp_basal_start", "Temp Basal Start", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),
    ("last_bolus_amount", "Last Bolus Amount", "U", None, None),
    ("last_bolus_time", "Last Bolus Time", None, SensorDeviceClass.TIMESTAMP, EntityCategory.DIAGNOSTIC),

    # Uploader/service
    ("phone_battery", "AAPS Phone Battery", "%", None, None),
    ("uploader_battery_voltage", "AAPS Uploader Battery Voltage", "mV", None, EntityCategory.DIAGNOSTIC),
    ("nightscout_version", "Nightscout Version", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_version", "AAPS Version", None, None, EntityCategory.DIAGNOSTIC),
    ("aaps_device", "AAPS Device", None, None, EntityCategory.DIAGNOSTIC),

    # Stats / counts
    ("average_bg", "Average BG", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("bg_sd", "BG Standard Deviation", None, SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION, EntityCategory.DIAGNOSTIC),
    ("bg_cv", "BG Coefficient of Variation", "%", None, EntityCategory.DIAGNOSTIC),
    ("tir", "Time in Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tbr", "Time Below Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("tar", "Time Above Range", "%", None, EntityCategory.DIAGNOSTIC),
    ("very_high", "Time Very High", "%", None, EntityCategory.DIAGNOSTIC),
    ("gmi", "Glucose Management Indicator", "%", None, EntityCategory.DIAGNOSTIC),
    ("entry_count", "Glucose Entries", None, None, EntityCategory.DIAGNOSTIC),
    ("treatment_count", "Treatments", None, None, EntityCategory.DIAGNOSTIC),
]

GLUCOSE_KEYS = {
    "bg", "delta", "eventual_bg", "target_bg", "snooze_bg", "suggested_bg", "suggested_snooze_bg",
    "suggested_min_pred_bg", "suggested_target_bg", "enacted_bg", "enacted_snooze_bg",
    "enacted_min_pred_bg", "enacted_target_bg", "average_pred", "minimum_pred", "min_iob_pred",
    "min_guard", "min_uam", "naive_eventual", "bg_undershoot", "average_bg", "bg_sd",
    "profile_target_low", "profile_target_high", "low_mark", "high_mark", "aaps_tick", "suggested_tick", "enacted_tick",
}
ISF_KEYS = {"current_isf", "profile_sens", "variable_sens", "suggested_variable_sens"}
TIMESTAMP_KEYS = {key for key, _, _, device_class, _ in SENSORS if device_class == SensorDeviceClass.TIMESTAMP}


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _value(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    glucose_unit = data.get("glucose_unit", "mmol/L")
    isf_unit = data.get("isf_unit", "mmol/L/U")

    if key == "decision_reason":
        return "Available" if data.get("decision_reason") else "Unavailable"
    if key == "decision_source":
        return (data.get("decision") or {}).get("source")
    if key == "current_isf":
        value = data.get("variable_sens")
    elif key == "average_bg":
        value = data.get("average_bg")

    if key in GLUCOSE_KEYS:
        value = _number(value)
        return value / 18.0 if value is not None and glucose_unit == "mmol/L" else value
    if key in ISF_KEYS:
        value = _number(value)
        return value / 18.0 if value is not None and isf_unit == "mmol/L/U" else value
    return value


class NightscoutExtendedSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: NightscoutExtendedCoordinator, key: str, name: str, unit, device_class, category):
        self.coordinator = coordinator
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        if key in GLUCOSE_KEYS:
            self._attr_native_unit_of_measurement = coordinator.glucose_unit
        elif key in ISF_KEYS:
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
        attrs: dict[str, Any] = {}
        decision = data.get("decision") or {}

        if self.key in {"decision_state", "decision_reason", "decision_source"}:
            attrs.update({
                "full_reason": decision.get("reason"),
                "decision_timestamp": decision.get("timestamp"),
                "source": decision.get("source"),
                "algorithm": decision.get("algorithm"),
                "bg_mgdl": decision.get("bg"),
                "eventual_bg_mgdl": decision.get("eventual_bg"),
                "target_bg_mgdl": decision.get("target_bg"),
                "insulin_required": decision.get("insulin_required"),
                "sensitivity_ratio": decision.get("sensitivity_ratio"),
                "variable_sens_mgdl_u": decision.get("variable_sens"),
                "iob": data.get("iob"),
                "basal_iob": data.get("basal_iob"),
                "cob": decision.get("cob"),
                "requested_rate": decision.get("rate"),
                "requested_duration": decision.get("duration"),
                "smb_amount": decision.get("smb"),
            })
        if self.key == "average_pred":
            attrs["prediction_series_available"] = list((decision.get("pred_bgs") or {}).keys())
            attrs["suggested_prediction_series"] = list((data.get("suggested_pred_bgs") or {}).keys())
            attrs["enacted_prediction_series"] = list((data.get("enacted_pred_bgs") or {}).keys())
            attrs["suggested_pred_bgs"] = data.get("suggested_pred_bgs") or {}
            attrs["enacted_pred_bgs"] = data.get("enacted_pred_bgs") or {}
        if self.key in {"mmtune_frequency", "mmtune_best_rssi", "mmtune_timestamp"}:
            attrs["mmtune"] = data.get("mmtune") or {}
        if self.key == "aaps_device":
            attrs["last_update"] = data.get("entry_time")
        if self.key in TIMESTAMP_KEYS:
            attrs["timezone"] = data.get("profile_timezone")
        if self.key in {"pump_status", "pump_battery_status"}:
            attrs.update({
                "bolusing": data.get("pump_bolusing"),
                "suspended": data.get("pump_suspended"),
                "status_timestamp": data.get("pump_status_timestamp"),
            })
        if self.key in {"aaps_config_version", "aaps_config_pump", "aaps_config_insulin", "aaps_config_aps", "aaps_config_sensitivity"}:
            attrs["configuration"] = data.get("configuration")
        age_meta = {
            "cannula_age": ("cage_warning", "cage_critical", "last_cannula_change"),
            "sensor_age": ("sage_warning", "sage_critical", "last_sensor_change"),
            "insulin_age": ("iage_warning", "iage_critical", "last_insulin_change"),
            "battery_age": ("bage_warning", "bage_critical", "last_battery_change"),
        }
        if self.key in age_meta:
            warning_key, critical_key, timestamp_key = age_meta[self.key]
            age = data.get(self.key)
            warning = data.get(warning_key)
            critical = data.get(critical_key)
            attrs.update({"warning_hours": warning, "critical_hours": critical, "last_change": data.get(timestamp_key)})
            if age is None:
                attrs["status"] = "unknown"
            elif critical is not None and age >= critical:
                attrs["status"] = "critical"
            elif warning is not None and age >= warning:
                attrs["status"] = "warning"
            else:
                attrs["status"] = "ok"
        return attrs or None

    async def async_added_to_hass(self):
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id] if entry.entry_id in hass.data.get(DOMAIN, {}) else hass.data["nightscout_extended"][entry.entry_id]
    async_add_entities([
        NightscoutExtendedSensor(coordinator, key, name, unit, device_class, category)
        for key, name, unit, device_class, category in SENSORS
    ])
