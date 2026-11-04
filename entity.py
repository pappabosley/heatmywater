"""Base entity for Dux HP."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DuxCoordinator


class DuxEntity(CoordinatorEntity[DuxCoordinator]):
    """Common device info and naming."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DuxCoordinator, key: str) -> None:
        super().__init__(coordinator)
        hub = coordinator.api.hub_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{hub}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub)},
            name="Dux HP",
            manufacturer="Dux (Cotherm)",
            model="Heat pump water heater",
        )
