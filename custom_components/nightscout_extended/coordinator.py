from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio
import math
import re
from typing import Any
import json
import hashlib
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import aiohttp
import socketio
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
        "delta": _num(source.get("delta")),  # mg/dL, never heuristic-converted
        "eventual_bg": _mgdl(source.get("eventualBG")),
        "target_bg": _mgdl(source.get("targetBG")),
        "insulin_required": _num(source.get("insulinReq")),
        "sensitivity_ratio": _num(source.get("sensitivityRatio")),
        "variable_sens": _num(source.get("variable_sens")),  # mg/dL/U
        "iob": _num(source.get("IOB")),
        "cob": _num(source.get("COB")),
        "rate": requested_number("rate"),
        "duration": requested_number("duration"),
        "smb": requested_number("smb"),
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
            _LOGGER.warning("Nightscout Socket.IO disconnected")

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

        self.data["socket_last_update"] = _parse_dt(payload.get("lastUpdated"))
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
            and isinstance(x.get("openaps"), dict)
        ]
        if not aaps_records:
            aaps_records = [x for x in statuses if isinstance(x, dict) and isinstance(x.get("openaps"), dict)]
        if aaps_records:
            latest_aaps = max(aaps_records, key=lambda x: _parse_dt(x.get("date") or x.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
            self.data["devicestatus"] = latest_aaps
            decision = _decision(latest_aaps)
            self.data["decision"] = decision
            for target, source in {
                "iob": "iob", "cob": "cob", "eventual_bg": "eventual_bg",
                "target_bg": "target_bg", "insulin_required": "insulin_required",
                "sensitivity_ratio": "sensitivity_ratio", "variable_sens": "variable_sens",
                "requested_rate": "rate", "requested_duration": "duration", "smb_amount": "smb",
            }.items():
                self.data[target] = decision.get(source)
            self.data["algorithm"] = _text(decision.get("algorithm"))
            self.data["decision_reason"] = decision.get("reason")
            self.data["dynamic_isf"] = bool(latest_aaps.get("configuration", {}).get("apsConfiguration", {}).get("use_dynamic_sensitivity", self.data.get("dynamic_isf")))
            self.data["delivery_received"] = bool(latest_aaps.get("openaps", {}).get("enacted") or latest_aaps.get("openaps", {}).get("suggested"))
            self.data["aaps_device"] = _text(latest_aaps.get("device")) or self.data.get("aaps_device")
            if latest_aaps.get("uploaderBattery") is not None:
                self.data["uploader_battery"] = _num(latest_aaps.get("uploaderBattery"))
            if latest_aaps.get("isCharging") is not None:
                self.data["charging"] = latest_aaps.get("isCharging")

            pump = latest_aaps.get("pump") if isinstance(latest_aaps.get("pump"), dict) else {}
            ext = pump.get("extended") if isinstance(pump.get("extended"), dict) else {}
            self.data["pump_status"] = _text(pump.get("status")) if not isinstance(pump.get("status"), dict) else _text(pump.get("status", {}).get("status"))
            self.data["pump_connected"] = bool(pump)
            self.data["pump_firmware"] = _text(ext.get("Version")) or self.data.get("pump_firmware")
            self.data["reservoir"] = _num(ext.get("Reservoir")) if ext.get("Reservoir") is not None else _num(pump.get("reservoir"))
            self.data["pump_battery"] = _num(pump.get("battery", {}).get("percent")) if isinstance(pump.get("battery"), dict) else _num(pump.get("battery"))
            self.data["base_basal"] = _num(ext.get("BaseBasalRate"))
            self.data["temp_basal_rate"] = _num(ext.get("TempBasalAbsoluteRate"))
            self.data["temp_basal_remaining"] = _num(ext.get("TempBasalRemaining"))
            self.data["temp_basal_start"] = _parse_dt(ext.get("TempBasalStart"))
            self.data["last_bolus_amount"] = _num(ext.get("LastBolusAmount"))
            self.data["last_bolus_time"] = _parse_dt(ext.get("LastBolus"))
            self.data["pump_clock"] = _parse_dt(pump.get("clock"))

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
            self._socket_task = self.hass.async_create_task(
                self._socketio_loop(), name="nightscout_extended_socketio"
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
            and isinstance(d.get("openaps"), dict)
        ]
        if not aaps_records:
            aaps_records = [
                d
                for d in devicestatus
                if isinstance(d, dict)
                and isinstance(d.get("openaps"), dict)
            ]
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

        decision = _decision(latest_aaps)
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

        uploader_battery = _num(latest_aaps.get("uploaderBattery"))
        charging = latest_aaps.get("isCharging")

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

        # Nightscout profile sensitivity is mmol/L/U -> expose mg/dL/U.
        profile_sens_raw = _schedule_value(
            active_profile.get("sens"), now_local
        )
        profile_sens = (
            profile_sens_raw * 18.0
            if profile_sens_raw is not None
            else None
        )

        # Insulin-to-carb ratio / carb ratio is g/U.
        carb_ratio = _schedule_value(
            active_profile.get("carbratio"), now_local
        )
        dia = _num(active_profile.get("dia"))

        # Profile targets are mmol/L.
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
        target_low = _schedule_value(target_value, now_local)
        target_high = _schedule_value(target_high_value, now_local)

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

        # AAPS configuration marks are mmol/L.
        status_settings = (
            status.get("settings", {}) if isinstance(status, dict) else {}
        )
        thresholds = (
            status_settings.get("thresholds", {})
            if isinstance(status_settings, dict)
            else {}
        )
        low_mark = _num(overview_cfg.get("low_mark"))
        high_mark = _num(overview_cfg.get("high_mark"))
        if low_mark is None:
            low_mark = (
                _num(thresholds.get("bgLow")) / 18.0
                if _num(thresholds.get("bgLow")) is not None
                else 70 / 18.0
            )
        if high_mark is None:
            high_mark = (
                _num(thresholds.get("bgHigh")) / 18.0
                if _num(thresholds.get("bgHigh")) is not None
                else 180 / 18.0
            )

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

        low_mgdl = low_mark * 18 if low_mark is not None else 70
        high_mgdl = high_mark * 18 if high_mark is not None else 180

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

        pump_status_raw = pump.get("status")
        if isinstance(pump_status_raw, dict):
            pump_status = _text(pump_status_raw.get("status"))
        else:
            pump_status = _text(pump_status_raw)

        temp_rate = _num(pump_ext.get("TempBasalAbsoluteRate"))
        temp_remaining = _num(pump_ext.get("TempBasalRemaining"))
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
                    or latest_bolus.get("timestamp")
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

        closed_loop = "closed loop" in str(
            pump.get("status", "")
        ).lower()

        delivery_received = bool(
            latest_aaps.get("openaps", {}).get("enacted")
            or latest_aaps.get("openaps", {}).get("suggested")
        )
        dynamic_isf = bool(aps_cfg.get("use_dynamic_sensitivity"))
        smb_enabled = (
            str(decision.get("algorithm") or "").upper() == "SMB"
            or decision.get("smb") is not None
        )

        # Seed change-event history from the REST treatment bootstrap. Socket.IO
        # then keeps these values current between REST refreshes.
        rest_changes = _extract_change_events(treatments)
        now = datetime.now(timezone.utc)
        for kind, event in rest_changes.items():
            self._change_events[kind] = event

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
            "charging": charging,

            # Active Nightscout profile.
            "profile_name": default_profile,
            "profile_sens": profile_sens,
            "dia": dia,
            "carb_ratio": carb_ratio,
            "profile_target_low": target_low,
            "profile_target_high": target_high,

            # Pump.
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

            # Decision values surfaced as sensors.
            "iob": decision.get("iob"),
            "cob": decision.get("cob"),
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
        self._apply_socket_events()
        return data

