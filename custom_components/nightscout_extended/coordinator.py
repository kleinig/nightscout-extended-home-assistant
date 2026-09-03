from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import math
import re
from typing import Any
import json
import hashlib
import logging
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp
import socketio
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

def _safe_state_text(value: Any) -> Any:
    """Keep text entity states within Home Assistant's 255-character limit."""
    if isinstance(value, str) and len(value) > 255:
        return value[:252] + "..."
    return value

from .const import (
    CONF_API_KEY,
    CONF_ENTRIES_COUNT,
    CONF_URL,
    DEFAULT_ENTRIES_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME,
)



def _decision_state(decision: dict[str, Any] | None) -> str:
    """Return a short Home Assistant-safe state for the latest AAPS decision."""
    if not decision:
        return "Unknown"

    reason = str(decision.get("reason") or "").lower()

    # Prefer explicit delivery information where available.
    smb = decision.get("smb")
    if smb not in (None, 0, 0.0, "0", "0.0"):
        return "Microbolus"

    # Match common AAPS reason wording without exposing the long reason as state.
    if "no temp required" in reason or "no temp" in reason:
        return "No Temp Required"
    if "temp basal" in reason or "temp" in reason and "basal" in reason:
        return "Temp Basal"
    if "microbolus" in reason or "micro bolus" in reason:
        return "Microbolus"
    if "setting current basal" in reason:
        return "Current Basal"

    # A valid calculation with no explicit delivery wording.
    if decision.get("eventual_bg") is not None or decision.get("bg") is not None:
        return "Calculated"

    return "Unknown"

