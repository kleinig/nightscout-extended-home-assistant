"""Config flow for Nightscout AAPS."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import NumberSelector, NumberSelectorConfig, NumberSelectorMode

from .const import (
    CONF_CARTRIDGE_CAPACITY,
    CONF_DAILY_USAGE,
    CONF_HISTORY_DAYS,
    CONF_PHONE_BATTERY_WARNING,
    CONF_PUMP_BATTERY_WARNING,
    CONF_RESERVOIR_CRITICAL,
    CONF_RESERVOIR_WARNING,
    DEFAULT_CARTRIDGE_CAPACITY,
    DEFAULT_DAILY_USAGE,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_PHONE_BATTERY_WARNING,
    DEFAULT_PUMP_BATTERY_WARNING,
    DEFAULT_RESERVOIR_CRITICAL,
    DEFAULT_RESERVOIR_WARNING,
    DOMAIN,
)
from .coordinator import normalize_url, fetch_json


def _number(default: float, min_value: float, max_value: float, step: float = 1.0):
    return NumberSelector(
        NumberSelectorConfig(
            min=min_value,
            max=max_value,
            step=step,
            mode=NumberSelectorMode.BOX,
        )
    )


async def _validate_url(hass: HomeAssistant, url: str) -> None:
    session = async_get_clientsession(hass)
    await fetch_json(session, f"{normalize_url(url)}/api/v1/devicestatus.json?count=1")


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout AAPS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            try:
                await _validate_url(self.hass, url)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Nightscout AAPS",
                    data={
                        **user_input,
                        CONF_URL: url,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Required(
                    CONF_CARTRIDGE_CAPACITY,
                    default=DEFAULT_CARTRIDGE_CAPACITY,
                ): _number(DEFAULT_CARTRIDGE_CAPACITY, 50, 500, 10),
                vol.Required(
                    CONF_DAILY_USAGE,
                    default=DEFAULT_DAILY_USAGE,
                ): _number(DEFAULT_DAILY_USAGE, 1, 200, 1),
                vol.Required(
                    CONF_HISTORY_DAYS,
                    default=DEFAULT_HISTORY_DAYS,
                ): _number(DEFAULT_HISTORY_DAYS, 1, 30, 1),
                vol.Required(
                    CONF_RESERVOIR_WARNING,
                    default=DEFAULT_RESERVOIR_WARNING,
                ): _number(DEFAULT_RESERVOIR_WARNING, 1, 200, 1),
                vol.Required(
                    CONF_RESERVOIR_CRITICAL,
                    default=DEFAULT_RESERVOIR_CRITICAL,
                ): _number(DEFAULT_RESERVOIR_CRITICAL, 1, 100, 1),
                vol.Required(
                    CONF_PUMP_BATTERY_WARNING,
                    default=DEFAULT_PUMP_BATTERY_WARNING,
                ): _number(DEFAULT_PUMP_BATTERY_WARNING, 1, 100, 1),
                vol.Required(
                    CONF_PHONE_BATTERY_WARNING,
                    default=DEFAULT_PHONE_BATTERY_WARNING,
                ): _number(DEFAULT_PHONE_BATTERY_WARNING, 1, 100, 1),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
