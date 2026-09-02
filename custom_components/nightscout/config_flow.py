from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HISTORY_DAYS, CONF_SCAN_INTERVAL, DEFAULT_HISTORY_DAYS, DEFAULT_SCAN_INTERVAL, DOMAIN


class NightscoutConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            url = user_input[CONF_URL].strip().rstrip("/")
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(f"{url}/api/v1/status.json", timeout=10) as response:
                    if response.status >= 400:
                        raise ValueError
                    if not isinstance(await response.json(content_type=None), dict):
                        raise ValueError
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=url.replace("https://", "").replace("http://", ""),
                    data={CONF_URL: url},
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_HISTORY_DAYS: DEFAULT_HISTORY_DAYS,
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_URL): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            )
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return NightscoutOptionsFlow(config_entry)


class NightscoutOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
            vol.Optional(
                CONF_HISTORY_DAYS,
                default=current.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
