from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timezone
from statistics import mean, pstdev

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
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


def mmol_from_mgdl(value):
    if value is None:
        return None
    return round(float(value) / 18.0, 2)


def mgdl_from_mmol(value):
    if value is None:
        return None
    return round(float(value) * 18.0, 0)


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def timestamp_from_any(value):
    if isinstance(value, (int, float)):
        # Nightscout commonly uses milliseconds.
        return datetime.fromtimestamp(
            value / 1000 if value > 10_000_000_000 else value,
            tz=timezone.utc,
        )
    return parse_iso(value)


def extract_number(text, pattern):
    if not text:
        return None
    match = re.search(pattern, str(text), re.IGNORECASE)
    return safe_float(match.group(1)) if match else None


def extract_mmol(text, label):
    return extract_number(
        text,
        rf"{re.escape(label)}\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*mmol",
    )


def extract_mgdl(text, label):
    return extract_number(
        text,
        rf"{re.escape(label)}\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*mg/dl",
    )


def direction_flags(direction):
    d = str(direction or "").lower()
    return {
        "rising": d in {"singledown", "doubleup", "singleup", "doubleup"}
        or "up" in d
        or "rising" in d,
        "falling": "down" in d or "falling" in d,
        "rapid_rising": d in {"doubleup", "doubleup"},
        "rapid_falling": d in {"doubledown", "doubledown"},
    }


