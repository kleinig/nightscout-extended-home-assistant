from __future__ import annotations

from urllib.parse import urlparse
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_KEY,
    CONF_ENTRIES_COUNT,
    CONF_URL,
    DEFAULT_ENTRIES_COUNT,
    DOMAIN,
    NAME,
)


class NightscoutConnectionError(Exception):
    """Base connection error."""


class NightscoutAuthError(NightscoutConnectionError):
    """Authentication failed."""


class NightscoutResponseError(NightscoutConnectionError):
    """Nightscout returned an unexpected response."""


def _normalise_url(value: str) -> str:
    url = value.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid_url")
    return url


async def _test_connection(
    hass,
    url: str,
    api_key: str,
) -> None:
    """Perform a small, independent connection test for the config flow."""
    session = async_get_clientsession(hass)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["API-SECRET"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with session.get(
            f"{url}/api/v1/status.json",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status in (401, 403):
                raise NightscoutAuthError
            if response.status >= 400:
                raise NightscoutConnectionError
            status = await response.json(content_type=None)

        if not isinstance(status, dict):
            raise NightscoutResponseError

        # A successful status response is sufficient to prove connectivity,
        # but entries are also checked because the integration depends on them.
        async with session.get(
            f"{url}/api/v1/entries.json",
            params={"count": 1},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status in (401, 403):
                raise NightscoutAuthError
            if response.status >= 400:
                raise NightscoutConnectionError
            entries = await response.json(content_type=None)

        if not isinstance(entries, list):
            raise NightscoutResponseError

    except NightscoutConnectionError:
        raise
    except NightscoutResponseError:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise NightscoutConnectionError from err
    except (ValueError, TypeError) as err:
        raise NightscoutResponseError from err


class NightscoutExtendedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Nightscout Extended config flow."""

    VERSION = 1

    def _schema(self, current: dict[str, Any] | None = None) -> vol.Schema:
        current = current or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_URL,
                    default=current.get(CONF_URL, ""),
                ): str,
                vol.Optional(
                    CONF_API_KEY,
                    default=current.get(CONF_API_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_ENTRIES_COUNT,
                    default=current.get(
                        CONF_ENTRIES_COUNT, DEFAULT_ENTRIES_COUNT
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=48, max=1000)),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                url = _normalise_url(user_input[CONF_URL])
                user_input[CONF_URL] = url
                await _test_connection(
                    self.hass,
                    url,
                    user_input.get(CONF_API_KEY, "").strip(),
                )
            except ValueError:
                errors["base"] = "invalid_url"
            except NightscoutAuthError:
                errors["base"] = "invalid_auth"
            except NightscoutResponseError:
                errors["base"] = "invalid_response"
            except NightscoutConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        current = self._get_reconfigure_entry().data

        if user_input is not None:
            try:
                url = _normalise_url(user_input[CONF_URL])
                user_input[CONF_URL] = url
                await _test_connection(
                    self.hass,
                    url,
                    user_input.get(CONF_API_KEY, "").strip(),
                )
            except ValueError:
                errors["base"] = "invalid_url"
            except NightscoutAuthError:
                errors["base"] = "invalid_auth"
            except NightscoutResponseError:
                errors["base"] = "invalid_response"
            except NightscoutConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(current),
            errors=errors,
        )


    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return NightscoutExtendedOptionsFlow()


class NightscoutExtendedOptionsFlow(config_entries.OptionsFlow):
    """Manage display unit preferences."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_GLUCOSE_UNIT,
                    default=self.config_entry.options.get(
                        CONF_GLUCOSE_UNIT, DEFAULT_GLUCOSE_UNIT
                    ),
                ): vol.In(["mmol/L", "mg/dL"]),
                vol.Required(
                    CONF_ISF_UNIT,
                    default=self.config_entry.options.get(
                        CONF_ISF_UNIT, DEFAULT_ISF_UNIT
                    ),
                ): vol.In(["mmol/L/U", "mg/dL/U"]),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
