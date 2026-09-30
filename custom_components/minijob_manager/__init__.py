"""The Minijob-Manager integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import MinijobClient
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
)
from .coordinator import MinijobCoordinator

PLATFORMS = [Platform.SENSOR]

type MinijobConfigEntry = ConfigEntry[MinijobCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MinijobConfigEntry) -> bool:
    """Set up from a config entry."""
    session = async_create_clientsession(hass)
    tokens = {
        "access_token": entry.data[CONF_ACCESS_TOKEN],
        "refresh_token": entry.data[CONF_REFRESH_TOKEN],
        "expires_at": entry.data[CONF_EXPIRES_AT],
        "refresh_expires_at": entry.data[CONF_REFRESH_EXPIRES_AT],
    }
    coordinator = MinijobCoordinator(hass, entry, MinijobClient(session, tokens))
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MinijobConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
