"""Operating mode select for Dux HP."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .const import (
    MODE_WANTED_VALUES,
    REG_BOOST_WANTED,
    REG_MODE_WANTED,
    REG_OUT_END,
    REG_OUT_START,
    SELECTABLE_MODES,
)
from .entity import DuxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([DuxModeSelect(entry.runtime_data, "operating_mode")])


class DuxModeSelect(DuxEntity, SelectEntity):
    """Permanent (base) mode. Selecting a mode also cancels Boost/Holiday, like the app."""

    _attr_options = SELECTABLE_MODES
    _attr_icon = "mdi:water-boiler"

    @property
    def current_option(self) -> str | None:
        base = self.coordinator.modes[0]
        if base.startswith("auto"):
            return "auto"
        return base if base in SELECTABLE_MODES else None

    async def async_select_option(self, option: str) -> None:
        c = self.coordinator
        values = {REG_MODE_WANTED: MODE_WANTED_VALUES[option]}
        if c.modes[1] == "boost":
            values[REG_BOOST_WANTED] = 0
        if c.value(REG_OUT_START) or c.value(REG_OUT_END):
            values[REG_OUT_END] = 0
            values[REG_OUT_START] = 0
        await c.async_send(values)
