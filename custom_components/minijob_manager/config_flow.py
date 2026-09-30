"""Config flow: password step, then e-mail OTP; reauth repeats both."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import MinijobAuthError, MinijobConnectionError, MinijobLogin
from .const import DOMAIN

CONF_CODE = "code"


class MinijobConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._username = ""
        self._login: MinijobLogin | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for portal credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME].strip().lower()
            errors = await self._start(user_input[CONF_PASSWORD])
            if not errors:
                return await self.async_step_otp()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._username): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _start(self, password: str) -> dict[str, str]:
        # dedicated session -> own cookie jar for the Keycloak login flow
        self._login = MinijobLogin(async_create_clientsession(self.hass))
        try:
            await self._login.start(self._username, password)
        except MinijobAuthError:
            return {"base": "invalid_auth"}
        except MinijobConnectionError:
            return {"base": "cannot_connect"}
        return {}

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the 6-digit code sent by e-mail."""
        errors: dict[str, str] = {}
        if user_input is not None and self._login:
            try:
                tokens = await self._login.finish(user_input[CONF_CODE])
            except MinijobAuthError:
                errors["base"] = "invalid_otp"
            except MinijobConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(self._username)
                data = {CONF_USERNAME: self._username, **tokens}
                if self.source == "reauth":
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=data
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=self._username, data=data)
        return self.async_show_form(
            step_id="otp",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Session expired: ask for password again."""
        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Password for reauth."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._start(user_input[CONF_PASSWORD])
            if not errors:
                return await self.async_step_otp()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"username": self._username},
            errors=errors,
        )