def parse_console_text(record):
    chunks = []
    for key in ("consoleLog", "consoleError"):
        value = record.get(key)
        if isinstance(value, list):
            chunks.extend(str(x) for x in value)
        elif value:
            chunks.append(str(value))
    text = "\n".join(chunks)

    return {
        "autosens_ratio": extract_number(text, r"(?:Autosens ratio|ratio)\s*[:=]?\s*(\d+(?:\.\d+)?)"),
        "current_sens": extract_number(text, r"\bsens\s*[:=]\s*(-?\d+(?:\.\d+)?)"),
        "csf": extract_number(text, r"\bCSF\s*[:=]\s*(-?\d+(?:\.\d+)?)"),
        "profile_sens": extract_number(text, r"profile\.sens\s*[:=]\s*(-?\d+(?:\.\d+)?)"),
        "carb_impact": extract_number(text, r"Carb Impact\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
        "carb_impact_duration": extract_number(text, r"CI Duration\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
        "uam_impact": extract_number(text, r"UAM Impact\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
        "uam_duration": extract_number(text, r"UAM Duration\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
        "avg_pred_bg_mmol": extract_mmol(text, "avgPredBG"),
        "min_pred_bg_mmol": extract_mmol(text, "minPredBG"),
        "min_guard_bg_mmol": extract_mmol(text, "minGuardBG"),
        "min_iob_pred_bg_mmol": extract_mmol(text, "minIOBPredBG"),
        "naive_eventual_bg_mmol": extract_mmol(text, "naive_eventualBG"),
        "smb_explicit": "SMB enabled" in text or "SMB bolus" in text,
        "text": text,
    }


def parse_reason(reason):
    text = str(reason or "")
    return {
        "reason": text,
        "target_mmol": extract_mmol(text, "targetBG"),
        "eventual_bg_mmol": extract_mmol(text, "EventualBG"),
        "insulin_req": extract_number(text, r"insulinReq\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
        "carbs_req": extract_number(text, r"carbsReq\s*[:=]?\s*(-?\d+(?:\.\d+)?)"),
    }


def classify_decision(enacted):
    if not enacted:
        return "Unknown"
    smb = safe_float(enacted.get("smb"))
    requested = enacted.get("requested") or {}
    duration = safe_float(requested.get("duration", enacted.get("duration")))
    rate = safe_float(requested.get("rate", enacted.get("rate")))
    if smb and smb > 0:
        return "SMB"
    if duration is not None and duration > 0:
        return "Temp basal"
    if rate is not None:
        return "Basal / no SMB"
    return "No action"


class NightscoutCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.base_url = entry.data[CONF_URL].rstrip("/")
        self.secret = entry.data.get(CONF_API_SECRET, "")
        self.device_name = "Nightscout"

        super().__init__(
            hass,
            logger=__import__("logging").getLogger(DOMAIN),
            name=f"Nightscout {self.base_url}",
            update_interval=__import__("datetime").timedelta(
                seconds=int(entry.data.get(CONF_SCAN_INTERVAL, 60))
            ),
        )

    async def _request_json(self, session, path, params=None):
        headers = {}
        if self.secret:
            headers["API-SECRET"] = self.secret
        async with session.get(
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20),
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
        if isinstance(entries, dict):
            entries = entries.get("entries", [])
        if isinstance(devices, dict):
            devices = devices.get("devices", devices.get("devicestatus", []))
        if isinstance(treatments, dict):
            treatments = treatments.get("treatments", [])
        if isinstance(profile, dict):
            profiles = profile.get("defaultProfile") or profile
        else:
            profiles = {}

        entries = sorted(
            [x for x in entries if isinstance(x, dict)],
            key=lambda x: x.get("date", 0),
            reverse=True,
        )
        latest = entries[0] if entries else {}

        device = next(
            (x for x in devices if x.get("pump") or x.get("openaps") or x.get("app") == "AAPS"),
            devices[0] if devices else {},
        )
        openaps = device.get("openaps") or {}
        enacted = openaps.get("enacted") or {}
        suggested = openaps.get("suggested") or {}
        pump = device.get("pump") or {}
        pump_ext = pump.get("extended") or {}
        uploader_battery = device.get("uploaderBattery")
        console = parse_console_text(enacted or suggested)
        reason = parse_reason(enacted.get("reason") or suggested.get("reason"))

        bg = safe_float(latest.get("sgv"))
        direction = latest.get("direction") or latest.get("trend")
        bg_time = timestamp_from_any(latest.get("dateString") or latest.get("date"))

        recent_bg = [
            safe_float(x.get("sgv"))
            for x in entries
            if safe_float(x.get("sgv")) is not None
        ]
        recent_bg = recent_bg[:288]
        avg_bg = mean(recent_bg) if recent_bg else None
        sd_bg = pstdev(recent_bg) if len(recent_bg) > 1 else None
        cv = (sd_bg / avg_bg * 100) if avg_bg else None

        low = safe_float(profiles.get("units") and profiles.get("low_mark"))
        high = safe_float(profiles.get("units") and profiles.get("high_mark"))
        # AAPS config is usually in devicestatus; prefer it below.
        config = device.get("configuration") or {}
        status_lights = config.get("statuslights") or {}

        treatment_times = [
            timestamp_from_any(t.get("created_at") or t.get("timestamp"))
            for t in treatments
        ]
        treatment_times = [x for x in treatment_times if x]

        now = datetime.now(timezone.utc)
        recent_24h = [
            t for t in treatments
            if (timestamp_from_any(t.get("created_at") or t.get("timestamp")) or now)
            >= now.replace(hour=0, minute=0, second=0, microsecond=0)
        ]

        bolus_total = sum(
            safe_float(t.get("insulin")) or 0
            for t in recent_24h
            if safe_float(t.get("insulin")) is not None
        )
        carbs_total = sum(
            safe_float(t.get("carbs")) or 0
            for t in recent_24h
            if safe_float(t.get("carbs")) is not None
        )

        daily_insulin = None
        if recent_24h:
            daily_insulin = bolus_total

        flags = direction_flags(direction)
        decision = classify_decision(enacted)

        # Flatten useful AAPS configuration fields from the actual devicestatus snapshot.
        aaps_config = {}
        raw_cfg = device.get("configuration") or {}
        for key in (
            "version", "pump", "insulin", "units", "low_mark", "high_mark",
            "max_bolus", "max_carbs", "use_dynamic_sensitivity",
            "DynISFAdjust", "autosens_min", "autosens_max",
            "min_5m_carbimpact", "carb_absorption_time",
            "res_warning", "res_critical", "bat_warning", "bat_critical",
            "sbat_warning", "sbat_critical", "cage_warning", "cage_critical",
            "iage_warning", "iage_critical", "sage_warning", "sage_critical",
            "bage_warning", "bage_critical",
        ):
            if key in raw_cfg:
                aaps_config[key] = raw_cfg[key]

        return {
            "status": status,
            "status_version": status.get("version") if isinstance(status, dict) else None,
            "status_name": status.get("name") if isinstance(status, dict) else None,
            "latest": latest,
            "entries": entries,
            "treatments": treatments,
            "profile": profiles,
            "device": device,
            "aaps_version": aaps_config.get("version") or device.get("version"),
            "aaps_config": aaps_config,
            "bg_mgdl": bg,
            "bg_mmol": mmol_from_mgdl(bg),
            "bg_time": bg_time,
            "direction": direction,
            "delta_mgdl": safe_float(latest.get("delta")),
            "delta_mmol": mmol_from_mgdl(safe_float(latest.get("delta"))),
            "avg_bg_mgdl": avg_bg,
            "avg_bg_mmol": mmol_from_mgdl(avg_bg),
            "bg_sd_mgdl": sd_bg,
            "bg_cv": cv,
            "glucose_count": len(recent_bg),
            "glucose_age": (now - bg_time).total_seconds() if bg_time else None,
            "eventual_bg_mmol": reason["eventual_bg_mmol"],
            "eventual_bg_mgdl": mgdl_from_mmol(reason["eventual_bg_mmol"]),
            "target_mmol": reason["target_mmol"] or safe_float(enacted.get("targetBG")),
            "target_mgdl": mgdl_from_mmol(reason["target_mmol"] or safe_float(enacted.get("targetBG"))),
            "iob": safe_float(openaps.get("iob", {}).get("iob")),
            "basaliob": safe_float(openaps.get("iob", {}).get("basaliob")),
            "activity": safe_float(openaps.get("iob", {}).get("activity")),
            "cob": safe_float(enacted.get("COB") or suggested.get("COB")),
            "insulin_req": safe_float(enacted.get("insulinReq") or suggested.get("insulinReq")),
            "sensitivity_ratio": safe_float(enacted.get("sensitivityRatio") or suggested.get("sensitivityRatio")),
            "isf_mgdl_for_carbs": safe_float(enacted.get("isfMgdlForCarbs") or suggested.get("isfMgdlForCarbs")),
            "current_isf": console["current_sens"],
            "profile_sens": console["profile_sens"],
            "cr": console["csf"],  # kept as diagnostic parser fallback
            "csf": console["csf"],
            "carb_impact": console["carb_impact"],
            "carb_impact_duration": console["carb_impact_duration"],
            "uam_impact": console["uam_impact"],
            "uam_duration": console["uam_duration"],
            "avg_pred_bg_mmol": console["avg_pred_bg_mmol"],
            "avg_pred_bg_mgdl": mgdl_from_mmol(console["avg_pred_bg_mmol"]),
            "min_pred_bg_mmol": console["min_pred_bg_mmol"],
            "min_pred_bg_mgdl": mgdl_from_mmol(console["min_pred_bg_mmol"]),
            "min_guard_bg_mmol": console["min_guard_bg_mmol"],
            "min_guard_bg_mgdl": mgdl_from_mmol(console["min_guard_bg_mmol"]),
            "min_iob_pred_bg_mmol": console["min_iob_pred_bg_mmol"],
            "min_iob_pred_bg_mgdl": mgdl_from_mmol(console["min_iob_pred_bg_mmol"]),
            "naive_eventual_bg_mmol": console["naive_eventual_bg_mmol"],
            "naive_eventual_bg_mgdl": mgdl_from_mmol(console["naive_eventual_bg_mmol"]),
            "carbs_req": reason["carbs_req"],
            "requested_rate": safe_float((enacted.get("requested") or {}).get("rate", enacted.get("rate"))),
            "requested_duration": safe_float((enacted.get("requested") or {}).get("duration", enacted.get("duration"))),
            "smb": safe_float(enacted.get("smb")),
            "decision": decision,
            "decision_reason": enacted.get("reason") or suggested.get("reason"),
            "algorithm": enacted.get("algorithm") or suggested.get("algorithm"),
            "dynamic_isf": bool(enacted.get("runningDynamicIsf") or suggested.get("runningDynamicIsf")),
            "smb_enabled": console["smb_explicit"],
            "delivery_received": bool(enacted.get("received") or suggested.get("received")),
            "pump_reservoir": safe_float(pump.get("reservoir")),
            "pump_battery": safe_float(pump.get("battery", {}).get("percent")),
            "pump_status": pump.get("status", {}).get("status") if isinstance(pump.get("status"), dict) else pump.get("status"),
            "pump_clock": parse_iso(pump.get("clock")),
            "pump_firmware": pump_ext.get("Version"),
            "last_bolus_amount": safe_float(pump_ext.get("LastBolusAmount")),
            "last_bolus_time": parse_iso(pump_ext.get("LastBolus")),
            "base_basal": safe_float(pump_ext.get("BaseBasalRate")),
            "temp_basal_rate": safe_float(pump_ext.get("TempBasalAbsoluteRate")),
            "temp_basal_start": parse_iso(pump_ext.get("TempBasalStart")),
            "temp_basal_remaining": safe_float(pump_ext.get("TempBasalRemaining")),
            "active_profile": pump_ext.get("ActiveProfile"),
            "phone_battery": safe_float(uploader_battery),
            "phone_charging": bool(device.get("isCharging")),
            "aaps_device": device.get("device"),
            "last_aaps_update": parse_iso(device.get("created_at")),
            "insulin_total_today": daily_insulin,
            "bolus_total_today": bolus_total,
            "carbs_total_today": carbs_total,
            "treatment_count": len(treatments),
            "max_bolus": safe_float(aaps_config.get("max_bolus")),
            "max_carbs": safe_float(aaps_config.get("max_carbs")),
            "low_mark_mmol": safe_float(aaps_config.get("low_mark")),
            "high_mark_mmol": safe_float(aaps_config.get("high_mark")),
            "res_warning": safe_float(aaps_config.get("res_warning")),
            "res_critical": safe_float(aaps_config.get("res_critical")),
            "bat_warning": safe_float(aaps_config.get("bat_warning")),
            "bat_critical": safe_float(aaps_config.get("bat_critical")),
            "autosens_min": safe_float(aaps_config.get("autosens_min")),
            "autosens_max": safe_float(aaps_config.get("autosens_max")),
            "min_carb_impact": safe_float(aaps_config.get("min_5m_carbimpact")),
            "absorption_cutoff": safe_float(aaps_config.get("carb_absorption_time")),
            "dynamic_isf_adjust": safe_float(aaps_config.get("DynISFAdjust")),
            "glucose_rising": flags["rising"],
            "glucose_falling": flags["falling"],
            "glucose_rapid_rising": flags["rapid_rising"],
            "glucose_rapid_falling": flags["rapid_falling"],
        }


async def validate_connection(hass, url, secret):
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
