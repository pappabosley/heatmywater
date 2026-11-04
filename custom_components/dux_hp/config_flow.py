"""Config flow for Dux HP."""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuxApi, DuxAuthError, DuxError
from .const import (
    CONF_HUB_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    REG_RUNNING_MODE,
)

HUB_RE = re.compile(r"^[0-9a-f]{32}$")


async def _validate(hass, email: str, password: str, hub_id: str) -> dict[str, str]:
    """Return an errors dict (empty if OK)."""
    api = DuxApi(async_get_clientsession(hass), email, password, hub_id)
    try:
        await api.login()
        await api.session_check(force=True)
        values = await api.read_registers([REG_RUNNING_MODE])
    except DuxAuthError:
        return {"base": "invalid_auth"}
    except DuxError:
        return {"base": "cannot_connect"}
    if REG_RUNNING_MODE not in values:
        return {CONF_HUB_ID: "no_data"}
    return {}


class DuxConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            hub = user_input[CONF_HUB_ID].strip().lower().replace("-", "")
            if not HUB_RE.match(hub):
                errors[CONF_HUB_ID] = "invalid_hub"
            else:
                await self.async_set_unique_id(hub)
                self._abort_if_unique_id_configured()
                errors = await _validate(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD], hub
                )
                if not errors:
                    return self.async_create_entry(
                        title="Dux HP",
                        data={
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_HUB_ID: hub,
                        },
                    )
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_HUB_ID): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate(
                self.hass, entry.data[CONF_EMAIL], user_input[CONF_PASSWORD], entry.data[CONF_HUB_ID]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DuxOptionsFlow()


class DuxOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