def _num(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    """Parse common boolean representations without treating 'false' as True."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes", "y", "on", "enabled"}:
        return True
    if text in {"false", "0", "no", "n", "off", "disabled"}:
        return False
    return None


def _normalise_units(value: Any, default: str = "mg/dl") -> str:
    """Normalize Nightscout/AAPS glucose-unit spellings."""
    text = str(value or "").strip().casefold().replace("_", "/")
    if text in {"mmol", "mmol/l", "mmol\u00a0/l"}:
        return "mmol"
    if text in {"mg/dl", "mgdl", "mg/dl."}:
        return "mg/dl"
    return _normalise_units(default, "mg/dl") if default != value else "mg/dl"


def _glucose_to_mgdl(value: Any, units: Any) -> float | None:
    """Convert a glucose concentration from source units to canonical mg/dL."""
    number = _num(value)
    if number is None:
        return None
    return number * 18.0 if _normalise_units(units) == "mmol" else number


def _delta_to_mgdl(value: Any, units: Any) -> float | None:
    """Convert a glucose delta/tick from source units to canonical mg/dL."""
    return _glucose_to_mgdl(value, units)


def _zero_if_none(value: Any) -> float:
    """Return a numeric value, using zero when the source has no value."""
    result = _num(value)
    return 0.0 if result is None else result

def _percent_ratio(value: Any) -> float | None:
    """Convert an AAPS sensitivity ratio (e.g. 0.628) to percent (62.8%)."""
    result = _num(value)
    return result * 100.0 if result is not None else None


def _resolve_temp_basal_rate(
    current_rate: Any, remaining: Any, base_basal: Any, previous_rate: Any = None
) -> float | None:
    """Resolve the displayed temp basal rate.

    While a temp basal has time remaining, retain the last known rate when a
    Socket.IO delta omits the rate. Once the temp basal has expired, report the
    base basal rate instead.
    """
    rate = _num(current_rate)
    remaining_num = _num(remaining)
    base_rate = _num(base_basal)
    previous_num = _num(previous_rate)

    if remaining_num is not None and remaining_num > 0:
        if rate is not None:
            return rate
        if previous_num is not None:
            return previous_num
        return None

    if base_rate is not None:
        return base_rate
    return rate if rate is not None else previous_num


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _parse_dt(value: Any, tzinfo=timezone.utc) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            v = float(value)
            if v > 10_000_000_000:
                v /= 1000
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    else:
        raw = str(value).strip()
        if not raw:
            return None

        dt = None
        for candidate in (raw, raw.replace("Z", "+00:00")):
            try:
                dt = datetime.fromisoformat(candidate)
                break
            except ValueError:
                pass

        if dt is None:
            # AAPS pump strings can be locale-formatted without a timezone.
            for fmt in (
                "%d/%m/%y %I:%M %p",
                "%m/%d/%y %I:%M %p",
                "%d/%m/%Y %I:%M %p",
                "%m/%d/%Y %I:%M %p",
                "%d/%m/%y %H:%M",
                "%m/%d/%y %H:%M",
                "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M",
            ):
                try:
                    dt = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    pass

        if dt is None:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzinfo)
    return dt


# Nightscout entries and AAPS OpenAPS BG values are mg/dL in the supplied API.
# Do NOT use a magnitude heuristic here: deltas can legitimately be -2, +2 etc.
def _stored_profile_tz(data: dict[str, Any] | None) -> Any:
    """Return the Nightscout profile timezone stored in coordinator data."""
    if not isinstance(data, dict):
        return timezone.utc
    name = data.get("profile_timezone")
    if name:
        try:
            return ZoneInfo(str(name))
        except Exception:
            pass
    return data.get("profile_tz") or timezone.utc


def _profile_timezone_name(profile_tz: Any) -> str:
    """Return a stable IANA timezone name for diagnostic exposure."""
    return getattr(profile_tz, "key", None) or str(profile_tz) or "UTC"


def _mgdl(value: Any) -> float | None:
    return _num(value)


def _mgdl_to_mmol(value: Any) -> float | None:
    value = _num(value)
    return value / 18.0 if value is not None else None


def _schedule_value(value: Any, now_local: datetime) -> float | None:
    """Return the active value from a Nightscout timed schedule."""
    if isinstance(value, (int, float)):
        return _num(value)

    if isinstance(value, str):
        # Some Nightscout profiles may contain a scalar as a string.
        scalar = _num(value)
        if scalar is not None:
            return scalar

    if not isinstance(value, list):
        return None

    parsed: list[tuple[int, float]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        val = _num(item.get("value"))
        raw_time = item.get("time") or item.get("start")
        if val is None or not isinstance(raw_time, str):
            continue

        match = re.match(r"^\s*(\d{1,2}):(\d{2})", raw_time)
        if not match:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            parsed.append((hour * 60 + minute, val))

    if not parsed:
        return None

    parsed.sort()
    now_minutes = now_local.hour * 60 + now_local.minute
    eligible = [item for item in parsed if item[0] <= now_minutes]
    return max(eligible, key=lambda item: item[0])[1] if eligible else parsed[-1][1]


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


def _first_num(*values):
    """Return the first value that can be converted to a number."""
    for value in values:
        parsed = _num(value)
        if parsed is not None:
            return parsed
    return None


def _has_openaps_data(record: Any) -> bool:
    """Return True when a devicestatus record contains substantive OpenAPS data."""
    if not isinstance(record, dict):
        return False
    openaps = record.get("openaps")
    if not isinstance(openaps, dict):
        return False
    return any(
        isinstance(openaps.get(key), dict) and bool(openaps.get(key))
        for key in ("suggested", "enacted", "iob")
    )


def _decision(aaps: dict[str, Any]) -> dict[str, Any]:
    openaps = aaps.get("openaps")
    if not isinstance(openaps, dict):
        return {}

    enacted = openaps.get("enacted")
    suggested = openaps.get("suggested")
    enacted = enacted if isinstance(enacted, dict) else {}
    suggested = suggested if isinstance(suggested, dict) else {}

    # The current AAPS recommendation is the suggested record. Enacted is a
    # separate historical/delivery record and should not silently replace it.
    source = suggested or enacted
    source_name = "suggested" if suggested else ("enacted" if enacted else None)

    requested = source.get("requested")
    requested = requested if isinstance(requested, dict) else {}

    def requested_number(name: str) -> float | None:
        value = _num(requested.get(name))
        if value is not None and value >= 0:
            return value
        value = _num(source.get(name))
        return value if value is None or value >= 0 else None

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
        "sensitivity_ratio": _percent_ratio(source.get("sensitivityRatio")),
        "variable_sens": _num(source.get("variable_sens")),
        "iob": _num(source.get("IOB")),
        "cob": _num(source.get("COB")),
        "snooze_bg": _mgdl(source.get("snoozeBG")),
        "tick": _num(source.get("tick")),
        "temp": _text(source.get("temp")),
        "reservoir": _num(source.get("reservoir")),
        "deliver_at": _parse_dt(source.get("deliverAt")),
        "rate": requested_number("rate"),
        "duration": requested_number("duration"),
        "smb": requested_number("smb"),
        "received": source.get("received", source.get("recieved")),
        "reason": _text(source.get("reason")),
        "console_log": _text(source.get("consoleLog")),
        "console_error": _text(source.get("consoleError")),
        "pred_bgs": pred,
    }


EVENT_TYPE_MAP = {
    "site change": "cannula",
    "sensor change": "sensor",
    "sensor start": "sensor",
    "insulin change": "insulin",
    "pump battery change": "battery",
    "battery change": "battery",
}


def _normalise_event_type(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _event_datetime(event: dict[str, Any]) -> datetime | None:
    for key in ("created_at", "timestamp", "date"):
        value = event.get(key)
        if value is None:
            continue
        parsed = _parse_dt(value)
        if parsed is not None:
            return parsed
    return None


def _extract_change_events(payload: Any) -> dict[str, dict[str, Any]]:
    """Extract latest valid device-change events from a Socket.IO payload."""
    found: dict[str, dict[str, Any]] = {}

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("eventType") is not None:
                event_type = EVENT_TYPE_MAP.get(_normalise_event_type(value.get("eventType")))
                if event_type and value.get("isValid") is not False:
                    when = _event_datetime(value)
                    if when is not None:
                        previous = found.get(event_type)
                        if previous is None or when > previous["timestamp"]:
                            found[event_type] = {
                                "timestamp": when,
                                "event_type": str(value.get("eventType")),
                            }
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return found


class NightscoutExtendedCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.base_url = entry.data[CONF_URL].rstrip("/")
        self.api_key = entry.data.get(CONF_API_KEY, "")
        self.entries_count = int(
            entry.data.get(CONF_ENTRIES_COUNT, DEFAULT_ENTRIES_COUNT)
        )
        self.glucose_unit = entry.options.get("glucose_unit", "mmol/L")
        self.isf_unit = entry.options.get("isf_unit", "mmol/L/U")
        self.session = async_get_clientsession(hass)
        self._change_events: dict[str, dict[str, Any]] = {}
        self._socket_task: asyncio.Task | None = None
        self._socket_connected = False
        self._socket_last_error: str | None = None
        self._socket_stop = asyncio.Event()
        self._socket_client = socketio.AsyncClient(
            reconnection=False,
            logger=False,
            engineio_logger=False,
        )
        self._socket_alarm_subscribed = False
        self._register_socket_handlers()

        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=NAME,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _socket_auth(self) -> tuple[str | None, str | None]:
        """Return the Socket.IO auth values expected by Nightscout.

        Nightscout's web client sends a SHA-1 API-secret hash in ``secret``.
        JWTs are sent as ``token`` instead. This mirrors the captured web
        client behaviour.
        """
        value = (self.api_key or "").strip()
        if not value:
            return None, None
        if value.count(".") == 2:
            return None, value
        return hashlib.sha1(value.encode("utf-8")).hexdigest(), None

    def _register_socket_handlers(self) -> None:
        @self._socket_client.event
        async def connect():
            self._socket_connected = True
            self._socket_last_error = None
            _LOGGER.info("Nightscout Socket.IO connected")
            if not self.data:
                self.async_set_updated_data({})

        @self._socket_client.event
        async def disconnect():
            self._socket_connected = False
            self._socket_alarm_subscribed = False
            _LOGGER.debug("Nightscout Socket.IO disconnected; reconnect loop will retry")

        @self._socket_client.on("connected", namespace="/")
        async def connected_event(*args):
            self._socket_connected = True

        @self._socket_client.on("dataUpdate", namespace="/")
        async def data_update(payload=None):
            if isinstance(payload, dict):
                self._apply_socket_payload(payload)

        @self._socket_client.on("retroUpdate", namespace="/")
        async def retro_update(payload=None):
            if isinstance(payload, dict):
                self._apply_socket_payload(payload)

        @self._socket_client.on("connect", namespace="/alarm")
        async def alarm_connect():
            secret, token = self._socket_auth()
            try:
                result = await self._socket_client.call(
                    "subscribe",
                    {"secret": secret, "jwtToken": token},
                    namespace="/alarm",
                    timeout=15,
                )
                self._socket_alarm_subscribed = bool(
                    isinstance(result, dict) and result.get("success")
                )
                _LOGGER.debug("Nightscout alarm subscription: %s", result)
            except Exception as err:
                _LOGGER.warning("Nightscout alarm subscription failed: %s", err)

        @self._socket_client.on("notification", namespace="/alarm")
        async def alarm_notification(payload=None):
            if not isinstance(payload, dict) or not self.data:
                return
            self.data["last_alarm"] = payload
            self.data["last_alarm_title"] = _text(payload.get("title"))
            self.data["last_alarm_message"] = _text(payload.get("message"))
            self.data["last_alarm_level"] = payload.get("level")
            self.async_set_updated_data(self.data)

    def _apply_socket_payload(self, payload: dict[str, Any]) -> None:
        """Apply live Socket.IO records to the cached HA data."""
        if not isinstance(self.data, dict):
            return

        profile_tz = _stored_profile_tz(self.data)
        self.data["socket_last_update"] = _parse_dt(payload.get("lastUpdated"), profile_tz)
        self.data["socket_last_event"] = "dataUpdate"

        # Glucose records: retain a bounded history for delta and live values.
        entries = self.data.setdefault("entries", [])
        if not isinstance(entries, list):
            entries = []
            self.data["entries"] = entries
        by_id = {str(x.get("_id")): x for x in entries if isinstance(x, dict) and x.get("_id")}
        for item in payload.get("sgvs") or []:
            if isinstance(item, dict):
                key = str(item.get("_id") or item.get("mills") or item.get("date"))
                if key:
                    by_id[key] = item
        merged_entries = list(by_id.values())
        merged_entries.sort(key=lambda x: _parse_dt(x.get("dateString") or x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
        self.data["entries"] = merged_entries[-max(self.entries_count, 288):]
        latest_entry = self.data["entries"][-1] if self.data["entries"] else {}
        previous_entry = self.data["entries"][-2] if len(self.data["entries"]) > 1 else {}
        bg = _mgdl(latest_entry.get("mgdl") or latest_entry.get("sgv"))
        previous_bg = _mgdl(previous_entry.get("mgdl") or previous_entry.get("sgv"))
        self.data["bg"] = bg
        self.data["delta"] = (
            bg - previous_bg if bg is not None and previous_bg is not None else self.data.get("delta")
        )
        self.data["direction"] = _text(latest_entry.get("direction")) or self.data.get("direction")
        self.data["latest_entry"] = latest_entry
        self.data["entry_time"] = _parse_dt(latest_entry.get("dateString") or latest_entry.get("created_at"))
        if self.data["entry_time"]:
            self.data["glucose_age"] = max(0.0, (datetime.now(timezone.utc) - self.data["entry_time"]).total_seconds())

        # AAPS device status is the live source for loop/pump values.
        statuses = self.data.setdefault("devicestatus_records", [])
        if not isinstance(statuses, list):
            statuses = []
            self.data["devicestatus_records"] = statuses
        by_id = {str(x.get("_id")): x for x in statuses if isinstance(x, dict) and x.get("_id")}
        for item in payload.get("devicestatus") or []:
            if isinstance(item, dict):
                key = str(item.get("_id") or item.get("mills") or item.get("date"))
                if key:
                    by_id[key] = item
        statuses = list(by_id.values())
        statuses.sort(key=lambda x: _parse_dt(x.get("date") or x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
        self.data["devicestatus_records"] = statuses[-100:]
        aaps_records = [
            x for x in statuses
            if isinstance(x, dict)
            and (str(x.get("app", "")).upper() == "AAPS" or "aaps" in str(x.get("device", "")).lower())
            and _has_openaps_data(x)
        ]
        if not aaps_records:
            aaps_records = [x for x in statuses if _has_openaps_data(x)]
        if aaps_records:
            sort_key = lambda x: _parse_dt(x.get("date") or x.get("created_at"), profile_tz) or datetime.min.replace(tzinfo=timezone.utc)
            latest_aaps = max(aaps_records, key=sort_key)
            suggested_records = [x for x in aaps_records if isinstance(x.get("openaps", {}).get("suggested"), dict)]
            enacted_records = [x for x in aaps_records if isinstance(x.get("openaps", {}).get("enacted"), dict)]
            latest_suggested_record = max(suggested_records, key=sort_key) if suggested_records else latest_aaps
            latest_enacted_record = max(enacted_records, key=sort_key) if enacted_records else latest_aaps
            self.data["devicestatus"] = latest_aaps
            decision = _decision(latest_suggested_record if latest_suggested_record is not latest_aaps else latest_aaps)
            self.data["decision"] = decision
            suggested_openaps = latest_suggested_record.get("openaps", {}) if isinstance(latest_suggested_record.get("openaps"), dict) else {}
            enacted_openaps = latest_enacted_record.get("openaps", {}) if isinstance(latest_enacted_record.get("openaps"), dict) else {}
            suggested = suggested_openaps.get("suggested", {}) if isinstance(suggested_openaps.get("suggested"), dict) else {}
            enacted = enacted_openaps.get("enacted", {}) if isinstance(enacted_openaps.get("enacted"), dict) else {}
            latest_openaps = latest_aaps.get("openaps", {}) if isinstance(latest_aaps.get("openaps"), dict) else {}
            iob_openaps = suggested_openaps if suggested_openaps.get("iob") is not None else latest_openaps
            iob_record = iob_openaps.get("iob", {})
            if isinstance(iob_record, list):
                iob_record = iob_record[0] if iob_record else {}
            if not isinstance(iob_record, dict):
                iob_record = {}
            suggested_units = _first_num(suggested.get("units"))
            enacted_units = _first_num(enacted.get("units"))
            self.data.update({
                "suggested_bg": _mgdl(suggested.get("bg")),
                "suggested_snooze_bg": _mgdl(suggested.get("snoozeBG")),
                "suggested_tick": _num(suggested.get("tick")),
                "suggested_temp": _text(suggested.get("temp")),
                "suggested_min_pred_bg": _mgdl(suggested.get("minPredBG")),
                "suggested_rate": _num(suggested.get("rate")),
                "suggested_duration": _num(suggested.get("duration")),
                "suggested_deliver_at": _parse_dt(suggested.get("deliverAt"), profile_tz),
                "suggested_timestamp": _parse_dt(suggested.get("timestamp"), profile_tz),
                "suggested_insulin_required": _num(suggested.get("insulinReq")),
                "suggested_target_bg": _mgdl(suggested.get("targetBG")),
                "suggested_sensitivity_ratio": _percent_ratio(suggested.get("sensitivityRatio")),
                "suggested_variable_sens": _num(suggested.get("variable_sens")),
                "suggested_algorithm": _text(suggested.get("algorithm")),
                "suggested_running_dynamic_isf": suggested.get("runningDynamicIsf"),
                "suggested_reservoir": _num(suggested.get("reservoir")),
                "suggested_smb": _num(suggested.get("smb")),
                "suggested_units": _zero_if_none(suggested_units),
                "suggested_received": suggested.get("received", suggested.get("recieved")),
                "suggested_pred_bgs": suggested.get("predBGs") if isinstance(suggested.get("predBGs"), dict) else {},
                "enacted_bg": _mgdl(enacted.get("bg")),
                "enacted_snooze_bg": _mgdl(enacted.get("snoozeBG")),
                "enacted_tick": _num(enacted.get("tick")),
                "enacted_temp": _text(enacted.get("temp")),
                "enacted_min_pred_bg": _mgdl(enacted.get("minPredBG")),
                "enacted_rate": _num(enacted.get("rate")),
                "enacted_duration": _num(enacted.get("duration")),
                "enacted_deliver_at": _parse_dt(enacted.get("deliverAt"), profile_tz),
                "enacted_timestamp": _parse_dt(enacted.get("timestamp"), profile_tz),
                "enacted_insulin_required": _num(enacted.get("insulinReq")),
                "enacted_target_bg": _mgdl(enacted.get("targetBG")),
                "enacted_sensitivity_ratio": _percent_ratio(enacted.get("sensitivityRatio")),
                "enacted_units": _zero_if_none(enacted_units),
                "enacted_meal_assist": enacted.get("mealAssist"),
                "enacted_variable_sens": _num(enacted.get("variable_sens")),
                "enacted_received": enacted.get("received", enacted.get("recieved")),
                "enacted_pred_bgs": enacted.get("predBGs") if isinstance(enacted.get("predBGs"), dict) else {},
                "iob": _num(iob_record.get("iob")) if _num(iob_record.get("iob")) is not None else decision.get("iob"),
                "basal_iob": _num(iob_record.get("basaliob")),
                "bolus_iob": _num(iob_record.get("bolusiob")),
                "insulin_activity": _num(iob_record.get("activity")),
                "bolus_snooze": _num(iob_record.get("bolussnooze")),
                "net_basal_insulin": _num(iob_record.get("netbasalinsulin")),
                "high_temp_insulin": _num(iob_record.get("hightempinsulin")),
                "microbolus_insulin": _num(iob_record.get("microBolusInsulin")),
                "microbolus_iob": _num(iob_record.get("microBolusIOB")),
                "iob_last_bolus_time": _parse_dt(iob_record.get("lastBolusTime"), profile_tz),
                "iob_timestamp": _parse_dt(iob_record.get("timestamp") or iob_record.get("time"), profile_tz),
            })
            for target, source in {
                "snooze_bg": "snooze_bg",
                "aaps_tick": "tick",
                "aaps_temp": "temp",
                "aaps_reservoir": "reservoir",
                "aaps_delivery_time": "deliver_at",
                "aaps_suggestion_time": "timestamp",
                "iob": "iob", "cob": "cob", "eventual_bg": "eventual_bg",
                "target_bg": "target_bg", "insulin_required": "insulin_required",
                "sensitivity_ratio": "sensitivity_ratio", "variable_sens": "variable_sens",
                "requested_rate": "rate", "requested_duration": "duration", "smb_amount": "smb",
            }.items():
                value = decision.get(source)
                if target in {"aaps_delivery_time", "aaps_suggestion_time"}:
                    value = _parse_dt(value)
                self.data[target] = value
            self.data["algorithm"] = _text(decision.get("algorithm"))
            self.data["decision_reason"] = decision.get("reason")
            self.data["decision_state"] = _decision_state(decision)
            dynamic_value = latest_aaps.get("configuration", {}).get("apsConfiguration", {}).get("use_dynamic_sensitivity")
            parsed_dynamic = _bool(dynamic_value)
            if parsed_dynamic is not None:
                self.data["dynamic_isf"] = parsed_dynamic
            parsed_received = _bool(decision.get("received"))
            if parsed_received is not None:
                self.data["delivery_received"] = parsed_received
            self.data["aaps_device"] = _text(latest_aaps.get("device")) or self.data.get("aaps_device")

            # Uploader/phone data is not guaranteed to be present on the same
            # devicestatus record as OpenAPS data. Search all recent status
            # records so uploaderBattery cannot disappear just because the
            # latest OpenAPS delta omitted it. Support both the normalized
            # uploader object and the legacy uploaderBattery field.
            uploader_records = [
                x for x in statuses
                if isinstance(x, dict)
                and (
                    isinstance(x.get("uploader"), dict)
                    or x.get("uploaderBattery") is not None
                    or x.get("isCharging") is not None
                )
            ]
            if uploader_records:
                uploader_records.sort(key=sort_key, reverse=True)
                for record in uploader_records:
                    uploader_data = record.get("uploader") if isinstance(record.get("uploader"), dict) else {}
                    if uploader_data.get("battery") is not None:
                        self.data["uploader_battery"] = _num(uploader_data.get("battery"))
                    elif record.get("uploaderBattery") is not None:
                        self.data["uploader_battery"] = _num(record.get("uploaderBattery"))
                    if uploader_data.get("batteryVoltage") is not None:
                        self.data["uploader_battery_voltage"] = _num(uploader_data.get("batteryVoltage"))
                    if record.get("isCharging") is not None:
                        parsed_charging = _bool(record.get("isCharging"))
                        if parsed_charging is not None:
                            self.data["charging"] = parsed_charging
                    if (
                        self.data.get("uploader_battery") is not None
                        and self.data.get("uploader_battery_voltage") is not None
                        and self.data.get("charging") is not None
                    ):
                        break

            pump = latest_aaps.get("pump") if isinstance(latest_aaps.get("pump"), dict) else {}
            ext = pump.get("extended") if isinstance(pump.get("extended"), dict) else {}
            self.data["pump_status"] = _text(pump.get("status")) if not isinstance(pump.get("status"), dict) else _text(pump.get("status", {}).get("status"))
            pump_status_value = self.data.get("pump_status")
            pump_status_time = self.data.get("pump_status_timestamp")
            pump_clock_value = self.data.get("pump_clock")
            now_utc = datetime.now(timezone.utc)
            recent_status = (
                isinstance(pump_status_time, datetime)
                and abs((now_utc - pump_status_time.astimezone(timezone.utc)).total_seconds()) <= 1800
            )
            recent_clock = (
                isinstance(pump_clock_value, datetime)
                and abs((now_utc - pump_clock_value.astimezone(timezone.utc)).total_seconds()) <= 1800
            )
            self.data["pump_connected"] = bool(pump and (recent_status or recent_clock or pump_status_value))
            self.data["pump_firmware"] = _text(ext.get("Version")) or self.data.get("pump_firmware")
            self.data["pump_active_profile"] = _text(ext.get("ActiveProfile")) or self.data.get("pump_active_profile")
            self.data["pump_battery_status"] = _text(pump.get("battery", {}).get("status")) if isinstance(pump.get("battery"), dict) else self.data.get("pump_battery_status")
            self.data["pump_battery_voltage"] = _num(pump.get("battery", {}).get("voltage")) if isinstance(pump.get("battery"), dict) else self.data.get("pump_battery_voltage")
            parsed_bolusing = _bool(pump.get("status", {}).get("bolusing")) if isinstance(pump.get("status"), dict) else None
            if parsed_bolusing is not None:
                self.data["pump_bolusing"] = parsed_bolusing
            parsed_suspended = _bool(pump.get("status", {}).get("suspended")) if isinstance(pump.get("status"), dict) else None
            if parsed_suspended is not None:
                self.data["pump_suspended"] = parsed_suspended
            self.data["pump_status_timestamp"] = _parse_dt(pump.get("status", {}).get("timestamp"), profile_tz) if isinstance(pump.get("status"), dict) else self.data.get("pump_status_timestamp")
            self.data["reservoir"] = _num(ext.get("Reservoir")) if ext.get("Reservoir") is not None else (_num(pump.get("reservoir")) if pump.get("reservoir") is not None else self.data.get("reservoir"))
            self.data["pump_battery"] = (_num(pump.get("battery", {}).get("percent")) if isinstance(pump.get("battery"), dict) and pump.get("battery", {}).get("percent") is not None else (_num(pump.get("battery")) if pump.get("battery") is not None else self.data.get("pump_battery")))
            socket_base_basal = _num(ext.get("BaseBasalRate"))
            socket_temp_remaining = _num(ext.get("TempBasalRemaining"))
            if socket_temp_remaining is None:
                socket_temp_remaining = _num(self.data.get("temp_basal_remaining"))
            socket_temp_rate = _resolve_temp_basal_rate(
                ext.get("TempBasalAbsoluteRate"),
                socket_temp_remaining,
                socket_base_basal if socket_base_basal is not None else self.data.get("base_basal"),
                self.data.get("temp_basal_rate"),
            )
            self.data["base_basal"] = socket_base_basal if socket_base_basal is not None else self.data.get("base_basal")
            self.data["temp_basal_rate"] = socket_temp_rate
            self.data["temp_basal_remaining"] = socket_temp_remaining if socket_temp_remaining is not None else self.data.get("temp_basal_remaining")
            self.data["temp_basal_start"] = _parse_dt(ext.get("TempBasalStart"), profile_tz) or self.data.get("temp_basal_start")
            self.data["last_bolus_amount"] = _num(ext.get("LastBolusAmount")) if ext.get("LastBolusAmount") is not None else self.data.get("last_bolus_amount")
            self.data["last_bolus_time"] = _parse_dt(ext.get("LastBolus"), profile_tz) or self.data.get("last_bolus_time")
            self.data["pump_clock"] = _parse_dt(pump.get("clock"), profile_tz) or self.data.get("pump_clock")

        # Treatments are authoritative for age pills and last treatment.
        treatments = self.data.setdefault("treatments", [])
        if not isinstance(treatments, list):
            treatments = []
        by_id = {str(x.get("_id")): x for x in treatments if isinstance(x, dict) and x.get("_id")}
        for item in payload.get("treatments") or []:
            if not isinstance(item, dict) or not item.get("_id"):
                continue
            key = str(item["_id"])
            if item.get("action") == "remove":
                by_id.pop(key, None)
            else:
                by_id[key] = item
        treatments = list(by_id.values())
        treatments.sort(key=lambda x: _event_datetime(x) or datetime.min.replace(tzinfo=timezone.utc))
        self.data["treatments"] = treatments[-1000:]
        self.data["treatment_count"] = len(treatments)

        # Recalculate the four Nightscout age values from the live treatment cache.
        changes = _extract_change_events({"treatments": treatments})
        mapping = {
            "cannula": ("cannula_age", "last_cannula_change", "cage_warning", "cage_critical"),
            "sensor": ("sensor_age", "last_sensor_change", "sage_warning", "sage_critical"),
            "insulin": ("insulin_age", "last_insulin_change", "iage_warning", "iage_critical"),
            "battery": ("battery_age", "last_battery_change", "bage_warning", "bage_critical"),
        }
        now = datetime.now(timezone.utc)
        for kind, (age_key, timestamp_key, _, _) in mapping.items():
            event = changes.get(kind)
            if event:
                self.data[timestamp_key] = event["timestamp"]
                self.data[age_key] = max(0.0, (now - event["timestamp"]).total_seconds() / 3600)
                self.data[f"{age_key}_event_type"] = event["event_type"]

        self.data["socket_connected"] = self._socket_connected
        self.async_set_updated_data(self.data)

    async def _socketio_loop(self) -> None:
        """Maintain a Socket.IO connection alongside REST polling."""
        delay = 2
        while not self._socket_stop.is_set():
            try:
                secret, token = self._socket_auth()
                await self._socket_client.connect(
                    self.base_url,
                    socketio_path="socket.io",
                    namespaces=["/", "/alarm"],
                    transports=["polling", "websocket"],
                    wait_timeout=15,
                    headers={"User-Agent": "Home Assistant Nightscout Extended"},
                )
                result = await self._socket_client.call(
                    "authorize",
                    {
                        "client": "web",
                        "secret": secret,
                        "token": token,
                        "history": 48,
                    },
                    namespace="/",
                    timeout=15,
                )
                if not isinstance(result, dict) or not result.get("read"):
                    raise RuntimeError("Nightscout Socket.IO authorization failed")
                delay = 2
                while self._socket_client.connected and not self._socket_stop.is_set():
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._socket_connected = False
                self._socket_last_error = str(err)
                _LOGGER.warning("Nightscout Socket.IO error: %s", err)
                self.async_set_updated_data(self.data or {})
            finally:
                if self._socket_client.connected:
                    try:
                        await self._socket_client.disconnect()
                    except Exception:
                        pass
                self._socket_connected = False
            if not self._socket_stop.is_set():
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    async def async_start_socketio(self) -> None:
        """Start the Nightscout Socket.IO listener."""
        self._socket_stop.clear()
        if self._socket_task is None or self._socket_task.done():
            self._socket_task = self.entry.async_create_background_task(
                self.hass, self._socketio_loop(), name="nightscout_extended_socketio"
            )

    async def async_stop_socketio(self) -> None:
        """Stop the Nightscout Socket.IO listener."""
        self._socket_stop.set()
        if self._socket_task is not None:
            self._socket_task.cancel()
            try:
                await self._socket_task
            except asyncio.CancelledError:
                pass
            self._socket_task = None
        if self._socket_client.connected:
            try:
                await self._socket_client.disconnect()
            except Exception:
                pass
        self._socket_connected = False

    async def _get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["API-SECRET"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}{path}"
        try:
            async with self.session.get(
                url, headers=headers, params=params, timeout=20
            ) as response:
                if response.status in (401, 403):
                    raise UpdateFailed("Nightscout authentication failed")
                if response.status >= 400:
                    raise UpdateFailed(
                        f"Nightscout returned HTTP {response.status}"
                    )
                return await response.json(content_type=None)
        except UpdateFailed:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Unable to connect to Nightscout: {err}"
            ) from err
        except ValueError as err:
            raise UpdateFailed(
                f"Nightscout returned invalid JSON: {err}"
            ) from err

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status, devicestatus, entries, treatments, profile = await asyncio.gather(
                self._get_json("/api/v1/status.json"),
                self._get_json("/api/v1/devicestatus.json", {"count": 50}),
                self._get_json(
                    "/api/v1/entries.json", {"count": self.entries_count}
                ),
                self._get_json("/api/v1/treatments.json", {"count": 1000}),
                self._get_json("/api/v1/profile.json"),
            )
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(
                f"Unable to fetch Nightscout data: {err}"
            ) from err

        if not isinstance(entries, list):
            entries = []
        if not isinstance(devicestatus, list):
            devicestatus = []
        if not isinstance(treatments, list):
            treatments = []
        if not isinstance(profile, (dict, list)):
            profile = {}

        entries_sorted = sorted(
            [e for e in entries if isinstance(e, dict)],
            key=lambda e: _parse_dt(
                e.get("dateString") or e.get("created_at")
            ) or datetime.min.replace(tzinfo=timezone.utc),
        )
        latest_entry = entries_sorted[-1] if entries_sorted else {}
        previous_entry = entries_sorted[-2] if len(entries_sorted) > 1 else {}

        # Prefer the AAPS device-status record that actually contains OpenAPS
        # decision data. This avoids accidentally selecting a pump-only record.
        aaps_records = [
            d
            for d in devicestatus
            if isinstance(d, dict)
            and (
                str(d.get("app", "")).upper() == "AAPS"
                or "aaps" in str(d.get("device", "")).lower()
            )
            and _has_openaps_data(d)
        ]
        if not aaps_records:
            aaps_records = [d for d in devicestatus if _has_openaps_data(d)]
        latest_aaps = aaps_records[0] if aaps_records else {}

        # Empty configuration objects are present on ordinary AAPS snapshots.
        # Only accept a genuinely populated configuration record.
        config_record = next(
            (
                d
                for d in devicestatus
                if isinstance(d, dict)
                and isinstance(d.get("configuration"), dict)
                and bool(d.get("configuration"))
            ),
            {},
        )
        aaps_config = (
            config_record.get("configuration", {})
            if isinstance(config_record, dict)
            else {}
        )

        aps_cfg = (
            aaps_config.get("apsConfiguration", {})
            if isinstance(aaps_config, dict)
            else {}
        )
        overview_cfg = (
            aaps_config.get("overviewConfiguration", {})
            if isinstance(aaps_config, dict)
            else {}
        )
        safety_cfg = (
            aaps_config.get("safetyConfiguration", {})
            if isinstance(aaps_config, dict)
            else {}
        )
        sensitivity_cfg = (
            aaps_config.get("sensitivityConfiguration", {})
            if isinstance(aaps_config, dict)
            else {}
        )

        suggested_records = [d for d in aaps_records if isinstance(d.get("openaps", {}).get("suggested"), dict)]
        enacted_records = [d for d in aaps_records if isinstance(d.get("openaps", {}).get("enacted"), dict)]
        record_sort_key = lambda x: _parse_dt(x.get("date") or x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        latest_suggested_record = max(suggested_records, key=record_sort_key) if suggested_records else latest_aaps
        latest_enacted_record = max(enacted_records, key=record_sort_key) if enacted_records else latest_aaps

        decision = _decision(latest_suggested_record)
        pump = (
            latest_aaps.get("pump", {})
            if isinstance(latest_aaps.get("pump"), dict)
            else {}
        )
        pump_ext = (
            pump.get("extended", {})
            if isinstance(pump.get("extended"), dict)
            else {}
        )
        suggested_openaps = latest_suggested_record.get("openaps", {}) if isinstance(latest_suggested_record.get("openaps"), dict) else {}
        enacted_openaps = latest_enacted_record.get("openaps", {}) if isinstance(latest_enacted_record.get("openaps"), dict) else {}
        openaps = latest_aaps.get("openaps", {}) if isinstance(latest_aaps.get("openaps"), dict) else {}
        suggested = suggested_openaps.get("suggested", {}) if isinstance(suggested_openaps.get("suggested"), dict) else {}
        enacted = enacted_openaps.get("enacted", {}) if isinstance(enacted_openaps.get("enacted"), dict) else {}
        iob_record = suggested_openaps.get("iob", {}) if suggested_openaps.get("iob") is not None else openaps.get("iob", {})
        if isinstance(iob_record, list):
            iob_record = iob_record[0] if iob_record else {}
        if not isinstance(iob_record, dict):
            iob_record = {}

        # Uploader/phone data can be stored on a separate AAPS devicestatus
        # record from the OpenAPS dosing record. Search all recent status
        # records, supporting both normalized uploader data and legacy
        # uploaderBattery.
        uploader_battery = None
        uploader_battery_voltage = None
        charging = None
        uploader_records = [
            x for x in devicestatus
            if isinstance(x, dict)
            and (
                isinstance(x.get("uploader"), dict)
                or x.get("uploaderBattery") is not None
                or x.get("isCharging") is not None
            )
        ]
        for record in sorted(uploader_records, key=record_sort_key, reverse=True):
            uploader_data = record.get("uploader") if isinstance(record.get("uploader"), dict) else {}
            if uploader_battery is None:
                if uploader_data.get("battery") is not None:
                    uploader_battery = _num(uploader_data.get("battery"))
                elif record.get("uploaderBattery") is not None:
                    uploader_battery = _num(record.get("uploaderBattery"))
            if uploader_battery_voltage is None and uploader_data.get("batteryVoltage") is not None:
                uploader_battery_voltage = _num(uploader_data.get("batteryVoltage"))
            if charging is None and record.get("isCharging") is not None:
                charging = _bool(record.get("isCharging"))
            if uploader_battery is not None and uploader_battery_voltage is not None and charging is not None:
                break

        # Current glucose is authoritative from Nightscout entries.
        bg = _mgdl(latest_entry.get("sgv") or latest_entry.get("mbg"))
        previous_bg = _mgdl(
            previous_entry.get("sgv") or previous_entry.get("mbg")
        )
        delta = (
            bg - previous_bg
            if bg is not None and previous_bg is not None
            else decision.get("delta")
        )
        direction = _text(latest_entry.get("direction"))
        entry_time = _parse_dt(
            latest_entry.get("dateString") or latest_entry.get("created_at")
        )

        # profile.json may contain one profile object or a list of historical
        # profile objects. Use the newest document and its defaultProfile.
        profile_docs = profile if isinstance(profile, list) else [profile]
        profile_docs = [x for x in profile_docs if isinstance(x, dict)]
        profile_docs.sort(
            key=lambda x: _parse_dt(
                x.get("startDate") or x.get("created_at") or x.get("date")
            ) or datetime.min.replace(tzinfo=timezone.utc)
        )
        profile_doc = profile_docs[-1] if profile_docs else {}

        default_profile = _text(profile_doc.get("defaultProfile"))
        profiles = profile_doc.get("store", {})
        if not isinstance(profiles, dict):
            profiles = {}

        active_profile = (
            profiles.get(default_profile, {}) if default_profile else {}
        )
        if not isinstance(active_profile, dict) and default_profile:
            for profile_name, profile_value in profiles.items():
                if str(profile_name).strip().lower() == default_profile.lower():
                    active_profile = profile_value
                    break
        if not isinstance(active_profile, dict):
            active_profile = {}

        timezone_name = _text(active_profile.get("timezone")) or "UTC"
        try:
            profile_tz = ZoneInfo(timezone_name)
        except Exception:
            profile_tz = timezone.utc
        now_local = datetime.now(profile_tz)

        # Nightscout profiles declare whether their glucose values are mg/dL
        # or mmol/L. Normalize profile sensitivity to canonical mg/dL/U.
        profile_units = _normalise_units(
            active_profile.get("units") or profile_doc.get("units"),
            default="mg/dl",
        )
        profile_sens_raw = _schedule_value(active_profile.get("sens"), now_local)
        profile_sens = _glucose_to_mgdl(profile_sens_raw, profile_units)

        # Insulin-to-carb ratio / carb ratio is g/U.
        carb_ratio = _schedule_value(
            active_profile.get("carbratio"), now_local
        )
        dia = _num(active_profile.get("dia"))

        # Profile targets use the profile's declared units. Normalize to mg/dL.
        target_value = (
            active_profile.get("target_low")
            if active_profile.get("target_low") is not None
            else active_profile.get("target")
        )
        target_high_value = (
            active_profile.get("target_high")
            if active_profile.get("target_high") is not None
            else active_profile.get("target")
        )
        target_low_source = _schedule_value(target_value, now_local)
        target_high_source = _schedule_value(target_high_value, now_local)
        target_low = _glucose_to_mgdl(target_low_source, profile_units)
        target_high = _glucose_to_mgdl(target_high_source, profile_units)

        # Prediction arrays are already mg/dL.
        pred = decision.get("pred_bgs") or {}
        pred_values: list[float] = []
        for key in ("IOB", "ZT", "UAM", "COB", "aCOB"):
            values = pred.get(key)
            if not isinstance(values, list):
                continue
            for item in values:
                value = item.get("predBG") if isinstance(item, dict) else item
                value = _mgdl(value)
                if value is not None and 20 <= value <= 600:
                    pred_values.append(value)

        average_pred = (
            sum(pred_values) / len(pred_values) if pred_values else None
        )
        minimum_pred = min(pred_values) if pred_values else None

        # AAPS console diagnostics are deliberately parsed only from the
        # structured console fields, not guessed from unrelated JSON values.
        console = (
            f"{decision.get('console_log') or ''}\n"
            f"{decision.get('console_error') or ''}"
        )
        min_iob_pred = _first_number_from_text(
            console, "minIOBPredBG"
        )
        min_guard = _first_number_from_text(
            console, "minZTGuardBG"
        )
        min_uam = _first_number_from_text(
            console, "minUAMPredBG"
        )
        naive_eventual = _first_number_from_text(
            console, "naive_eventualBG"
        )
        bg_undershoot = _first_number_from_text(
            console, "bgUndershoot"
        )
        carb_impact = _first_number_from_text(
            console, "Carb Impact"
        )
        carb_impact_duration = _first_number_from_text(
            console, "CI Duration"
        )
        uam_impact = _first_number_from_text(
            console, "UAM Impact"
        )
        uam_duration = _first_number_from_text(
            console, "UAM Duration"
        )
        carbs_required = _first_number_from_text(
            console, "carbsReq"
        )
        zero_temp_duration = _first_number_from_text(
            console, "zeroTempDuration"
        )
        zero_temp_effect = _first_number_from_text(
            console, "zeroTempEffect"
        )
        average_pred_console = _first_number_from_text(
            console, "avgPredBG"
        )
        if average_pred is None:
            average_pred = average_pred_console

        # AAPS overview marks follow the units explicitly published by AAPS.
        # Normalize them once to canonical mg/dL.
        status_settings = (
            status.get("settings", {}) if isinstance(status, dict) else {}
        )
        thresholds = (
            status_settings.get("thresholds", {})
            if isinstance(status_settings, dict)
            else {}
        )
        aaps_units = _normalise_units(
            overview_cfg.get("units"),
            default=profile_units,
        )
        low_mark_source = _num(overview_cfg.get("low_mark"))
        high_mark_source = _num(overview_cfg.get("high_mark"))
        if low_mark_source is None:
            raw_low = _num(thresholds.get("bgLow"))
            low_mark_source = raw_low
        if high_mark_source is None:
            raw_high = _num(thresholds.get("bgHigh"))
            high_mark_source = raw_high
        low_mark = _glucose_to_mgdl(low_mark_source, aaps_units)
        high_mark = _glucose_to_mgdl(high_mark_source, aaps_units)

        values_for_stats = [
            _mgdl(e.get("sgv")) for e in entries_sorted
        ]
        values_for_stats = [
            v for v in values_for_stats if v is not None and 20 <= v <= 600
        ]

        avg_bg = (
            sum(values_for_stats) / len(values_for_stats)
            if values_for_stats
            else None
        )
        sd = None
        if len(values_for_stats) > 1 and avg_bg is not None:
            sd = (
                sum((v - avg_bg) ** 2 for v in values_for_stats)
                / (len(values_for_stats) - 1)
            ) ** 0.5
        cv = sd / avg_bg * 100 if sd is not None and avg_bg else None

        low_mgdl = low_mark if low_mark is not None else 70
        high_mgdl = high_mark if high_mark is not None else 180

        tir = (
            sum(low_mgdl <= v <= high_mgdl for v in values_for_stats)
            / len(values_for_stats)
            * 100
            if values_for_stats
            else None
        )
        tbr = (
            sum(v < low_mgdl for v in values_for_stats)
            / len(values_for_stats)
            * 100
            if values_for_stats
            else None
        )
        tar = (
            sum(v > high_mgdl for v in values_for_stats)
            / len(values_for_stats)
            * 100
            if values_for_stats
            else None
        )
        very_high = (
            sum(v >= 250 for v in values_for_stats)
            / len(values_for_stats)
            * 100
            if values_for_stats
            else None
        )
        gmi = 3.31 + 0.02392 * avg_bg if avg_bg is not None else None

        # Treatment totals are based on Home Assistant's local date.
        local_today = datetime.now().astimezone().date()
        insulin_total = 0.0
        bolus_total = 0.0
        carbs_total = 0.0

        for treatment in treatments:
            if not isinstance(treatment, dict):
                continue

            created = _parse_dt(
                treatment.get("created_at") or treatment.get("timestamp")
            )
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

        # AAPS version: explicit configuration first. Never confuse pump
        # firmware with the AAPS application version.
        aaps_version = (
            _text(aaps_config.get("version"))
            or _text(aaps_config.get("aaps_version"))
            or _text(latest_aaps.get("version"))
        )
        if not aaps_version:
            candidate = _walk_for_key(
                aaps_config, {"aapsVersion", "version"}
            )
            if candidate:
                aaps_version = _text(candidate)

        pump_clock = _parse_dt(pump.get("clock"), profile_tz)
        pump_status_timestamp = (
            _parse_dt(pump.get("status", {}).get("timestamp"), profile_tz)
            if isinstance(pump.get("status"), dict)
            else None
        )
        now_utc = datetime.now(timezone.utc)
        recent_pump_status = (
            pump_status_timestamp is not None
            and abs((now_utc - pump_status_timestamp.astimezone(timezone.utc)).total_seconds()) <= 1800
        )
        recent_pump_clock = (
            pump_clock is not None
            and abs((now_utc - pump_clock.astimezone(timezone.utc)).total_seconds()) <= 1800
        )

        # DataUpdateCoordinator starts with self.data=None on the first REST
        # refresh. Use the previous cached data only when it actually exists.
        # This is also important for fallback values such as the last known
        # temp basal rate.
        previous_data = self.data if isinstance(self.data, dict) else {}

        # Raw OpenAPS/AAPS IOB fields. These are preferred over values repeated
        # in suggested/enacted because openaps.iob is the authoritative IOB record.
        raw_iob = _num(iob_record.get("iob"))
        basal_iob = _num(iob_record.get("basaliob"))
        bolus_iob = _num(iob_record.get("bolusiob"))
        insulin_activity = _num(iob_record.get("activity"))
        bolus_snooze = _num(iob_record.get("bolussnooze"))
        net_basal_insulin = _num(iob_record.get("netbasalinsulin"))
        high_temp_insulin = _num(iob_record.get("hightempinsulin"))
        microbolus_insulin = _num(iob_record.get("microBolusInsulin"))
        microbolus_iob = _num(iob_record.get("microBolusIOB"))
        iob_last_bolus_time = _parse_dt(iob_record.get("lastBolusTime"), profile_tz)
        iob_timestamp = _parse_dt(iob_record.get("timestamp") or iob_record.get("time"), profile_tz)

        pump_status_raw = pump.get("status")
        if isinstance(pump_status_raw, dict):
            pump_status = _text(pump_status_raw.get("status"))
        else:
            pump_status = _text(pump_status_raw)

        base_basal = _num(pump_ext.get("BaseBasalRate"))
        temp_remaining = _num(pump_ext.get("TempBasalRemaining"))
        temp_rate = _resolve_temp_basal_rate(
            pump_ext.get("TempBasalAbsoluteRate"),
            temp_remaining,
            base_basal,
            previous_data.get("temp_basal_rate"),
        )
        temp_start = _parse_dt(
            pump_ext.get("TempBasalStart"), profile_tz
        )
        last_bolus_amount = _num(pump_ext.get("LastBolusAmount"))
        last_bolus_time = _parse_dt(
            pump_ext.get("LastBolus"), profile_tz
        )

        # Treatment fallback for bolus timestamp/amount.
        bolus_treatments = [
            t
            for t in treatments
            if isinstance(t, dict)
            and _num(t.get("insulin")) is not None
            and "bolus" in str(t.get("eventType", "")).lower()
        ]
        bolus_treatments.sort(
            key=lambda t: _parse_dt(
                t.get("created_at") or t.get("timestamp")
            ) or datetime.min.replace(tzinfo=timezone.utc)
        )
        if bolus_treatments:
            latest_bolus = bolus_treatments[-1]
            if last_bolus_amount is None:
                last_bolus_amount = _num(latest_bolus.get("insulin"))
            if last_bolus_time is None:
                last_bolus_time = _parse_dt(
                    latest_bolus.get("created_at")
                    or latest_bolus.get("timestamp"),
                    profile_tz,
                )

        max_bolus = _num(
            safety_cfg.get(
                "max_bolus",
                safety_cfg.get("treatmentssafety_maxbolus"),
            )
        )
        max_carbs = _num(
            safety_cfg.get(
                "max_carbs",
                safety_cfg.get("treatmentssafety_maxcarbs"),
            )
        )
        autosens_min = _num(sensitivity_cfg.get("autosens_min"))
        autosens_max = _num(sensitivity_cfg.get("autosens_max"))
        absorption_cutoff = _num(
            sensitivity_cfg.get("absorption_cutoff")
        )
        min_carb_impact = _num(
            sensitivity_cfg.get("min_5m_carbimpact")
        )
        if min_carb_impact is None:
            min_carb_impact = _num(sensitivity_cfg.get("min5m_carbimpact"))
        dyn_isf_adjust = _num(aps_cfg.get("DynISFAdjust"))

        reservoir = _num(pump.get("reservoir"))
        pump_battery = _num(
            pump.get("battery", {}).get("percent")
            if isinstance(pump.get("battery"), dict)
            else pump.get("battery")
        )
        if pump_battery is None:
            pump_battery = _num(pump_ext.get("battery"))

        pump_status_text = (
            _text(pump.get("status", {}).get("status"))
            if isinstance(pump.get("status"), dict)
            else _text(pump.get("status"))
        )
        closed_loop = pump_status_text is not None and pump_status_text.casefold() == "closed loop"

        # Prefer AAPS' explicit received/enacted flag. Do not infer delivery
        # merely from the presence of an OpenAPS suggestion.
        delivery_received = decision.get("received")
        dynamic_isf = _bool(aps_cfg.get("use_dynamic_sensitivity")) or False
        explicit_smb = _bool(
            aps_cfg.get("enableSMB")
            or aps_cfg.get("enableSMB_always")
            or aps_cfg.get("enableSMB_with_COB")
            or aps_cfg.get("enableSMB_after_carbs")
        )
        smb_enabled = (
            explicit_smb
            if explicit_smb is not None
            else str(decision.get("algorithm") or "").upper() == "SMB"
        )

        # Seed change-event history from the REST treatment bootstrap. Socket.IO
        # then keeps these values current between REST refreshes.
        rest_changes = _extract_change_events(treatments)
        now = datetime.now(timezone.utc)
        for kind, event in rest_changes.items():
            self._change_events[kind] = event

        # Additional raw/diagnostic values. Keep these as None when AAPS/Nightscout
        # does not supply them; do not infer substitutes for raw fields.
        def _first_text(*values):
            for value in values:
                if value is not None and str(value).strip():
                    return _text(value)
            return None

        # AAPS console diagnostics. AAPS writes these labels into consoleLog/
        # consoleError in some algorithm states. They are deliberately parsed
        # only when the exact label is present.
        console_text = "\
".join(
            x for x in (
                _text(latest_aaps.get("consoleLog")),
                _text(latest_aaps.get("consoleError")),
                _text(suggested.get("consoleLog")),
                _text(suggested.get("consoleError")),
            ) if x
        )
        # AAPS exposes the sensitivity values through two complementary paths:
        # the OpenAPS/AAPS result JSON and, in some versions, the algorithm
        # console log. Prefer the structured fields when present and only use
        # the exact console labels as a compatibility fallback.
        structured_autosens = _first_num(
            suggested.get("sensitivityRatio"),
            enacted.get("sensitivityRatio"),
            decision.get("sensitivity_ratio"),
        )
        autosens_ratio_console = _first_number_from_text(console_text, "Autosens ratio")
        autosens_ratio = (
            autosens_ratio_console
            if autosens_ratio_console is not None
            else structured_autosens
        )
        # sensitivityRatio is the value AAPS places in the algorithm result
        # and is therefore the best Nightscout representation of the ratio
        # actually supplied to the algorithm. Keep it separate from the
        # human-readable Autosens diagnostic above.
        autosens_in_algorithm = structured_autosens

        future_sens = _first_number_from_text(console_text, "Future state sensitivity")
        csf = _first_number_from_text(console_text, "CSF")

        # Newer AAPS payloads can carry this as a structured field. The field
        # name explicitly identifies mg/dL, so it is already canonical mg/dL/U.
        isf_for_carbs_structured = _first_num(
            _walk_for_key(suggested, {"isfMgdlForCarbs"}),
            _walk_for_key(enacted, {"isfMgdlForCarbs"}),
            _walk_for_key(latest_aaps, {"isfMgdlForCarbs"}),
        )
        isf_for_carbs = (
            isf_for_carbs_structured
            if isf_for_carbs_structured is not None
            else _first_number_from_text(console_text, "isfMgdlForCarbs")
        )
        meal_insulin_req = _first_number_from_text(console_text, "mealInsulinReq")
        max_uam_smb_basal_minutes = _first_number_from_text(console_text, "maxUAMSMBBasalMinutes")
        current_basal = _first_number_from_text(console_text, "current_basal")
        last_bolus_age = _first_number_from_text(console_text, "last bolus")
        zero_temp_rate = None
        match_zero_rate = re.search(r"zeroTempDuration\\s+(-?\\d+(?:\\.\\d+)?)\\s+zeroTempEffect\\s*:\\s*(-?\\d+(?:\\.\\d+)?)", console_text, re.I)
        if match_zero_rate:
            zero_temp_rate = _first_number_from_text(console_text, "temp needed")
        carbs_required = self.data.get("carbs_required") if self.data else None
        if carbs_required is None:
            carbs_required = _first_number_from_text(console_text, "carbsReq")
        meal_assist = _first_text(suggested.get("mealAssist"), enacted.get("mealAssist"))
        suggested_units = _first_num(suggested.get("units"))
        enacted_units = _first_num(enacted.get("units"))
        charging_value = charging

        # Nightscout/OpenAPS mmtune diagnostic data. Keep the raw structure in
        # attributes and expose the common summary values when available.
        mmtune = latest_aaps.get("mmtune") if isinstance(latest_aaps.get("mmtune"), dict) else {}
        mmtune_frequency = _first_num(mmtune.get("setFreq"), mmtune.get("frequency"))
        mmtune_timestamp = _parse_dt(mmtune.get("timestamp"), profile_tz)
        mmtune_best_rssi = None
        scan_details = mmtune.get("scanDetails")
        if isinstance(scan_details, dict):
            for details in scan_details.values():
                if isinstance(details, dict):
                    rssi = _num(details.get("rssi"))
                    if rssi is not None and (mmtune_best_rssi is None or rssi > mmtune_best_rssi):
                        mmtune_best_rssi = rssi
        elif isinstance(scan_details, list):
            for details in scan_details:
                if isinstance(details, dict):
                    rssi = _num(details.get("rssi"))
                    if rssi is not None and (mmtune_best_rssi is None or rssi > mmtune_best_rssi):
                        mmtune_best_rssi = rssi

        # These quantities represent an amount/duration that is naturally zero
        # when AAPS has no current value to report.
        meal_insulin_req = _zero_if_none(meal_insulin_req)
        max_uam_smb_basal_minutes = _zero_if_none(max_uam_smb_basal_minutes)
        current_basal = _zero_if_none(current_basal)
        suggested_units = _zero_if_none(suggested_units)
        enacted_units = _zero_if_none(enacted_units)

        data = {
            "status": status,
            "devicestatus": latest_aaps,
            "configuration": aaps_config,
            "entries": entries_sorted,
            "treatments": treatments,
            "profile": profile,
            "latest_entry": latest_entry,
            "entry_time": entry_time,

            # Canonical glucose values.
            "bg": bg,
            "delta": delta,
            "direction": direction,
            "average_bg": avg_bg,
            "average_bg_mgdl": avg_bg,
            "average_bg_mmol": _mgdl_to_mmol(avg_bg),
            "bg_sd": sd,
            "bg_cv": cv,
            "tir": tir,
            "tbr": tbr,
            "tar": tar,
            "very_high": very_high,
            "gmi": gmi,

            # AAPS decision.
            "decision": decision,
            "average_pred": average_pred,
            "minimum_pred": minimum_pred,
            "min_iob_pred": min_iob_pred,
            "min_guard": min_guard,
            "min_uam": min_uam,
            "naive_eventual": naive_eventual,
            "bg_undershoot": bg_undershoot,
            "carb_impact": carb_impact,
            "carb_impact_duration": carb_impact_duration,
            "uam_impact": uam_impact,
            "uam_duration": uam_duration,
            "carbs_required": carbs_required,
            "autosens_ratio": _percent_ratio(autosens_ratio),
            "autosens_in_algorithm": _percent_ratio(autosens_in_algorithm),
            "future_state_sensitivity": future_sens,
            "csf": csf,
            "isf_for_carbs": isf_for_carbs,
            "meal_insulin_required": _zero_if_none(meal_insulin_req),
            "max_uam_smb_basal_minutes": _zero_if_none(max_uam_smb_basal_minutes),
            "aaps_current_basal": _zero_if_none(current_basal),
            "last_bolus_age": last_bolus_age,
            "zero_temp_rate": zero_temp_rate,
            "meal_assist": meal_assist,
            "suggested_units": _zero_if_none(suggested_units),
            "enacted_units": _zero_if_none(enacted_units),
            "zero_temp_duration": zero_temp_duration,
            "zero_temp_effect": zero_temp_effect,

            # Treatment totals.
            "insulin_total": insulin_total,
            "bolus_total": bolus_total,
            "carbs_total": carbs_total,

            # AAPS phone/config.
            "aaps_version": _text(aaps_version),
            "aaps_device": _text(latest_aaps.get("device")),
            "uploader_battery": uploader_battery,
            "uploader_battery_voltage": uploader_battery_voltage,
            "charging": charging_value if charging_value is not None else charging,

            # Active Nightscout profile.
            "profile_name": default_profile,
            "profile_timezone": _profile_timezone_name(profile_tz),
            "profile_units": profile_units,
            "aaps_units": aaps_units,
            "profile_tz": profile_tz,
            "profile_sens": profile_sens,
            "dia": dia,
            "carb_ratio": carb_ratio,
            "profile_target_low": target_low,
            "profile_target_high": target_high,

            # Pump.
            "pump_status": pump_status,
            "pump_connected": bool(pump and (recent_pump_status or recent_pump_clock)),
            "pump_clock": pump_clock,
            "pump_firmware": _text(pump_ext.get("Version")),
            "pump_manufacturer": _text(pump.get("manufacturer") or pump.get("Manufacturer")),
            "pump_model": _text(pump.get("model") or pump.get("Model")),
            "pump_device": _text(pump.get("device") or pump.get("Device")),
            "pump_active_profile": _text(pump_ext.get("ActiveProfile")),
            "pump_battery_status": _text(pump.get("battery", {}).get("status")) if isinstance(pump.get("battery"), dict) else None,
            "pump_battery_voltage": _num(pump.get("battery", {}).get("voltage")) if isinstance(pump.get("battery"), dict) else None,
            "pump_bolusing": _bool(pump.get("status", {}).get("bolusing")) if isinstance(pump.get("status"), dict) else None,
            "pump_suspended": _bool(pump.get("status", {}).get("suspended")) if isinstance(pump.get("status"), dict) else None,
            "pump_status_timestamp": pump_status_timestamp,
            "reservoir": reservoir,
            "pump_battery": pump_battery,
            "base_basal": base_basal,
            "temp_basal_rate": temp_rate,
            "temp_basal_remaining": temp_remaining,
            "temp_basal_start": temp_start,
            "last_bolus_amount": last_bolus_amount,
            "last_bolus_time": last_bolus_time,

            # Raw AAPS/OpenAPS suggested/enacted values.
            "suggested_bg": _mgdl(suggested.get("bg")),
            "suggested_snooze_bg": _mgdl(suggested.get("snoozeBG")),
            "suggested_tick": _num(suggested.get("tick")),
            "suggested_temp": _text(suggested.get("temp")),
            "suggested_min_pred_bg": _mgdl(suggested.get("minPredBG")),
            "suggested_rate": _num(suggested.get("rate")),
            "suggested_duration": _num(suggested.get("duration")),
            "suggested_deliver_at": _parse_dt(suggested.get("deliverAt"), profile_tz),
            "suggested_timestamp": _parse_dt(suggested.get("timestamp"), profile_tz),
            "suggested_insulin_required": _num(suggested.get("insulinReq")),
            "suggested_target_bg": _mgdl(suggested.get("targetBG")),
            "suggested_sensitivity_ratio": _percent_ratio(suggested.get("sensitivityRatio")),
            "suggested_variable_sens": _num(suggested.get("variable_sens")),
            "suggested_algorithm": _text(suggested.get("algorithm")),
            "suggested_running_dynamic_isf": suggested.get("runningDynamicIsf"),
            "suggested_reservoir": _num(suggested.get("reservoir")),
            "suggested_smb": _num(suggested.get("smb")),
            "suggested_units": suggested_units,
            "suggested_meal_assist": suggested.get("mealAssist"),
            "suggested_received": suggested.get("received", suggested.get("recieved")),
            "suggested_pred_bgs": suggested.get("predBGs") if isinstance(suggested.get("predBGs"), dict) else {},
            "enacted_bg": _mgdl(enacted.get("bg")),
            "enacted_snooze_bg": _mgdl(enacted.get("snoozeBG")),
            "enacted_tick": _num(enacted.get("tick")),
            "enacted_temp": _text(enacted.get("temp")),
            "enacted_min_pred_bg": _mgdl(enacted.get("minPredBG")),
            "enacted_rate": _num(enacted.get("rate")),
            "enacted_duration": _num(enacted.get("duration")),
            "enacted_deliver_at": _parse_dt(enacted.get("deliverAt"), profile_tz),
            "enacted_timestamp": _parse_dt(enacted.get("timestamp"), profile_tz),
            "enacted_insulin_required": _num(enacted.get("insulinReq")),
            "enacted_target_bg": _mgdl(enacted.get("targetBG")),
            "enacted_sensitivity_ratio": _percent_ratio(enacted.get("sensitivityRatio")),
            "enacted_units": enacted_units,
            "enacted_meal_assist": enacted.get("mealAssist"),
            "enacted_variable_sens": _num(enacted.get("variable_sens")),
            "enacted_received": enacted.get("received", enacted.get("recieved")),
            "enacted_pred_bgs": enacted.get("predBGs") if isinstance(enacted.get("predBGs"), dict) else {},

            # Decision values surfaced as sensors.
            "iob": raw_iob if raw_iob is not None else decision.get("iob"),
            "basal_iob": basal_iob,
            "bolus_iob": bolus_iob,
            "insulin_activity": insulin_activity,
            "bolus_snooze": bolus_snooze,
            "net_basal_insulin": net_basal_insulin,
            "high_temp_insulin": high_temp_insulin,
            "microbolus_insulin": microbolus_insulin,
            "microbolus_iob": microbolus_iob,
            "iob_last_bolus_time": iob_last_bolus_time,
            "iob_timestamp": iob_timestamp,
            "cob": decision.get("cob"),
            "snooze_bg": decision.get("snooze_bg"),
            "aaps_tick": decision.get("tick"),
            "aaps_temp": decision.get("temp"),
            "aaps_reservoir": decision.get("reservoir"),
            "aaps_delivery_time": decision.get("deliver_at"),
            "aaps_suggestion_time": _parse_dt(decision.get("timestamp")),
            "eventual_bg": decision.get("eventual_bg"),
            "target_bg": decision.get("target_bg"),
            "insulin_required": decision.get("insulin_required"),
            "sensitivity_ratio": decision.get("sensitivity_ratio"),
            "variable_sens": decision.get("variable_sens"),
            "requested_rate": decision.get("rate"),
            "requested_duration": decision.get("duration"),
            "smb_amount": decision.get("smb"),
            "decision_reason": decision.get("reason"),
            "decision_state": _decision_state(decision),
            "algorithm": _text(decision.get("algorithm")),

            # Flags.
            "closed_loop": closed_loop,
            "delivery_received": delivery_received,
            "dynamic_isf": dynamic_isf,
            "smb_enabled": smb_enabled,

            # AAPS configuration.
            "low_mark": low_mark,
            "high_mark": high_mark,
            "max_bolus": max_bolus,
            "max_carbs": max_carbs,
            "autosens_min": autosens_min,
            "autosens_max": autosens_max,
            "absorption_cutoff": absorption_cutoff,
            "min_carb_impact": min_carb_impact,
            "dyn_isf_adjust": dyn_isf_adjust,
            "aaps_config_version": _text(aaps_config.get("version")),
            "aaps_config_pump": _text(aaps_config.get("pump")),
            "aaps_config_insulin": _num(aaps_config.get("insulin")),
            "aaps_config_aps": _text(aaps_config.get("aps")),
            "aaps_config_sensitivity": _num(aaps_config.get("sensitivity")),

            # AAPS status-light thresholds.
            "reservoir_warning": _num(
                overview_cfg.get(
                    "res_warning",
                    overview_cfg.get("statuslights_res_warning"),
                )
            ),
            "reservoir_critical": _num(
                overview_cfg.get(
                    "res_critical",
                    overview_cfg.get("statuslights_res_critical"),
                )
            ),
            "pump_battery_warning": _num(
                overview_cfg.get(
                    "bat_warning",
                    overview_cfg.get("statuslights_bat_warning"),
                )
            ),
            "pump_battery_critical": _num(
                overview_cfg.get(
                    "bat_critical",
                    overview_cfg.get("statuslights_bat_critical"),
                )
            ),

            # CAGE / SAGE / IAGE / BAGE from the Socket.IO event stream.
            "cannula_age": self.data.get("cannula_age") if self.data else None,
            "sensor_age": self.data.get("sensor_age") if self.data else None,
            "insulin_age": self.data.get("insulin_age") if self.data else None,
            "battery_age": self.data.get("battery_age") if self.data else None,
            "last_cannula_change": self.data.get("last_cannula_change") if self.data else None,
            "last_sensor_change": self.data.get("last_sensor_change") if self.data else None,
            "last_insulin_change": self.data.get("last_insulin_change") if self.data else None,
            "last_battery_change": self.data.get("last_battery_change") if self.data else None,
            "cage_warning": _num(overview_cfg.get("statuslights_cage_warning")),
            "cage_critical": _num(overview_cfg.get("statuslights_cage_critical")),
            "sage_warning": _num(overview_cfg.get("statuslights_sage_warning")),
            "sage_critical": _num(overview_cfg.get("statuslights_sage_critical")),
            "iage_warning": _num(overview_cfg.get("statuslights_iage_warning")),
            "iage_critical": _num(overview_cfg.get("statuslights_iage_critical")),
            "bage_warning": _num(overview_cfg.get("statuslights_bage_warning")),
            "bage_critical": _num(overview_cfg.get("statuslights_bage_critical")),

            # Nightscout/statistics.
            "nightscout_version": _text(
                status.get("version") if isinstance(status, dict) else None
            ),
            "glucose_unit": self.glucose_unit,
            "isf_unit": self.isf_unit,
            "entry_count": len(entries_sorted),
            "treatment_count": len(treatments),
            "last_treatment": treatments[-1] if treatments else None,
            "socket_connected": self._socket_connected,
            "socket_last_error": self._socket_last_error,
            "glucose_age": (
                (datetime.now(timezone.utc) - entry_time).total_seconds()
                if entry_time
                else None
            ),
        }
        self.data = data
        self.data["devicestatus_records"] = [d for d in devicestatus if isinstance(d, dict)]
        self.data["socket_connected"] = self._socket_connected
        self.data["socket_last_error"] = self._socket_last_error
        self.data["last_alarm"] = self.data.get("last_alarm")
        return data

