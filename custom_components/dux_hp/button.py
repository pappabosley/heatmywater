"""Manual refresh button for Dux HP."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .entity import DuxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([DuxRefreshButton(entry.runtime_data, "refresh")])


class DuxRefreshButton(DuxEntity, ButtonEntity):
    """Read the heater now instead of waiting for the next scheduled poll."""

    _attr_icon = "mdi:refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()
