from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_DEVICE_STATUS,
    API_ENTRIES,
    API_PROFILE,
    API_STATUS,
    API_TREATMENTS,
    CONF_API_SECRET,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(DOMAIN)


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mmol_from_mgdl(value):
    value = safe_float(value)
    return round(value / 18.0, 2) if value is not None else None


def mgdl_from_mmol(value):
    value = safe_float(value)
    return round(value * 18.0, 0) if value is not None else None


def timestamp_from_any(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(
            value / 1000 if value > 10_000_000_000 else value,
            tz=timezone.utc,
        )
    text = str(value).strip()
    # Accept ISO strings, Nightscout date strings and common numeric strings.
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        numeric = float(text)
        return timestamp_from_any(numeric)
    except ValueError:
        return None


def recursive_find(obj, keys):
    if isinstance(obj, dict):
        for key in keys:
            if key in obj and obj[key] not in (None, ""):
                return obj[key]
        for value in obj.values():
            result = recursive_find(value, keys)
            if result not in (None, ""):
                return result
    elif isinstance(obj, list):
        for value in obj:
            result = recursive_find(value, keys)
            if result not in (None, ""):
                return result
    return None


def recursive_version(obj):
    value = recursive_find(
        obj,
        {"version", "appVersion", "aapsVersion", "AAPSVersion"},
    )
    if value:
        return str(value)
    return None


def extract_number(text, pattern):
    if not text:
        return None
    match = re.search(pattern, str(text), re.IGNORECASE)
    return safe_float(match.group(1)) if match else None


def parse_console_text(record):
    chunks = []
    for key in ("consoleLog", "consoleError"):
        value = record.get(key)
        if isinstance(value, list):
            chunks.extend(str(x) for x in value)
        elif value:
            chunks.append(str(value))
    text = "\n".join(chunks)

    def labelled(label):
        return extract_number(
            text,
            rf"\b{re.escape(label)}\b\s*[:=]?\s*(-?\d+(?:\.\d+)?)",
        )

    return {
        "autosens_ratio": extract_number(
            text, r"(?:Autosens ratio|ratio)\s*[:=]?\s*(\d+(?:\.\d+)?)"
        ),
        "current_isf": labelled("sens"),
        "csf": labelled("CSF"),
        "profile_sens": labelled("profile.sens"),
        "carb_impact": labelled("Carb Impact"),
        "carb_impact_duration": labelled("CI Duration"),
        "uam_impact": labelled("UAM Impact"),
        "uam_duration": labelled("UAM Duration"),
        "avg_pred_bg_mmol": labelled("avgPredBG"),
        "min_pred_bg_mmol": labelled("minPredBG"),
        "min_guard_bg_mmol": labelled("minGuardBG"),
        "min_iob_pred_bg_mmol": labelled("minIOBPredBG"),
        "naive_eventual_bg_mmol": labelled("naive_eventualBG"),
        "smb_explicit": bool(
            re.search(r"\bSMB\b.*(?:enabled|bolus|delivery)", text, re.IGNORECASE)
        ),
        "text": text,
    }


def parse_aaps_record(device):
    openaps = device.get("openaps") or {}
    enacted = openaps.get("enacted") or {}
    suggested = openaps.get("suggested") or {}

    merged = {}
    merged.update(suggested)
    merged.update(enacted)

    requested = {}
    requested.update(suggested.get("requested") or {})
    requested.update(enacted.get("requested") or {})

    iob_obj = openaps.get("iob") or {}
    pump = device.get("pump") or {}
    pump_status = pump.get("status")
    if isinstance(pump_status, dict):
        pump_status = pump_status.get("status")

    pump_extended = pump.get("extended") or {}
    console = parse_console_text(enacted or suggested)

    reason = str(merged.get("reason") or "")
    pred = merged.get("predBGs") or {}

    # Some AAPS/Nightscout versions put IOB/COB at different levels.
    iob = safe_float(merged.get("IOB"))
    if iob is None:
        iob = safe_float(iob_obj.get("iob"))

    cob = safe_float(merged.get("COB"))
    if cob is None:
        cob = safe_float(openaps.get("COB"))

    return {
        "raw": device,
        "aaps_version": recursive_version(device),
        "aaps_device": device.get("device"),
        "aaps_timestamp": timestamp_from_any(device.get("created_at")),
        "phone_battery": safe_float(device.get("uploaderBattery")),
        "phone_charging": bool(device.get("isCharging")),
        "algorithm": merged.get("algorithm"),
        "decision_reason": reason or None,
        "decision": classify_decision(merged),
        "bg_mgdl": safe_float(merged.get("bg")),
        "delta_mgdl": safe_float(merged.get("delta")),
        "eventual_bg_mgdl": safe_float(merged.get("eventualBG")),
        "target_mgdl": safe_float(merged.get("targetBG")),
        "insulin_req": safe_float(merged.get("insulinReq")),
        "carbs_req": safe_float(merged.get("carbsReq")),
        "iob": iob,
        "basaliob": safe_float(iob_obj.get("basaliob")),
        "activity": safe_float(iob_obj.get("activity")),
        "cob": cob,
        "sensitivity_ratio": safe_float(merged.get("sensitivityRatio")),
        "isf_mgdl_for_carbs": safe_float(merged.get("isfMgdlForCarbs")),
        "smb": safe_float(merged.get("smb")),
        "smb_enabled": bool(
            merged.get("smb") is not None
            or console["smb_explicit"]
            or str(merged.get("algorithm") or "").upper() == "SMB"
        ),
        "dynamic_isf": bool(
            merged.get("runningDynamicIsf")
            or merged.get("useDynamicSensitivity")
            or merged.get("dynamicIsf")
        ),
        "requested_rate": safe_float(requested.get("rate", merged.get("rate"))),
        "requested_duration": safe_float(
            requested.get("duration", merged.get("duration"))
        ),
        "requested_temp": requested.get("temp", merged.get("temp")),
        "requested_smb": safe_float(requested.get("smb")),
        "delivery_received": bool(merged.get("received") or device.get("received")),
        "pred_bg_iob": pred.get("IOB"),
        "pred_bg_zt": pred.get("ZT"),
        "pred_bg_cob": pred.get("COB"),
        "pred_bg_uam": pred.get("UAM"),
        "console": console,
        "pump_reservoir": safe_float(pump.get("reservoir")),
        "pump_battery": safe_float((pump.get("battery") or {}).get("percent")),
        "pump_status": pump_status,
        "pump_clock": timestamp_from_any(pump.get("clock")),
        "pump_firmware": pump_extended.get("Version"),
        "last_bolus_amount": safe_float(pump_extended.get("LastBolusAmount")),
        "last_bolus_time": timestamp_from_any(pump_extended.get("LastBolus")),
        "base_basal": safe_float(pump_extended.get("BaseBasalRate")),
        "temp_basal_rate": safe_float(pump_extended.get("TempBasalAbsoluteRate")),
        "temp_basal_start": timestamp_from_any(pump_extended.get("TempBasalStart")),
        "temp_basal_remaining": safe_float(pump_extended.get("TempBasalRemaining")),
        "active_profile": pump_extended.get("ActiveProfile"),
        "configuration": device.get("configuration") or {},
    }


def classify_decision(data):
    if not data:
        return "Unknown"
    smb = safe_float(data.get("smb"))
    duration = safe_float(data.get("duration"))
    rate = safe_float(data.get("rate"))
    insulin_req = safe_float(data.get("insulinReq"))

    if smb is not None and smb > 0:
        return "SMB"
    if duration is not None and duration > 0:
        return "Temp basal"
    if rate is not None:
        if insulin_req is not None and insulin_req < 0:
            return "Low / negative insulin request"
        return "Basal"
    return "No action"


def direction_flags(direction):
    d = str(direction or "").lower().replace(" ", "")
    return {
        "rising": "up" in d or "rising" in d,
        "falling": "down" in d or "falling" in d,
        "rapid_rising": d == "doubleup",
        "rapid_falling": d == "doubledown",
    }


def glucose_stats(entries):
    values = [
        safe_float(x.get("sgv"))
        for x in entries
        if safe_float(x.get("sgv")) is not None
    ]
    if not values:
        return {}
    avg = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0
    total = len(values)
    return {
        "count": total,
        "avg": avg,
        "sd": sd,
        "cv": sd / avg * 100 if avg else None,
        "tir": sum(70 <= v <= 180 for v in values) / total * 100,
        "tbr": sum(v < 70 for v in values) / total * 100,
        "tar": sum(v > 180 for v in values) / total * 100,
        "very_high": sum(v > 250 for v in values) / total * 100,
        "gmi": 3.31 + 0.02392 * avg if avg else None,
    }


def treatment_time(t):
    return timestamp_from_any(
        t.get("created_at") or t.get("timestamp") or t.get("date")
    )


def treatment_totals(treatments):
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = [t for t in treatments if (treatment_time(t) or start) >= start]

    insulin = sum(
        safe_float(t.get("insulin")) or 0
        for t in today
        if safe_float(t.get("insulin")) is not None
    )
    carbs = sum(
        safe_float(t.get("carbs")) or 0
        for t in today
        if safe_float(t.get("carbs")) is not None
    )

    last_bolus = next(
        (
            t for t in sorted(
                today, key=lambda x: treatment_time(x) or start, reverse=True
            )
            if (safe_float(t.get("insulin")) or 0) > 0
        ),
        None,
    )
    return {
        "insulin": insulin,
        "carbs": carbs,
        "last_bolus": last_bolus,
    }


class NightscoutCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.base_url = entry.data[CONF_URL].rstrip("/")
        self.secret = entry.data.get(CONF_API_SECRET, "")

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Nightscout Extended {self.base_url}",
            update_interval=timedelta(
                seconds=int(entry.data.get(CONF_SCAN_INTERVAL, 60))
            ),
        )

    async def _request_json(self, session, path, params=None):
        headers = {"API-SECRET": self.secret} if self.secret else {}
        async with session.get(
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=25),
        ) as response:
            if response.status >= 400:
                raise UpdateFailed(f"Nightscout returned HTTP {response.status}")
            return await response.json(content_type=None)

    async def _async_update_data(self):
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                status, devices, entries, treatments, profile = await asyncio.gather(
                    self._request_json(session, API_STATUS),
                    self._request_json(session, API_DEVICE_STATUS, {"count": 5}),
                    self._request_json(session, API_ENTRIES, {"count": 288}),
                    self._request_json(session, API_TREATMENTS, {"count": 200}),
                    self._request_json(session, API_PROFILE),
                )
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        return self._parse(status, devices, entries, treatments, profile)

    def _parse(self, status, devices, entries, treatments, profile):
        if isinstance(devices, dict):
            devices = devices.get("devicestatus", devices.get("devices", []))
        if isinstance(entries, dict):
            entries = entries.get("entries", [])
        if isinstance(treatments, dict):
            treatments = treatments.get("treatments", [])
        if not isinstance(profile, dict):
            profile = {}

        devices = [x for x in devices if isinstance(x, dict)]
        entries = sorted(
            [x for x in entries if isinstance(x, dict)],
            key=lambda x: x.get("date", 0),
            reverse=True,
        )

        aaps_candidates = [
            x for x in devices
            if x.get("openaps") or x.get("pump") or x.get("app") == "AAPS"
        ]
        device = max(
            aaps_candidates or devices or [{}],
            key=lambda x: timestamp_from_any(x.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
        )

        aaps = parse_aaps_record(device)
        stats = glucose_stats(entries)
        totals = treatment_totals(treatments)

        latest = entries[0] if entries else {}
        bg = safe_float(latest.get("sgv"))
        bg_time = timestamp_from_any(latest.get("dateString") or latest.get("date"))
        direction = latest.get("direction") or latest.get("trend")
        delta = safe_float(latest.get("delta"))

        if bg is None:
            bg = aaps["bg_mgdl"]
        if delta is None and len(entries) > 1:
            previous = safe_float(entries[1].get("sgv"))
            if previous is not None and bg is not None:
                delta = bg - previous

        now = datetime.now(timezone.utc)
        age = (now - bg_time).total_seconds() if bg_time else None
        flags = direction_flags(direction)

        cfg = aaps["configuration"]
        low = safe_float(cfg.get("low_mark")) or 4.0
        high = safe_float(cfg.get("high_mark")) or 10.0

        # Extract prediction arrays only when values look like mg/dL.
        arrays = {
            "IOB": aaps["pred_bg_iob"],
            "ZT": aaps["pred_bg_zt"],
            "COB": aaps["pred_bg_cob"],
            "UAM": aaps["pred_bg_uam"],
        }
        valid_prediction_values = [
            safe_float(v)
            for arr in arrays.values()
            if isinstance(arr, list)
            for v in arr
            if safe_float(v) is not None and 20 <= safe_float(v) <= 600
        ]

        console = aaps["console"]
        avg_pred = (
            mean(valid_prediction_values)
            if valid_prediction_values
            else None
        )
        min_pred = min(valid_prediction_values) if valid_prediction_values else None

        last_bolus_time = aaps["last_bolus_time"]
        last_bolus_amount = aaps["last_bolus_amount"]
        if last_bolus_time is None and totals["last_bolus"]:
            last_bolus_time = treatment_time(totals["last_bolus"])
            last_bolus_amount = safe_float(totals["last_bolus"].get("insulin"))

        return {
            "nightscout_version": status.get("version") if isinstance(status, dict) else None,

            "bg_mgdl": bg,
            "bg_mmol": mmol_from_mgdl(bg),
            "bg_time": bg_time,
            "glucose_age": age,
            "direction": direction,
            "delta_mgdl": delta,
            "delta_mmol": mmol_from_mgdl(delta),

            "avg_bg_mgdl": stats.get("avg"),
            "avg_bg_mmol": mmol_from_mgdl(stats.get("avg")),
            "bg_sd_mgdl": stats.get("sd"),
            "bg_cv": stats.get("cv"),
            "tir_percent": stats.get("tir"),
            "tbr_percent": stats.get("tbr"),
            "tar_percent": stats.get("tar"),
            "very_high_percent": stats.get("very_high"),
            "gmi": stats.get("gmi"),
            "glucose_count": stats.get("count", 0),

            "low_mark_mmol": low,
            "high_mark_mmol": high,

            "eventual_bg_mgdl": aaps["eventual_bg_mgdl"],
            "eventual_bg_mmol": mmol_from_mgdl(aaps["eventual_bg_mgdl"]),
            "target_mgdl": aaps["target_mgdl"],
            "target_mmol": mmol_from_mgdl(aaps["target_mgdl"]),

            "iob": aaps["iob"],
            "basaliob": aaps["basaliob"],
            "activity": aaps["activity"],
            "cob": aaps["cob"],
            "insulin_req": aaps["insulin_req"],
            "carbs_req": aaps["carbs_req"],
            "sensitivity_ratio": aaps["sensitivity_ratio"],
            "isf_mgdl_for_carbs": aaps["isf_mgdl_for_carbs"],
            "current_isf": console.get("current_isf"),
            "profile_sens": console.get("profile_sens"),
            "csf": console.get("csf"),
            "carb_impact": console.get("carb_impact"),
            "carb_impact_duration": console.get("carb_impact_duration"),
            "uam_impact": console.get("uam_impact"),
            "uam_duration": console.get("uam_duration"),

            "avg_pred_bg_mgdl": avg_pred,
            "avg_pred_bg_mmol": mmol_from_mgdl(avg_pred),
            "min_pred_bg_mgdl": min_pred,
            "min_pred_bg_mmol": mmol_from_mgdl(min_pred),
            "min_guard_bg_mgdl": None,
            "min_guard_bg_mmol": None,
            "min_iob_pred_bg_mgdl": None,
            "min_iob_pred_bg_mmol": None,
            "naive_eventual_bg_mgdl": None,
            "naive_eventual_bg_mmol": None,

            "algorithm": aaps["algorithm"],
            "decision": aaps["decision"],
            "decision_reason": aaps["decision_reason"],
            "requested_rate": aaps["requested_rate"],
            "requested_duration": aaps["requested_duration"],
            "requested_temp": aaps["requested_temp"],
            "requested_smb": aaps["requested_smb"],
            "smb": aaps["smb"],
            "smb_enabled": aaps["smb_enabled"],
            "dynamic_isf": aaps["dynamic_isf"],
            "delivery_received": aaps["delivery_received"],
            "prediction_arrays": arrays,

            "pump_reservoir": aaps["pump_reservoir"],
            "pump_battery": aaps["pump_battery"],
            "pump_status": aaps["pump_status"],
            "pump_clock": aaps["pump_clock"],
            "pump_firmware": aaps["pump_firmware"],
            "last_bolus_amount": last_bolus_amount,
            "last_bolus_time": last_bolus_time,
            "base_basal": aaps["base_basal"],
            "temp_basal_rate": aaps["temp_basal_rate"],
            "temp_basal_start": aaps["temp_basal_start"],
            "temp_basal_remaining": aaps["temp_basal_remaining"],
            "active_profile": aaps["active_profile"],

            "phone_battery": aaps["phone_battery"],
            "phone_charging": aaps["phone_charging"],
            "aaps_device": aaps["aaps_device"],
            "aaps_version": aaps["aaps_version"],
            "last_aaps_update": aaps["aaps_timestamp"],

            "insulin_total_today": totals["insulin"],
            "bolus_total_today": totals["insulin"],
            "carbs_total_today": totals["carbs"],
            "treatment_count": len(treatments),

            "max_bolus": safe_float(cfg.get("max_bolus")),
            "max_carbs": safe_float(cfg.get("max_carbs")),
            "res_warning": safe_float(cfg.get("res_warning")),
            "res_critical": safe_float(cfg.get("res_critical")),
            "bat_warning": safe_float(cfg.get("bat_warning")),
            "bat_critical": safe_float(cfg.get("bat_critical")),
            "autosens_min": safe_float(cfg.get("autosens_min")),
            "autosens_max": safe_float(cfg.get("autosens_max")),
            "min_carb_impact": safe_float(cfg.get("min_5m_carbimpact")),
            "absorption_cutoff": safe_float(
                cfg.get("absorption_cutoff") or cfg.get("carb_absorption_time")
            ),
            "dynamic_isf_adjust": safe_float(cfg.get("DynISFAdjust")),

            "glucose_rising": flags["rising"],
            "glucose_falling": flags["falling"],
            "glucose_rapid_rising": flags["rapid_rising"],
            "glucose_rapid_falling": flags["rapid_falling"],
        }


async def validate_connection(hass: HomeAssistant, url: str, secret: str):
    connector = aiohttp.TCPConnector(ssl=False)
    headers = {"API-SECRET": secret} if secret else {}
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(
            f"{url.rstrip('/')}{API_STATUS}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            if response.status >= 400:
                raise ValueError(f"HTTP {response.status}")
            await response.read()
