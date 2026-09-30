"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinijobAuthError, MinijobClient, MinijobConnectionError
from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class MinijobCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch all portal data in one go."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: MinijobClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Minijob-Manager",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        client = self.client
        try:
            partner = await client.get("geschaeftspartner/geschaeftspartnernummer")
            role = partner.get("rolle") or ""
            data: dict[str, Any] = {
                "partner": partner,
                "bank": await client.get("geschaeftspartner/bankverbindung"),
                "notices": await client.get("meldungen/current", {"rolle": role}),
                "unread": await client.get(
                    "messages/count", {"read": "false", "folder": "Posteingang"}
                ),
                "employees": await client.get_all_pages(
                    "meldezeiten", {"sort": "nachname", "descending": "false"}
                ),
                "contributions": await client.get(
                    "beitraege", {"from": f"{date.today().year - 1}-01-01"}
                ),
            }
        except MinijobAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MinijobConnectionError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            # persist rotated tokens
            if self.config_entry and client.tokens != dict(self.config_entry.data):
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, **client.tokens},
                )
        return data
