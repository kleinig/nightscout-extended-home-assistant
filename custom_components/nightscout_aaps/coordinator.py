"""Data coordinator for Nightscout AAPS."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import ClientError, ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_TIMEOUT,
    CONF_CARTRIDGE_CAPACITY,
    CONF_DAILY_USAGE,
    CONF_HISTORY_DAYS,
    DOMAIN,
    UPDATE_INTERVAL,
)


def normalize_url(url: str) -> str:
    """Normalize a Nightscout URL."""
    return url.strip().rstrip("/")


async def fetch_json(session: ClientSession, url: str) -> Any:
    """Fetch JSON from Nightscout."""
    timeout = __import__("aiohttp").ClientTimeout(total=API_TIMEOUT)
    async with session.get(url, timeout=timeout) as response:
        response.raise_for_status()
        return await response.json()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _reservoir_usage(history: list[dict[str, Any]], days: int, fallback: float) -> float:
    """Estimate U/day from downward reservoir changes.

    Positive jumps are treated as cartridge changes/refills and are ignored.
    This avoids needing a treatment endpoint and uses the actual pump reservoir.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    points: list[tuple[datetime, float]] = []

    for item in history:
        pump = item.get("pump") or {}
        reservoir = pump.get("reservoir")
        dt = _parse_dt(item.get("created_at") or pump.get("clock"))
        if dt is None or reservoir is None or dt < cutoff:
            continue
        try:
            points.append((dt, float(reservoir)))
        except (TypeError, ValueError):
            continue

    points.sort()
    if len(points) < 2:
        return fallback

    consumed = 0.0
    for (_, previous), (_, current) in zip(points, points[1:]):
        delta = previous - current
        if 0 < delta < 20:
            consumed += delta

    elapsed = max((points[-1][0] - points[0][0]).total_seconds() / 86400, 1 / 24)
    estimate = consumed / elapsed

    # Guard against bad/stale reservoir data.
    if estimate < 1 or estimate > 200:
        return fallback
    return estimate


class NightscoutAAPSCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Nightscout API data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.url = normalize_url(entry.data["url"])
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        self.session = async_get_clientsession(hass)

        self.cartridge_capacity = float(entry.data[CONF_CARTRIDGE_CAPACITY])
        self.config_daily_usage = float(entry.data[CONF_DAILY_USAGE])
        self.history_days = int(entry.data[CONF_HISTORY_DAYS])

        self._history: list[dict[str, Any]] = []

        super().__init__(
            hass,
            logging.getLogger(DOMAIN),
            name="Nightscout AAPS",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            current = await fetch_json(
                self.session,
                f"{self.url}/api/v1/devicestatus.json?count=1",
            )

            if not isinstance(current, list) or not current:
                raise UpdateFailed("Nightscout returned no device status data")

            history_count = max(500, self.history_days * 24 * 12 + 100)
            history = await fetch_json(
                self.session,
                f"{self.url}/api/v1/devicestatus.json?count={history_count}",
            )
        except (ClientError, asyncio.TimeoutError, ValueError) as err:
            raise UpdateFailed(f"Unable to retrieve Nightscout data: {err}") from err

        if not isinstance(history, list):
            history = current

        self._history = history

        item = current[0]
        pump = item.get("pump") or {}
        extended = pump.get("extended") or {}
        battery = pump.get("battery") or {}
        status = pump.get("status") or {}

        dynamic_daily_usage = _reservoir_usage(
            history,
            self.history_days,
            self.config_daily_usage,
        )

        reservoir = float(pump.get("reservoir", 0) or 0)
        remaining_days = reservoir / dynamic_daily_usage if dynamic_daily_usage > 0 else 0
        remaining_hours = remaining_days * 24
        reservoir_percent = max(0.0, min(100.0, reservoir / self.cartridge_capacity * 100))

        data_age = None
        pump_timestamp = _parse_dt(status.get("timestamp") or pump.get("clock") or item.get("created_at"))
        if pump_timestamp:
            data_age = max(0.0, (datetime.now(timezone.utc) - pump_timestamp).total_seconds() / 60)

        return {
            "reservoir": reservoir,
            "reservoir_percent": reservoir_percent,
            "pump_battery": float(battery.get("percent", 0) or 0),
            "pump_status": status.get("status", "Unknown"),
            "pump_clock": pump.get("clock"),
            "profile": extended.get("ActiveProfile", "Unknown"),
            "base_basal": float(extended.get("BaseBasalRate", 0) or 0),
            "temp_basal": float(extended.get("TempBasalAbsoluteRate", 0) or 0),
            "temp_basal_remaining": int(extended.get("TempBasalRemaining", 0) or 0),
            "last_bolus": float(extended.get("LastBolusAmount", 0) or 0),
            "last_bolus_time": extended.get("LastBolus"),
            "aaps_phone_battery": float(item.get("uploaderBattery", 0) or 0),
            "device": item.get("device", ""),
            "app": item.get("app", "AAPS"),
            "created_at": item.get("created_at"),
            "data_age": data_age if data_age is not None else 999.0,
            "daily_usage": dynamic_daily_usage,
            "estimated_days": remaining_days,
            "estimated_hours": remaining_hours,
            "cartridge_capacity": self.cartridge_capacity,
        }

    async def async_shutdown(self) -> None:
        """Release coordinator resources."""
        # Shared Home Assistant aiohttp session; nothing to close.
        return
