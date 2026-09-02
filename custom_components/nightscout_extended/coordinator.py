from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_ENTRIES_COUNT,
    CONF_URL,
    DEFAULT_ENTRIES_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
)


def _num(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            v = float(value)
            if v > 10_000_000_000:
                v /= 1000
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    value = str(value).strip()
    if not value:
        return None

    for candidate in (value, value.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    for fmt in (
        "%d/%m/%y %I:%M %p",
        "%m/%d/%y %I:%M %p",
        "%d/%m/%Y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
    ):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def _mgdl(value: Any) -> float | None:
    value = _num(value)
    if value is None:
        return None
    return value * 18.0 if abs(value) < 20 else value


def _mmol(value: Any) -> float | None:
    value = _num(value)
    if value is None:
        return None
    return value / 18.0 if abs(value) >= 20 else value


def _walk_for_key(obj: Any, keys: set[str]) -> Any:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and value is not None:
                return value
            found = _walk_for_key(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _walk_for_key(value, keys)
            if found is not None:
                return found
    return None


def _first_number_from_text(text: str | None, label: str) -> float | None:
    if not text:
        return None
    pattern = rf"{re.escape(label)}\s*[:=]\s*(-?\d+(?:\.\d+)?)"
    match = re.search(pattern, text, re.IGNORECASE)
    return _num(match.group(1)) if match else None


def _first_text_from_text(text: str | None, label: str) -> str | None:
    if not text:
        return None
    pattern = rf"{re.escape(label)}\s*[:=]\s*([^,\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _decision(aaps: dict[str, Any]) -> dict[str, Any]:
    openaps = aaps.get("openaps")
    if not isinstance(openaps, dict):
        return {}

    enacted = openaps.get("enacted")
    suggested = openaps.get("suggested")
    enacted = enacted if isinstance(enacted, dict) else {}
    suggested = suggested if isinstance(suggested, dict) else {}

    source = enacted or suggested
    source_name = "enacted" if enacted else ("suggested" if suggested else None)
    requested = source.get("requested")
    requested = requested if isinstance(requested, dict) else {}

    def requested_value(name: str) -> float | None:
        top = _num(source.get(name))
        if top is not None and top >= 0:
            return top
        return _num(requested.get(name))

    pred = source.get("predBGs")
    pred = pred if isinstance(pred, dict) else {}

    return {
        "source": source_name,
        "algorithm": _text(source.get("algorithm")),
        "timestamp": _text(source.get("timestamp")),
        "bg": _mgdl(source.get("bg")),
        "delta": _num(source.get("delta")),
        "eventual_bg": _mgdl(source.get("eventualBG")),
        "target_bg": _mgdl(source.get("targetBG")),
        "insulin_required": _num(source.get("insulinReq")),
        "sensitivity_ratio": _num(source.get("sensitivityRatio")),
        "variable_sens": _num(source.get("variable_sens")),
        "iob": _num(source.get("IOB")),
        "cob": _num(source.get("COB")),
        "rate": requested_value("rate"),
        "duration": requested_value("duration"),
        "smb": requested_value("smb"),
        "requested_temp": _text(requested.get("temp")),
        "reason": _text(source.get("reason")),
        "console_log": _text(source.get("consoleLog")),
        "console_error": _text(source.get("consoleError")),
        "pred_bgs": pred,
    }

class NightscoutExtendedCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.base_url = entry.data[CONF_URL].rstrip("/")
        self.api_key = entry.data.get(CONF_API_KEY, "")
        self.entries_count = int(entry.data.get(CONF_ENTRIES_COUNT, DEFAULT_ENTRIES_COUNT))
        self.session = async_get_clientsession(hass)

        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=NAME,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["API-SECRET"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}{path}"
        try:
            async with self.session.get(url, headers=headers, params=params, timeout=20) as response:
                if response.status in (401, 403):
                    raise UpdateFailed("Nightscout authentication failed")
                if response.status >= 400:
                    raise UpdateFailed(f"Nightscout returned HTTP {response.status}")
                return await response.json(content_type=None)
        except UpdateFailed:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Unable to connect to Nightscout: {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Nightscout returned invalid JSON: {err}") from err

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status, devicestatus, entries, treatments, profile = await __import__("asyncio").gather(
                self._get_json("/api/v1/status.json"),
                self._get_json("/api/v1/devicestatus.json", {"count": 10}),
                self._get_json("/api/v1/entries.json", {"count": self.entries_count}),
                self._get_json("/api/v1/treatments.json", {"count": 1000}),
                self._get_json("/api/v1/profile.json"),
            )
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch Nightscout data: {err}") from err

        if not isinstance(entries, list):
            entries = []
        if not isinstance(devicestatus, list):
            devicestatus = []
        if not isinstance(treatments, list):
            treatments = []
        if not isinstance(profile, dict):
            profile = {}

        entries_sorted = sorted(
            [e for e in entries if isinstance(e, dict)],
            key=lambda e: _parse_dt(e.get("dateString") or e.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        latest_entry = entries_sorted[-1] if entries_sorted else {}
        previous_entry = entries_sorted[-2] if len(entries_sorted) > 1 else {}

        latest_aaps = next(
            (d for d in devicestatus if isinstance(d, dict) and d.get("device") and (
                str(d.get("app", "")).upper() == "AAPS"
                or "openaps" in d
                or "pump" in d
            )),
            {},
        )

        config_record = next(
            (
                d for d in devicestatus
                if isinstance(d, dict)
                and isinstance(d.get("configuration"), dict)
                and bool(d.get("configuration"))
            ),
            {},
        )
        aaps_config = config_record.get("configuration", {}) if isinstance(config_record, dict) else {}

        aps_cfg = aaps_config.get("apsConfiguration", {}) if isinstance(aaps_config, dict) else {}
        overview_cfg = aaps_config.get("overviewConfiguration", {}) if isinstance(aaps_config, dict) else {}
        safety_cfg = aaps_config.get("safetyConfiguration", {}) if isinstance(aaps_config, dict) else {}
        sensitivity_cfg = aaps_config.get("sensitivityConfiguration", {}) if isinstance(aaps_config, dict) else {}

        decision = _decision(latest_aaps)
        pump = latest_aaps.get("pump", {}) if isinstance(latest_aaps.get("pump"), dict) else {}
        pump_ext = pump.get("extended", {}) if isinstance(pump.get("extended"), dict) else {}

        uploader_battery = _num(latest_aaps.get("uploaderBattery"))
        charging = latest_aaps.get("isCharging")

        # Current glucose from entries is authoritative.
        bg = _mgdl(latest_entry.get("sgv") or latest_entry.get("mbg"))
        previous_bg = _mgdl(previous_entry.get("sgv") or previous_entry.get("mbg"))
        delta = None
        if bg is not None and previous_bg is not None:
            delta = bg - previous_bg
        elif decision.get("delta") is not None:
            delta = decision["delta"]

        direction = _text(latest_entry.get("direction"))
        entry_time = _parse_dt(latest_entry.get("dateString") or latest_entry.get("created_at"))

        # Profile.
        default_profile = _text(profile.get("defaultProfile"))
        profiles = profile.get("store", {}) if isinstance(profile.get("store"), dict) else {}
        active_profile = profiles.get(default_profile, {}) if default_profile else {}
        if not isinstance(active_profile, dict):
            active_profile = {}

        profile_sens_raw = _num(active_profile.get("sens"))
        profile_sens = profile_sens_raw * 18.0 if profile_sens_raw is not None and abs(profile_sens_raw) < 20 else profile_sens_raw
        carb_ratio = _num(active_profile.get("carbratio"))
        dia = _num(active_profile.get("dia"))

        target_low = _mmol(
            active_profile.get("target_low")
            if active_profile.get("target_low") is not None
            else active_profile.get("target")
        )
        target_high = _mmol(
            active_profile.get("target_high")
            if active_profile.get("target_high") is not None
            else active_profile.get("target")
        )

        # Prediction arrays. AAPS supplies several distinct prediction series.
        pred = decision.get("pred_bgs") or {}
        pred_values = []
        for key in ("IOB", "ZT", "UAM", "COB", "aCOB"):
            values = pred.get(key)
            if isinstance(values, list):
                for item in values:
                    value = item.get("predBG") if isinstance(item, dict) else item
                    value = _mgdl(value)
                    if value is not None and 20 <= value <= 600:
                        pred_values.append(value)

        average_pred = sum(pred_values) / len(pred_values) if pred_values else None
        minimum_pred = min(pred_values) if pred_values else None

        console = f"{decision.get('console_log') or ''}\n{decision.get('console_error') or ''}"
        min_iob_pred = _first_number_from_text(console, "minIOBPredBG")
        min_guard = _first_number_from_text(console, "minZTGuardBG")
        min_uam = _first_number_from_text(console, "minUAMPredBG")
        naive_eventual = _first_number_from_text(console, "naive_eventualBG")
        bg_undershoot = _first_number_from_text(console, "bgUndershoot")
        carb_impact = _first_number_from_text(console, "Carb Impact")
        carb_impact_duration = _first_number_from_text(console, "CI Duration")
        uam_impact = _first_number_from_text(console, "UAM Impact")
        uam_duration = _first_number_from_text(console, "UAM Duration")
        carbs_required = _first_number_from_text(console, "carbsReq")
        zero_temp_duration = _first_number_from_text(console, "zeroTempDuration")
        zero_temp_effect = _first_number_from_text(console, "zeroTempEffect")
        average_pred_console = _first_number_from_text(console, "avgPredBG")
        if average_pred is None:
            average_pred = average_pred_console

        # TIR statistics based on the AAPS marks when available; otherwise
        # Nightscout status thresholds.
        status_settings = status.get("settings", {}) if isinstance(status, dict) else {}
        thresholds = status_settings.get("thresholds", {}) if isinstance(status_settings, dict) else {}
        low_mark = _mmol(overview_cfg.get("low_mark"))
        high_mark = _mmol(overview_cfg.get("high_mark"))
        if low_mark is None:
            low_mark = _mmol(thresholds.get("bgLow", 70))
        if high_mark is None:
            high_mark = _mmol(thresholds.get("bgHigh", 180))

        values_for_stats = [_mgdl(e.get("sgv")) for e in entries_sorted]
        values_for_stats = [v for v in values_for_stats if v is not None and 20 <= v <= 600]
        avg_bg = sum(values_for_stats) / len(values_for_stats) if values_for_stats else None
        sd = None
        if len(values_for_stats) > 1 and avg_bg is not None:
            sd = (sum((v - avg_bg) ** 2 for v in values_for_stats) / (len(values_for_stats) - 1)) ** 0.5
        cv = (sd / avg_bg * 100) if sd is not None and avg_bg else None

        low_mgdl = low_mark * 18 if low_mark is not None else 70
        high_mgdl = high_mark * 18 if high_mark is not None else 180
        tir = (sum(low_mgdl <= v <= high_mgdl for v in values_for_stats) / len(values_for_stats) * 100) if values_for_stats else None
        tbr = (sum(v < low_mgdl for v in values_for_stats) / len(values_for_stats) * 100) if values_for_stats else None
        tar = (sum(v > high_mgdl for v in values_for_stats) / len(values_for_stats) * 100) if values_for_stats else None
        very_high = (sum(v >= 250 for v in values_for_stats) / len(values_for_stats) * 100) if values_for_stats else None
        gmi = 3.31 + 0.02392 * avg_bg if avg_bg is not None else None

        # Treatment totals in Home Assistant's local timezone.
        local_today = datetime.now().astimezone().date()
        insulin_total = bolus_total = carbs_total = 0.0
        for treatment in treatments:
            if not isinstance(treatment, dict):
                continue
            created = _parse_dt(treatment.get("created_at") or treatment.get("timestamp"))
            if not created or created.astimezone().date() != local_today:
                continue
            insulin = _num(treatment.get("insulin"))
            carbs = _num(treatment.get("carbs"))
            if insulin is not None:
                insulin_total += insulin
            if carbs is not None:
                carbs_total += carbs
            event = str(treatment.get("eventType", "")).lower()
            if insulin is not None and "bolus" in event:
                bolus_total += insulin

        # Current AAPS version: prefer explicit configuration, then top-level AAPS version,
        # never pump firmware.
        aaps_version = (
            _text(aaps_config.get("version"))
            or _text(aaps_config.get("aaps_version"))
            or _text(latest_aaps.get("version"))
        )
        if not aaps_version:
            aaps_version = _walk_for_key(aaps_config, {"version", "aapsVersion"})

        # Pump status / timestamps.
        pump_clock = _parse_dt(pump.get("clock"))
        pump_status_raw = pump.get("status")
        if isinstance(pump_status_raw, dict):
            pump_status = _text(pump_status_raw.get("status"))
        else:
            pump_status = _text(pump_status_raw)
        temp_rate = _num(pump_ext.get("TempBasalAbsoluteRate"))
        temp_remaining = _num(pump_ext.get("TempBasalRemaining"))
        temp_start = _parse_dt(pump_ext.get("TempBasalStart"))
        last_bolus_amount = _num(pump_ext.get("LastBolusAmount"))
        last_bolus_time = _parse_dt(pump_ext.get("LastBolus"))

        # Fall back to treatments for timestamps/amounts when pump formatting is unavailable.
        bolus_treatments = [
            t for t in treatments
            if isinstance(t, dict)
            and _num(t.get("insulin")) is not None
            and "bolus" in str(t.get("eventType", "")).lower()
        ]
        bolus_treatments.sort(
            key=lambda t: _parse_dt(t.get("created_at") or t.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)
        )
        if bolus_treatments:
            latest_bolus = bolus_treatments[-1]
            if last_bolus_amount is None:
                last_bolus_amount = _num(latest_bolus.get("insulin"))
            if last_bolus_time is None:
                last_bolus_time = _parse_dt(latest_bolus.get("created_at") or latest_bolus.get("timestamp"))

        # Configuration keys from the actual AAPS configuration object.
        max_bolus = _num(safety_cfg.get("max_bolus", safety_cfg.get("treatmentssafety_maxbolus")))
        max_carbs = _num(safety_cfg.get("max_carbs", safety_cfg.get("treatmentssafety_maxcarbs")))
        autosens_min = _num(sensitivity_cfg.get("autosens_min"))
        autosens_max = _num(sensitivity_cfg.get("autosens_max"))
        absorption_cutoff = _num(sensitivity_cfg.get("absorption_cutoff"))
        min_carb_impact = _num(sensitivity_cfg.get("min_5m_carbimpact"))
        dyn_isf_adjust = _num(aps_cfg.get("DynISFAdjust"))

        reservoir = _num(pump.get("reservoir"))
        pump_battery = _num(pump.get("battery", {}).get("percent") if isinstance(pump.get("battery"), dict) else pump.get("battery"))
        if pump_battery is None:
            pump_battery = _num(pump_ext.get("battery"))

        # AAPS status flags.
        closed_loop = str(pump.get("status", "")).lower() == "closed loop" or "closed loop" in str(pump.get("status", "")).lower()
        delivery_received = bool(latest_aaps.get("openaps", {}).get("enacted") or latest_aaps.get("openaps", {}).get("suggested"))
        dynamic_isf = bool(aps_cfg.get("use_dynamic_sensitivity"))
        smb_enabled = str(decision.get("algorithm") or "").upper() == "SMB" or bool(decision.get("smb") is not None)

        data = {
            "status": status,
            "devicestatus": latest_aaps,
            "configuration": aaps_config,
            "entries": entries_sorted,
            "treatments": treatments,
            "profile": profile,
            "latest_entry": latest_entry,
            "entry_time": entry_time,
            "previous_entry": previous_entry,
            "bg": bg,
            "delta": delta,
            "direction": direction,
            "average_bg": avg_bg,
            "bg_sd": sd,
            "bg_cv": cv,
            "tir": tir,
            "tbr": tbr,
            "tar": tar,
            "very_high": very_high,
            "gmi": gmi,
            "decision": decision,
            "average_pred": average_pred,
            "minimum_pred": minimum_pred,
            "min_iob_pred": _mgdl(min_iob_pred),
            "min_guard": _mgdl(min_guard),
            "min_uam": _mgdl(min_uam),
            "naive_eventual": _mgdl(naive_eventual),
            "bg_undershoot": bg_undershoot,
            "carb_impact": carb_impact,
            "carb_impact_duration": carb_impact_duration,
            "uam_impact": uam_impact,
            "uam_duration": uam_duration,
            "carbs_required": carbs_required,
            "zero_temp_duration": zero_temp_duration,
            "zero_temp_effect": zero_temp_effect,
            "insulin_total": insulin_total,
            "bolus_total": bolus_total,
            "carbs_total": carbs_total,
            "aaps_version": _text(aaps_version),
            "aaps_device": _text(latest_aaps.get("device")),
            "uploader_battery": uploader_battery,
            "charging": charging,
            "profile_name": default_profile,
            "profile_sens": profile_sens,
            "profile_name": default_profile,
            "dia": dia,
            "carb_ratio": carb_ratio,
            "dia": dia,
            "profile_target_low": target_low,
            "profile_target_high": target_high,
            "pump_status": pump_status,
            "pump_connected": bool(pump),
            "pump_clock": pump_clock,
            "pump_firmware": _text(pump_ext.get("Version")),
            "reservoir": reservoir,
            "pump_battery": pump_battery,
            "base_basal": _num(pump_ext.get("BaseBasalRate")),
            "temp_basal_rate": temp_rate,
            "temp_basal_remaining": temp_remaining,
            "temp_basal_start": temp_start,
            "last_bolus_amount": last_bolus_amount,
            "last_bolus_time": last_bolus_time,
            "iob": _num(decision.get("iob")),
            "cob": _num(decision.get("cob")),
            "eventual_bg": decision.get("eventual_bg"),
            "target_bg": decision.get("target_bg"),
            "insulin_required": decision.get("insulin_required"),
            "sensitivity_ratio": decision.get("sensitivity_ratio"),
            "variable_sens": decision.get("variable_sens"),
            "requested_rate": decision.get("rate"),
            "requested_duration": decision.get("duration"),
            "smb_amount": decision.get("smb"),
            "decision_reason": decision.get("reason"),
            "algorithm": _text(decision.get("algorithm")),
            "closed_loop": closed_loop,
            "delivery_received": delivery_received,
            "dynamic_isf": dynamic_isf,
            "smb_enabled": smb_enabled,
            "low_mark": low_mark,
            "high_mark": high_mark,
            "max_bolus": max_bolus,
            "max_carbs": max_carbs,
            "autosens_min": autosens_min,
            "autosens_max": autosens_max,
            "absorption_cutoff": absorption_cutoff,
            "min_carb_impact": min_carb_impact,
            "dyn_isf_adjust": dyn_isf_adjust,
            "reservoir_warning": _num(overview_cfg.get("statuslights_res_warning", overview_cfg.get("res_warning"))),
            "reservoir_critical": _num(overview_cfg.get("statuslights_res_critical", overview_cfg.get("res_critical"))),
            "pump_battery_warning": _num(overview_cfg.get("statuslights_bat_warning", overview_cfg.get("bat_warning"))),
            "pump_battery_critical": _num(overview_cfg.get("statuslights_bat_critical", overview_cfg.get("bat_critical"))),
            "nightscout_version": _text(status.get("version") if isinstance(status, dict) else None),
            "entry_count": len(entries_sorted),
            "treatment_count": len(treatments),
            "glucose_age": (
                (datetime.now(timezone.utc) - entry_time).total_seconds()
                if entry_time else None
            ),
        }

        return data
