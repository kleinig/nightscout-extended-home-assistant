"""Config flow for Nightscout Extended."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_URL

from .const import (
    CONF_API_KEY,
    CONF_DEVICESTATUS_COUNT,
    CONF_ENTRIES_COUNT,
    CONF_TREATMENTS_COUNT,
    DEFAULT_DEVICESTATUS_COUNT,
    DEFAULT_ENTRIES_COUNT,
    DEFAULT_TREATMENTS_COUNT,
    DOMAIN,
)

class NightscoutExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Nightscout Extended config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Configure Nightscout Extended."""
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            if not url.startswith(("http://", "https://")):
                errors[CONF_URL] = "invalid_url"
            else:
                return self.async_create_entry(
                    title=url,
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: user_input.get(CONF_API_KEY, "").strip(),
                        CONF_ENTRIES_COUNT: int(user_input[CONF_ENTRIES_COUNT]),
                        CONF_TREATMENTS_COUNT: int(user_input[CONF_TREATMENTS_COUNT]),
                        CONF_DEVICESTATUS_COUNT: int(user_input[CONF_DEVICESTATUS_COUNT]),
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_URL): str,
            vol.Optional(CONF_API_KEY, default=""): str,
            vol.Optional(
                CONF_ENTRIES_COUNT, default=DEFAULT_ENTRIES_COUNT
            ): vol.All(vol.Coerce(int), vol.Range(min=12, max=2000)),
            vol.Optional(
                CONF_TREATMENTS_COUNT, default=DEFAULT_TREATMENTS_COUNT
            ): vol.All(vol.Coerce(int), vol.Range(min=20, max=2000)),
            vol.Optional(
                CONF_DEVICESTATUS_COUNT, default=DEFAULT_DEVICESTATUS_COUNT
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
