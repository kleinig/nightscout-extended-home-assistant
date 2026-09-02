from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
import statistics

from aiohttp import ClientError
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


def num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def first_number(*values):
    for v in values:
        n = num(v)
        if n is not None:
            return n
    return None


def dt(v):
    if not v:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        except Exception:
            return None
    try:
        x = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def mmol(mgdl):
    return mgdl / 18.0 if mgdl is not None else None


def parse_reason(reason):
    if not isinstance(reason, str):
        return {}
    out = {}
    patterns = {
        "dosing_sensitivity_mgdl": r"Dosing sensitivity:\s*([0-9.]+)",
        "dev_mgdl": r"Dev:\s*([-0-9.]+)",
        "bgi_mgdl": r"BGI:\s*([-0-9.]+)",
        "isf_mgdl": r"ISF:\s*([0-9.]+)",
        "cr": r"CR:\s*([0-9.]+)",
        "target_mmol": r"Target:\s*([0-9.]+)",
        "min_pred_mmol": r"minPredBG\s*([0-9.]+)",
        "min_guard_mmol": r"minGuardBG\s*([0-9.]+)",
        "iob_pred_mmol": r"IOBpredBG\s*([0-9.]+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, reason)
        if m:
            out[key] = float(m.group(1))
    return out


def parse_console(lines):
    out = {}
    if not isinstance(lines, list):
        return out
    text = " ".join(str(x) for x in lines)
    patterns = {
        "autosens_ratio": r"Autosens ratio:\s*([0-9.]+)",
        "adjusted_basal": r"Adjusting basal from [0-9.]+ to ([0-9.]+)",
        "profile_sens": r"profile\.sens:\s*([0-9.]+)",
        "sens": r"profile\.sens:\s*[0-9.]+,\s*sens:\s*([0-9.]+)",
        "csf": r"CSF:\s*([0-9.]+)",
        "carb_impact": r"Carb Impact:\s*([-0-9.]+)",
        "ci_duration": r"CI Duration:\s*([-0-9.]+)",
        "uam_impact": r"UAM Impact:\s*([-0-9.]+)",
        "uam_duration": r"UAM Duration:\s*([-0-9.]+)",
        "avg_pred_bg": r"avgPredBG:\s*([0-9.]+)",
        "naive_eventual_bg": r"naive_eventualBG:\s*([0-9.]+)",
        "bg_undershoot": r"bgUndershoot:\s*([-0-9.]+)",
        "zero_temp_duration": r"zeroTempDuration\s*([0-9.]+)",
        "zero_temp_effect": r"zeroTempEffect:\s*([-0-9.]+)",
        "carbs_required": r"carbsReq:\s*([-0-9.]+)",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if m:
            out[key] = float(m.group(1))
    return out


class NightscoutCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry: ConfigEntry, scan_interval, history_days):
        self.entry = entry
        self.base_url = entry.data["url"].rstrip("/")
        self.history_days = history_days
        self.session = async_get_clientsession(hass)
        super().__init__(
            hass, _LOGGER, name="Nightscout",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def get(self, endpoint, params=None):
        try:
            async with self.session.get(
                f"{self.base_url}{endpoint}", params=params, timeout=20
            ) as r:
                if r.status >= 400:
                    raise UpdateFailed(f"Nightscout HTTP {r.status}")
                return await r.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self):
        count = max(500, self.history_days * 24 * 12 + 100)
        status = await self.get("/api/v1/status.json")
        devs = await self.get("/api/v1/devicestatus.json", {"count": 1})
        entries = await self.get("/api/v1/entries.json", {"count": count})
        treatments = await self.get("/api/v1/treatments.json", {"count": count})
        try:
            profile = await self.get("/api/v1/profile.json")
        except UpdateFailed:
            profile = None

        device = devs[0] if isinstance(devs, list) and devs else {}
        latest = entries[0] if isinstance(entries, list) and entries else {}
        o = device.get("openaps") or {}
        enacted = o.get("enacted") or {}
        suggested = o.get("suggested") or {}
        iob = o.get("iob") or {}
        pump = device.get("pump") or {}
        ext = pump.get("extended") or {}
        pb = pump.get("battery") or {}
        ps = pump.get("status") or {}
        now = datetime.now(timezone.utc)

        source = suggested or enacted
        console = parse_console(source.get("consoleError") or source.get("consoleLog"))
        reason = parse_reason(source.get("reason"))

        bg = num(latest.get("sgv"))
        recent = [num(e.get("sgv")) for e in entries[:288] if num(e.get("sgv")) is not None]
        avg = statistics.mean(recent) if recent else None
        sd = statistics.pstdev(recent) if len(recent) > 1 else None
        cv = (sd / avg * 100) if avg else None

        latest_dt = dt(latest.get("dateString") or latest.get("date") or latest.get("created_at"))
        device_dt = dt(device.get("created_at") or device.get("srvCreated"))

        d = {
            "status": status,
            "latest": latest,
            "entries": entries,
            "treatments": treatments,
            "profile": profile,
            "device": device,
            "pump": pump,
            "bg": bg,
            "bg_mmol": mmol(bg),
            "delta": first_number(latest.get("delta")),
            "direction": latest.get("direction"),
            "bg_age": (now - latest_dt).total_seconds() if latest_dt else None,
            "avg_bg": avg,
            "avg_bg_mmol": mmol(avg),
            "bg_sd": sd,
            "bg_cv": cv,
            "iob": num(iob.get("iob")),
            "basaliob": num(iob.get("basaliob")),
            "activity": num(iob.get("activity")),
            "cob": first_number(source.get("COB"), source.get("cob")),
            "eventual_bg": first_number(source.get("eventualBG"), source.get("eventualBg")),
            "target_bg": first_number(source.get("targetBG"), source.get("targetBg")),
            "insulin_req": num(source.get("insulinReq")),
            "algorithm": source.get("algorithm"),
            "dynamic_isf": source.get("runningDynamicIsf"),
            "sensitivity_ratio": num(source.get("sensitivityRatio")),
            "variable_sens": num(source.get("variable_sens")),
            "isf_for_carbs": num(source.get("isfMgdlForCarbs")),
            "reason": source.get("reason"),
            "requested_rate": num((source.get("requested") or {}).get("rate")),
            "requested_duration": num((source.get("requested") or {}).get("duration")),
            "requested_temp": (source.get("requested") or {}).get("temp"),
            "delivery_received": source.get("received"),
            "smb": num(source.get("smb")),
            "pred_iob": (source.get("predBGs") or {}).get("IOB"),
            "pred_zt": (source.get("predBGs") or {}).get("ZT"),
            "reservoir": num(pump.get("reservoir")),
            "pump_battery": num(pb.get("percent")),
            "pump_status": ps.get("status"),
            "pump_status_timestamp": ps.get("timestamp"),
            "pump_clock": pump.get("clock"),
            "pump_version": ext.get("Version"),
            "active_profile": ext.get("ActiveProfile"),
            "base_basal": num(ext.get("BaseBasalRate")),
            "temp_basal_rate": num(ext.get("TempBasalAbsoluteRate")),
            "temp_basal_remaining": num(ext.get("TempBasalRemaining")),
            "temp_basal_start": ext.get("TempBasalStart"),
            "last_bolus_amount": num(ext.get("LastBolusAmount")),
            "last_bolus": ext.get("LastBolus"),
            "uploader_battery": num(device.get("uploaderBattery")),
            "uploader_charging": bool(device.get("isCharging")),
            "uploader_device": device.get("device"),
            "last_device_update": device_dt,
            "entries_count": len(entries) if isinstance(entries, list) else 0,
            "treatments_count": len(treatments) if isinstance(treatments, list) else 0,
            **console,
            **reason,
        }

        cfg = device.get("configuration") or {}
        overview = cfg.get("overviewConfiguration") or {}
        aps_cfg = cfg.get("apsConfiguration") or {}
        safety = cfg.get("safetyConfiguration") or {}
        sens_cfg = cfg.get("sensitivityConfiguration") or {}

        d.update({
            "pump_type": cfg.get("pump"),
            "aps_type": cfg.get("aps"),
            "aaps_version": cfg.get("version"),
            "units": overview.get("units"),
            "age_profile": safety.get("age"),
            "max_bolus": num(safety.get("treatmentssafety_maxbolus")),
            "max_carbs": num(safety.get("treatmentssafety_maxcarbs")),
            "eatingsoon_duration": num(overview.get("eatingsoon_duration")),
            "eatingsoon_target": num(overview.get("eatingsoon_target")),
            "activity_duration": num(overview.get("activity_duration")),
            "activity_target": num(overview.get("activity_target")),
            "hypo_duration": num(overview.get("hypo_duration")),
            "hypo_target": num(overview.get("hypo_target")),
            "low_mark": num(overview.get("low_mark")),
            "high_mark": num(overview.get("high_mark")),
            "res_warning": num(overview.get("statuslights_res_warning")),
            "res_critical": num(overview.get("statuslights_res_critical")),
            "pump_bat_warning": num(overview.get("statuslights_bat_warning")),
            "pump_bat_critical": num(overview.get("statuslights_bat_critical")),
            "sbat_warning": num(overview.get("statuslights_sbat_warning")),
            "sbat_critical": num(overview.get("statuslights_sbat_critical")),
            "autosens_min": num(sens_cfg.get("autosens_min")),
            "autosens_max": num(sens_cfg.get("autosens_max")),
            "min_carb_impact": num(sens_cfg.get("openaps_smb_min_5m_carbimpact")),
            "absorption_cutoff": num(sens_cfg.get("absorption_cutoff")),
            "dynamic_isf_adjust": num(aps_cfg.get("DynISFAdjust")),
            "smb_always": "enableSMB_always" in " ".join(str(x) for x in (source.get("consoleError") or [])),
            "quickwizard": overview.get("QuickWizard"),
            "smoothing": cfg.get("smoothing"),
        })

        # Treatment-derived totals for the configured history window.
        cutoff = now - timedelta(days=self.history_days)
        insulin = bolus = carbs = 0.0
        treatment_insulin_count = 0
        for t in treatments if isinstance(treatments, list) else []:
            td = dt(t.get("created_at") or t.get("date"))
            if td and td < cutoff:
                continue
            iv = num(t.get("insulin"))
            if iv is not None:
                insulin += iv
                bolus += iv
                treatment_insulin_count += 1
            cvv = num(t.get("carbs"))
            if cvv is not None:
                carbs += cvv

        d["insulin_total"] = insulin
        d["bolus_total"] = bolus
        d["carbs_total"] = carbs
        d["tdd_average"] = insulin / self.history_days
        d["carbs_average"] = carbs / self.history_days
        d["treatment_insulin_count"] = treatment_insulin_count

        # Keep the full prediction curves and latest decision available as attributes.
        d["source_decision"] = source
        d["raw_configuration"] = cfg
        return d
