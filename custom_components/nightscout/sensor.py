from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity

SPECS = [
    ("bg","Blood Glucose","mg/dL"),("bg_mmol","Blood Glucose","mmol/L"),
    ("delta","BG Delta","mg/dL"),("avg_bg","Average BG","mg/dL"),
    ("avg_bg_mmol","Average BG","mmol/L"),("bg_sd","BG Standard Deviation","mg/dL"),
    ("bg_cv","Glucose CV",PERCENTAGE),("bg_age","Glucose Data Age","s"),
    ("eventual_bg","Eventual BG","mg/dL"),("target_bg","Target BG","mg/dL"),
    ("iob","Insulin on Board","U"),("basaliob","Basal IOB","U"),
    ("activity","Insulin Activity","U/min"),("cob","Carbs on Board","g"),
    ("insulin_req","Insulin Required","U"),("sensitivity_ratio","Sensitivity Ratio",None),
    ("variable_sens","Dynamic Sensitivity","mg/dL/U"),
    ("isf_for_carbs","ISF for Carbs","mg/dL/U"),
    ("dosing_sensitivity_mgdl","Dosing Sensitivity","mg/dL/U"),
    ("isf_mgdl","Current ISF","mg/dL/U"),("cr","Current Carb Ratio","g/U"),
    ("csf","Carb Sensitivity","mg/dL/g"),("profile_sens","Profile Sensitivity","mg/dL/U"),
    ("avg_pred_bg","Average Predicted BG","mg/dL"),("min_pred_mmol","Minimum Predicted BG","mmol/L"),
    ("min_guard_mmol","Minimum Guard BG","mmol/L"),("iob_pred_mmol","Minimum IOB Pred BG","mmol/L"),
    ("naive_eventual_bg","Naive Eventual BG","mg/dL"),
    ("carb_impact","Carb Impact","mg/dL/5m"),("ci_duration","Carb Impact Duration","h"),
    ("uam_impact","UAM Impact","mg/dL/5m"),("uam_duration","UAM Duration","h"),
    ("carbs_required","Carbs Required","g"),
    ("requested_rate","Requested Basal Rate","U/h"),("requested_duration","Requested Duration","min"),
    ("smb","SMB Amount","U"),
    ("reservoir","Pump Reservoir","U"),("pump_battery","Pump Battery",PERCENTAGE),
    ("base_basal","Base Basal Rate","U/h"),("temp_basal_rate","Temp Basal Rate","U/h"),
    ("temp_basal_remaining","Temp Basal Remaining","min"),("last_bolus_amount","Last Bolus Amount","U"),
    ("uploader_battery","AAPS Phone Battery",PERCENTAGE),
    ("insulin_total","Insulin Total","U"),("bolus_total","Bolus Total","U"),
    ("carbs_total","Carbs Total","g"),("tdd_average","Average Daily Insulin","U/day"),
    ("carbs_average","Average Daily Carbs","g/day"),("entries_count","Glucose Entries",None),
    ("treatments_count","Treatments",None),
    ("max_bolus","Max Bolus","U"),("max_carbs","Max Carbs","g"),
    ("low_mark","Low Glucose Mark","mmol/L"),("high_mark","High Glucose Mark","mmol/L"),
    ("res_warning","Reservoir Warning","U"),("res_critical","Reservoir Critical","U"),
    ("pump_bat_warning","Pump Battery Warning",PERCENTAGE),("pump_bat_critical","Pump Battery Critical",PERCENTAGE),
    ("autosens_min","Autosens Minimum",None),("autosens_max","Autosens Maximum",None),
    ("min_carb_impact","Minimum Carb Impact","mg/dL/5m"),("absorption_cutoff","Absorption Cutoff","h"),
    ("dynamic_isf_adjust","Dynamic ISF Adjust",PERCENTAGE),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data["nightscout"][entry.entry_id]
    async_add_entities([NightscoutSensor(c, *spec) for spec in SPECS])


class NightscoutSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name, unit):
        super().__init__(coordinator)
        self.key, self._attr_name = key, name
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = self._icon(key)

    @staticmethod
    def _icon(key):
        if "bg" in key or "glucose" in key: return "mdi:diabetes"
        if "reservoir" in key or "carb" in key: return "mdi:needle"
        if "battery" in key: return "mdi:battery"
        if "bolus" in key or "insulin" in key or "basal" in key: return "mdi:needle"
        return "mdi:chart-line"

    @property
    def native_value(self):
        d = self.coordinator.data
        # Console-derived values.
        if self.key == "isf_mgdl": return d.get("isf_mgdl")
        if self.key == "cr": return d.get("cr")
        if self.key == "csf": return d.get("csf")
        if self.key == "profile_sens": return d.get("profile_sens")
        if self.key == "avg_pred_bg": return d.get("avg_pred_bg")
        if self.key == "min_pred_mmol": return d.get("min_pred_mmol")
        if self.key == "min_guard_mmol": return d.get("min_guard_mmol")
        if self.key == "iob_pred_mmol": return d.get("iob_pred_mmol")
        if self.key == "naive_eventual_bg":
            return d.get("naive_eventual_bg") * 18 if d.get("naive_eventual_bg") is not None else None
        if self.key in ("carb_impact","ci_duration","uam_impact","uam_duration","carbs_required"):
            return d.get(self.key)
        return d.get(self.key)

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        attrs = {
            "nightscout_url": self.coordinator.base_url,
            "pump_status": d.get("pump_status"),
            "active_profile": d.get("active_profile"),
            "algorithm": d.get("algorithm"),
            "dynamic_isf": d.get("dynamic_isf"),
            "pump_type": d.get("pump_type"),
            "aps_type": d.get("aps_type"),
            "aaps_version": d.get("aaps_version"),
            "units": d.get("units"),
        }
        if self.key in ("bg","bg_mmol"):
            attrs.update({
                "direction": d.get("direction"),
                "delta_mgdl": d.get("delta"),
                "eventual_bg_mgdl": d.get("eventual_bg"),
                "target_bg_mgdl": d.get("target_bg"),
                "data_age_seconds": d.get("bg_age"),
            })
        if self.key in ("requested_rate","insulin_req","smb"):
            attrs.update({
                "requested_temp": d.get("requested_temp"),
                "requested_duration": d.get("requested_duration"),
                "delivery_received": d.get("delivery_received"),
                "decision_reason": d.get("reason"),
            })
        if self.key == "bg":
            attrs["prediction_iob"] = d.get("pred_iob")
            attrs["prediction_zt"] = d.get("pred_zt")
        if self.key == "reservoir":
            attrs["estimated_daily_insulin"] = d.get("tdd_average")
        if self.key in ("iob","cob","activity"):
            attrs["eventual_bg_mgdl"] = d.get("eventual_bg")
            attrs["target_bg_mgdl"] = d.get("target_bg")
        return attrs
