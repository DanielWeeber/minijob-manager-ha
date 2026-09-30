"""Sensors for the Minijob-Manager integration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MinijobConfigEntry
from .calc import current_monthly, next_due, yearly_earnings
from .const import DOMAIN, MINIJOB_MONTHLY_LIMIT
from .coordinator import MinijobCoordinator

EUR = "EUR"


@dataclass(frozen=True, kw_only=True)
class MinijobSensorDescription(SensorEntityDescription):
    """Account-level sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _due(data: dict[str, Any]) -> tuple[date, float] | None:
    return next_due(data["contributions"], date.today())


ACCOUNT_SENSORS: tuple[MinijobSensorDescription, ...] = (
    MinijobSensorDescription(
        key="balance",
        translation_key="balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=EUR,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d["partner"]["mjmDaten"]["betragSaldo"],
    ),
    MinijobSensorDescription(
        key="employees",
        translation_key="employees",
        state_class=SensorStateClass.MEASUREMENT,
        # portal field anzahlBeschaeftigter is 0 for household employers
        value_fn=lambda d: sum(
            1
            for e in d["employees"]
            if not e.get("endeDatum") or e["endeDatum"][:10] >= date.today().isoformat()
        ),
    ),
    MinijobSensorDescription(
        key="unread_messages",
        translation_key="unread_messages",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["unread"],
    ),
    MinijobSensorDescription(
        key="notices",
        translation_key="notices",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: len(d["notices"]),
        attrs_fn=lambda d: {
            "notices": [
                {"text": n["text"], "from": n["from"], "to": n["to"], "warning": n["warning"]}
                for n in d["notices"]
            ]
        },
    ),
    MinijobSensorDescription(
        key="next_due_date",
        translation_key="next_due_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: (due := _due(d)) and due[0],
    ),
    MinijobSensorDescription(
        key="next_due_amount",
        translation_key="next_due_amount",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=EUR,
        value_fn=lambda d: (due := _due(d)) and due[1],
    ),
    MinijobSensorDescription(
        key="sepa_status",
        translation_key="sepa_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d["bank"].get("sepaMandat") or {}).get("status"),
        attrs_fn=lambda d: {
            "valid_from": (d["bank"].get("sepaMandat") or {}).get("gueltigAb"),
            "valid_to": (d["bank"].get("sepaMandat") or {}).get("gueltigBis"),
        },
    ),
)


def _employee_id(emp: dict[str, Any]) -> str:
    # hash instead of the raw social-security number
    raw = f"{emp['rentenversicherungsnummer']}|{emp['startDatum']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MinijobConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        MinijobAccountSensor(coordinator, entry, desc) for desc in ACCOUNT_SENSORS
    )

    known: set[str] = set()

    @callback
    def _add_employees() -> None:
        new = []
        for emp in coordinator.data["employees"]:
            eid = _employee_id(emp)
            if eid in known:
                continue
            known.add(eid)
            new += [
                MinijobEmployeeSensor(coordinator, entry, eid, kind)
                for kind in ("monthly", "yearly", "remaining")
            ]
        if new:
            async_add_entities(new)

    _add_employees()
    entry.async_on_unload(coordinator.async_add_listener(_add_employees))


class MinijobAccountSensor(CoordinatorEntity[MinijobCoordinator], SensorEntity):
    """Account-level sensor."""

    _attr_has_entity_name = True
    entity_description: MinijobSensorDescription

    def __init__(
        self,
        coordinator: MinijobCoordinator,
        entry: MinijobConfigEntry,
        description: MinijobSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name="Minijob-Manager",
            manufacturer="Minijob-Zentrale",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        return fn(self.coordinator.data) if fn else None


class MinijobEmployeeSensor(CoordinatorEntity[MinijobCoordinator], SensorEntity):
    """Earnings sensors per employee (monthly earnings, no hours available)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = EUR

    def __init__(
        self,
        coordinator: MinijobCoordinator,
        entry: MinijobConfigEntry,
        eid: str,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._eid = eid
        self._kind = kind
        self._attr_translation_key = f"employee_{kind}"
        self._attr_unique_id = f"{entry.unique_id}_{eid}_{kind}"
        emp = self._employee() or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.unique_id}_{eid}")},
            name=f"{emp.get('vorname', '')} {emp.get('nachname', '')}".strip()
            or "Beschäftigte/r",
            manufacturer="Minijob-Zentrale",
            via_device=(DOMAIN, entry.unique_id),
        )

    def _employee(self) -> dict[str, Any] | None:
        for emp in self.coordinator.data["employees"]:
            if _employee_id(emp) == self._eid:
                return emp
        return None

    @property
    def available(self) -> bool:
        return super().available and self._employee() is not None

    @property
    def native_value(self) -> float | None:
        emp = self._employee()
        if not emp:
            return None
        today = date.today()
        if self._kind == "monthly":
            return current_monthly(emp["entgelte"], today)
        yearly = yearly_earnings(emp["entgelte"], today.year)
        if self._kind == "yearly":
            return yearly
        return round(MINIJOB_MONTHLY_LIMIT * 12 - yearly, 2)
