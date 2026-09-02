from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from .const import (
    CONF_API_SECRET,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import validate_connection


class NightscoutConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            secret = user_input.get(CONF_API_SECRET, "").strip()
            interval = int(user_input[CONF_SCAN_INTERVAL])

            try:
                await validate_connection(self.hass, url, secret)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=url.replace("https://", "").replace("http://", ""),
                    data={
                        CONF_URL: url,
                        CONF_API_SECRET: secret,
                        CONF_SCAN_INTERVAL: interval,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_API_SECRET, default=""): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=3600),
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
