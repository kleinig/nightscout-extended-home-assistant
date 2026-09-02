from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from .const import (
    CONF_ENTRIES_COUNT,
    CONF_URL,
    DEFAULT_ENTRIES_COUNT,
    DOMAIN,
    NAME,
)


class NightscoutExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            user_input[CONF_URL] = url

            # Do a lightweight validation by constructing the coordinator and
            # performing its first refresh. The coordinator reports useful
            # connection/authentication errors.
            try:
                from .coordinator import NightscoutExtendedCoordinator

                coordinator = NightscoutExtendedCoordinator(
                    self.hass,
                    type(
                        "Entry",
                        (),
                        {"data": user_input, "entry_id": "config_flow"},
                    )(),
                )
                await coordinator.async_config_entry_first_refresh()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=url,
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_API_KEY, default=""): str,
                vol.Optional(
                    CONF_ENTRIES_COUNT, default=DEFAULT_ENTRIES_COUNT
                ): vol.All(vol.Coerce(int), vol.Range(min=48, max=1000)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
