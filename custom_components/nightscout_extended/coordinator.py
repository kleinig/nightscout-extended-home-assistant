"""Data coordinator for Nightscout Extended."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from statistics import mean, stdev
from typing import Any

import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_KEY,
    CONF_DEVICESTATUS_COUNT,
    CONF_ENTRIES_COUNT,
    CONF_TREATMENTS_COUNT,
    DEFAULT_DEVICESTATUS_COUNT,
    DEFAULT_ENTRIES_COUNT,
    DEFAULT_TREATMENTS_COUNT,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _num(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value):
    """Return a non-empty string value, or None."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _first_num(*values):
    for value in values:
        n = _num(value)
        if n is not None:
            return n
    return None


def _first(data, *keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _walk(obj, wanted):
    """Find the first scalar key in a nested JSON structure."""
    wanted = {str(x).lower() for x in wanted}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in wanted and not isinstance(v, (dict, list)):
                return v
            found = _walk(v, wanted)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk(item, wanted)
            if found is not None:
                return found
    return None


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # Nightscout milliseconds epoch.
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        # ISO 8601.
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Common pump/AAPS local date strings such as 2/9/26 09:40 pm.
        for fmt in (
            "%d/%m/%y %I:%M %p",
            "%d/%m/%Y %I:%M %p",
            "%m/%d/%y %I:%M %p",
            "%m/%d/%Y %I:%M %p",
        ):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _age_seconds(value):
    dt = _parse_dt(value)
    if not dt:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())


