"""Config flow test with mocked portal login."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.minijob_manager.const import DOMAIN

TOKENS = {
    "access_token": "a",
    "refresh_token": "r",
    "expires_at": 9999999999.0,
    "refresh_expires_at": 9999999999.0,
}


async def test_flow_password_then_otp(hass):
    with patch(
        "custom_components.minijob_manager.config_flow.MinijobLogin.start",
        new=AsyncMock(),
    ), patch(
        "custom_components.minijob_manager.config_flow.MinijobLogin.finish",
        new=AsyncMock(return_value=TOKENS),
    ), patch(
        "custom_components.minijob_manager.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "Test@Example.com", "password": "x"}
        )
        assert result["step_id"] == "otp"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123456"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "test@example.com"
    assert "password" not in result["data"]