def _parse_log_value(lines, pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    for line in lines or []:
        m = rx.search(str(line))
        if m:
            try:
                return float(m.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _prediction_metrics(pred):
    if not isinstance(pred, dict):
        return {}
    result = {}
    for name, values in pred.items():
        if not isinstance(values, list):
            continue
        nums = [_num(v) for v in values]
        nums = [v for v in nums if v is not None and 20 <= v <= 600]
        if nums:
            result[name] = {
                "min": min(nums),
                "max": max(nums),
                "average": mean(nums),
                "values": nums,
            }
    return result


def _active_profile(profile_json):
    if not isinstance(profile_json, dict):
        return {}
    name = profile_json.get("defaultProfile")
    store = profile_json.get("store", {})
    if name and isinstance(store, dict) and isinstance(store.get(name), dict):
        p = store[name]
        return {"name": name, **p}
    return {}


class NightscoutCoordinator(DataUpdateCoordinator):
    """Fetch and normalize Nightscout endpoints."""

    def __init__(self, hass, config):
        self.url = config["url"].rstrip("/")
        self.api_key = config.get(CONF_API_KEY, "")
        self.entries_count = int(config.get(CONF_ENTRIES_COUNT, DEFAULT_ENTRIES_COUNT))
        self.treatments_count = int(
            config.get(CONF_TREATMENTS_COUNT, DEFAULT_TREATMENTS_COUNT)
        )
        self.devicestatus_count = int(
            config.get(CONF_DEVICESTATUS_COUNT, DEFAULT_DEVICESTATUS_COUNT)
        )
        self.last_raw = {}
        super().__init__(
            hass,
            _LOGGER,
            name="Nightscout Extended",
            update_interval=__import__("datetime").timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _get_json(self, session, path):
        url = f"{self.url}{path}"
        headers = {}
        if self.api_key:
            # Nightscout commonly accepts API-SECRET as the SHA1 API secret.
            headers["API-SECRET"] = self.api_key
        async with session.get(url, headers=headers, timeout=20) as resp:
            if resp.status >= 400:
                raise UpdateFailed(f"{path}: HTTP {resp.status}")
            return await resp.json(content_type=None)

    @staticmethod
    def _latest_aaps(records):
        if not isinstance(records, list):
            return {}
        aaps = [x for x in records if isinstance(x, dict) and str(x.get("app", "")).upper() == "AAPS"]
        return aaps[0] if aaps else (records[0] if records else {})

    @staticmethod
    def _latest_entry(entries):
        if not isinstance(entries, list):
            return {}
        valid = [x for x in entries if isinstance(x, dict) and _num(x.get("sgv")) is not None]
        valid.sort(key=lambda x: _parse_dt(x.get("date") or x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return valid[0] if valid else {}

    @staticmethod
    def _configuration(aaps_records):
        for record in aaps_records if isinstance(aaps_records, list) else []:
            cfg = record.get("configuration")
            if isinstance(cfg, dict) and cfg:
                return cfg
        return {}

    @staticmethod
    def _profile_value(profile, key, default=None):
        arr = profile.get(key)
        if isinstance(arr, list) and arr:
            # For current profile, use the latest time <= now; otherwise first.
            return _num(arr[0].get("value")) if isinstance(arr[0], dict) else default
        return default

    def _normalize(self, status, devicestatus, entries, treatments, profile):
        latest_aaps = self._latest_aaps(devicestatus)
        latest_entry = self._latest_entry(entries)
        cfg = self._configuration(devicestatus)
        aps = cfg.get("apsConfiguration", {}) if isinstance(cfg, dict) else {}
        overview = cfg.get("overviewConfiguration", {}) if isinstance(cfg, dict) else {}
        safety = cfg.get("safetyConfiguration", {}) if isinstance(cfg, dict) else {}
        sensitivity_cfg = cfg.get("sensitivityConfiguration", {}) if isinstance(cfg, dict) else {}

        openaps = latest_aaps.get("openaps", {}) or {}
        suggested = openaps.get("suggested", {}) or {}
        enacted = openaps.get("enacted", {}) or {}
        iob = openaps.get("iob", {}) or {}
        pump = latest_aaps.get("pump", {}) or {}
        extended = pump.get("extended", {}) or {}
        uploader = latest_aaps.get("uploader", {}) or {}

        decision = suggested or enacted
        pred = decision.get("predBGs", {}) or {}
        pred_metrics = _prediction_metrics(pred)
        iob_pred = pred_metrics.get("IOB", {})
        zt_pred = pred_metrics.get("ZT", {})

        # Values specifically emitted in AAPS consoleError are parsed only from
        # the known diagnostic lines, never from arbitrary JSON text.
        console = decision.get("consoleError", []) or []
        naive = _parse_log_value(console, r"naive_eventualBG:\s*([-+]?\d+(?:\.\d+)?)")
        bg_undershoot = _parse_log_value(console, r"bgUndershoot\s+([-+]?\d+(?:\.\d+)?)")
        zero_temp_duration = _parse_log_value(console, r"zeroTempDuration\s+([-+]?\d+(?:\.\d+)?)")
        zero_temp_effect = _parse_log_value(console, r"zeroTempEffect:\s*([-+]?\d+(?:\.\d+)?)")
        carbs_req = _parse_log_value(console, r"carbsReq:\s*([-+]?\d+(?:\.\d+)?)")
        carb_impact = _parse_log_value(console, r"Carb Impact:\s*([-+]?\d+(?:\.\d+)?)")
        carb_duration_h = _parse_log_value(console, r"CI Duration:\s*([-+]?\d+(?:\.\d+)?)")
        uam_impact = _parse_log_value(console, r"UAM Impact:\s*([-+]?\d+(?:\.\d+)?)")
        uam_duration_h = _parse_log_value(console, r"UAM Duration:\s*([-+]?\d+(?:\.\d+)?)")
        csf = _parse_log_value(console, r"CSF:\s*([-+]?\d+(?:\.\d+)?)")
        cr = _parse_log_value(console, r"CR:\s*([-+]?\d+(?:\.\d+)?)")

        # Explicit consoleLog line has all four prediction guard minima.
        min_pred_log = _parse_log_value(decision.get("consoleLog", []), r"minPredBG:\s*([-+]?\d+(?:\.\d+)?)")
        min_iob_log = _parse_log_value(decision.get("consoleLog", []), r"minIOBPredBG:\s*([-+]?\d+(?:\.\d+)?)")
        min_guard_log = _parse_log_value(decision.get("consoleLog", []), r"minZTGuardBG:\s*([-+]?\d+(?:\.\d+)?)")
        min_uam_log = _parse_log_value(decision.get("consoleLog", []), r"minUAMPredBG:\s*([-+]?\d+(?:\.\d+)?)")

        # Prefer structured prediction minima when available, otherwise known AAPS log values.
        min_pred = min(iob_pred["values"]) if iob_pred.get("values") else min_pred_log
        min_iob = min_pred if iob_pred.get("values") else min_iob_log
        min_guard = min_guard_log
        min_uam = min_uam_log

        # Current profile from /profile.json.
        active_profile = _active_profile(profile)
        cr_profile = self._profile_value(active_profile, "carbratio")
        sens_profile = self._profile_value(active_profile, "sens")
        basal_profile = self._profile_value(active_profile, "basal")
        target_low = self._profile_value(active_profile, "target_low")
        target_high = self._profile_value(active_profile, "target_high")

        # Current glucose history statistics.
        recent = []
        now = datetime.now(timezone.utc)
        for e in entries if isinstance(entries, list) else []:
            v = _num(e.get("sgv"))
            dt = _parse_dt(e.get("date") or e.get("created_at"))
            if v is not None and dt and (now - dt.astimezone(timezone.utc)).total_seconds() <= 86400:
                recent.append(v)
        avg_bg = mean(recent) if recent else None
        sd_bg = stdev(recent) if len(recent) >= 2 else None
        cv = (sd_bg / avg_bg * 100) if sd_bg and avg_bg else None

        # TIR based on Nightscout status thresholds.
        thresholds = ((status or {}).get("settings") or {}).get("thresholds") or {}
        low = _num(thresholds.get("bgLow")) or 70
        high = _num(thresholds.get("bgHigh")) or 180
        very_high = 250
        if recent:
            tir = sum(low <= v < high for v in recent) / len(recent) * 100
            tbr = sum(v < low for v in recent) / len(recent) * 100
            tar = sum(v >= high for v in recent) / len(recent) * 100
            tvh = sum(v >= very_high for v in recent) / len(recent) * 100
        else:
            tir = tbr = tar = tvh = None

        treatment_list = treatments if isinstance(treatments, list) else []
        insulin_today = 0.0
        bolus_today = 0.0
        carbs_today = 0.0
        today = now.date()
        for t in treatment_list:
            dt = _parse_dt(t.get("date") or t.get("created_at") or t.get("mills"))
            if not dt or dt.astimezone(timezone.utc).date() != today:
                continue
            insulin = _num(t.get("insulin")) or 0
            carbs = _num(t.get("carbs")) or 0
            insulin_today += insulin
            carbs_today += carbs
            if t.get("eventType") in ("Bolus", "Correction Bolus") or t.get("type") in ("SMB", "Bolus"):
                bolus_today += insulin

        last_bolus = next(
            (t for t in treatment_list if isinstance(t, dict) and _num(t.get("insulin")) is not None and "Bolus" in str(t.get("eventType", ""))),
            None,
        )

        # Build a read-only normalized model.
        bg = _num(latest_entry.get("sgv"))
        direction = latest_entry.get("direction") or "Unknown"
        last_update = latest_entry.get("date") or latest_entry.get("created_at")
        aaps_update = latest_aaps.get("created_at") or decision.get("timestamp")
        pump_clock = pump.get("clock")
        pump_status = (pump.get("status") or {}).get("status")

        return {
            "status": status or {},
            "aaps": latest_aaps,
            "entries": entries or [],
            "treatments": treatments or [],
            "profile": profile or {},
            "active_profile": active_profile,
            "configuration": cfg,
            "bg": bg,
            "bg_mmol": bg / 18.0 if bg is not None else None,
            "direction": direction,
            "delta": _first_num(decision.get("bg") - bg if _num(decision.get("bg")) is not None and bg is not None else None, _num(decision.get("tick"))),
            "glucose_age": _age_seconds(last_update),
            "last_glucose_update": _parse_dt(last_update),
            "aaps_update": _parse_dt(aaps_update),
            "phone_battery": _num(latest_aaps.get("uploaderBattery")),
            "phone_charging": bool(latest_aaps.get("isCharging")),
            "aaps_device": latest_aaps.get("device"),
            "aaps_version": (
                _text(configuration.get("version"))
                or _text(configuration.get("aaps_version"))
                or _text(latest_aaps.get("version"))
                or _walk(latest_aaps, {"version"})
            ),
            "pump_battery": _num((pump.get("battery") or {}).get("percent")),
            "pump_reservoir": _num(pump.get("reservoir")),
            "pump_status": pump_status,
            "pump_connected": pump_status is not None,
            "pump_clock": _parse_dt(pump_clock),
            "pump_firmware": extended.get("Version"),
            "last_bolus_amount": _first_num(extended.get("LastBolusAmount"), last_bolus.get("insulin") if last_bolus else None),
            "last_bolus_time": _parse_dt(extended.get("LastBolus")) or (_parse_dt(last_bolus.get("created_at")) if last_bolus else None),
            "temp_basal_rate": _num(extended.get("TempBasalAbsoluteRate")),
            "temp_basal_start": _parse_dt(extended.get("TempBasalStart")),
            "temp_basal_remaining": _num(extended.get("TempBasalRemaining")),
            "base_basal": _num(extended.get("BaseBasalRate")),
            "profile_basal": basal_profile,
            "profile_cr": cr_profile,
            "profile_sens": (sens_profile * 18.0 if sens_profile is not None and sens_profile < 20 else sens_profile),
            "profile_target_low": target_low,
            "profile_target_high": target_high,
            "iob": _num(iob.get("iob", decision.get("IOB"))),
            "basaliob": _num(iob.get("basaliob")),
            "activity": _num(iob.get("activity")),
            "cob": _num(decision.get("COB")),
            "eventual_bg": _num(decision.get("eventualBG")),
            "target_bg": _num(decision.get("targetBG")),
            "insulin_req": _num(decision.get("insulinReq")),
            "sensitivity_ratio": _num(decision.get("sensitivityRatio")),
            "dynamic_isf": bool(decision.get("runningDynamicIsf")),
            "current_isf": _num(decision.get("variable_sens")),
            "isf_for_carbs": _num(decision.get("isfMgdlForCarbs")),
            "carb_sensitivity": csf,
            "carb_ratio": cr,
            "carb_impact": carb_impact,
            "carb_impact_duration": carb_duration_h * 60 if carb_duration_h is not None else None,
            "uam_impact": uam_impact,
            "uam_duration": uam_duration_h * 60 if uam_duration_h is not None else None,
            "carbs_required": carbs_req,
            "min_pred": min_pred,
            "min_iob_pred": min_iob,
            "min_guard": min_guard,
            "min_uam_pred": min_uam,
            "naive_eventual": naive,
            "bg_undershoot": bg_undershoot,
            "zero_temp_duration": zero_temp_duration,
            "zero_temp_effect": zero_temp_effect,
            "avg_pred": mean(iob_pred["values"]) if iob_pred.get("values") else None,
            "prediction_iob": iob_pred.get("values", []),
            "prediction_zt": zt_pred.get("values", []),
            "decision_algorithm": decision.get("algorithm"),
            "decision_reason": decision.get("reason"),
            "requested_rate": _num((decision.get("requested") or {}).get("rate")),
            "requested_duration": _num((decision.get("requested") or {}).get("duration")),
            "requested_smb": _num((decision.get("requested") or {}).get("smb")),
            "delivery_received": bool(decision.get("received")),
            "smb": _num(decision.get("smb")),
            "active_smb": bool(decision.get("algorithm") == "SMB"),
            "avg_bg": avg_bg,
            "sd_bg": sd_bg,
            "cv": cv,
            "tir": tir,
            "tbr": tbr,
            "tar": tar,
            "very_high": tvh,
            "gmi": (3.31 + 0.02392 * avg_bg) if avg_bg is not None else None,
            "glucose_entries": len(entries) if isinstance(entries, list) else 0,
            "treatments_count": len(treatment_list),
            "insulin_today": insulin_today,
            "bolus_today": bolus_today,
            "carbs_today": carbs_today,
            # Nightscout server settings/configuration.
            "nightscout_version": (status or {}).get("version"),
            "nightscout_units": ((status or {}).get("settings") or {}).get("units"),
            "bg_low_threshold": low,
            "bg_high_threshold": high,
            "bg_target_low": _num(((status or {}).get("settings") or {}).get("thresholds", {}).get("bgTargetBottom")),
            "bg_target_high": _num(((status or {}).get("settings") or {}).get("thresholds", {}).get("bgTargetTop")),
            # AAPS configuration, explicitly from devicestatus.configuration.
            "aaps_low_mark": _num(overview.get("low_mark")),
            "aaps_high_mark": _num(overview.get("high_mark")),
            "aaps_max_bolus": _num(safety.get("max_bolus", safety.get("treatmentssafety_maxbolus"))),
            "aaps_max_carbs": _num(safety.get("max_carbs", safety.get("treatmentssafety_maxcarbs"))),
            "autosens_min": _num(sensitivity_cfg.get("autosens_min")),
            "autosens_max": _num(sensitivity_cfg.get("autosens_max")),
            "carb_absorption_cutoff": _num(sensitivity_cfg.get("absorption_cutoff")),
            "minimum_carb_impact": _num(sensitivity_cfg.get("openaps_smb_min_5m_carbimpact")),
            "dynamic_isf_adjustment": _num(aps.get("DynISFAdjust")),
            "reservoir_warning": _num(overview.get("statuslights_res_warning")),
            "reservoir_critical": _num(overview.get("statuslights_res_critical")),
            "pump_battery_warning": _num(overview.get("statuslights_bat_warning")),
            "pump_battery_critical": _num(overview.get("statuslights_bat_critical")),
            "tir_thresholds": {"low": low, "high": high, "very_high": very_high},
        }

    async def _async_update_data(self):
        try:
            async with aiohttp.ClientSession() as session:
                status, devicestatus, entries, treatments, profile = await __import__("asyncio").gather(
                    self._get_json(session, "/api/v1/status.json"),
                    self._get_json(session, f"/api/v1/devicestatus.json?count={self.devicestatus_count}"),
                    self._get_json(session, f"/api/v1/entries.json?count={self.entries_count}"),
                    self._get_json(session, f"/api/v1/treatments.json?count={self.treatments_count}"),
                    self._get_json(session, "/api/v1/profile.json"),
                )
                self.last_raw = {
                    "status": status,
                    "devicestatus": devicestatus,
                    "entries": entries,
                    "treatments": treatments,
                    "profile": profile,
                }
                return self._normalize(status, devicestatus, entries, treatments, profile)
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch Nightscout data: {err}") from err
