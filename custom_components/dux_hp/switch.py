"""Boost switch for Dux HP."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .const import (
    MODE_WANTED_VALUES,
    REG_BOOST_SETPOINT,
    REG_BOOST_WANTED,
    REG_MODE_WANTED,
    REG_OUT_END,
    REG_OUT_START,
    REG_T_TANK,
)
from .entity import DuxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([DuxBoostSwitch(entry.runtime_data, "boost")])


class DuxBoostSwitch(DuxEntity, SwitchEntity):
    """Start/stop Boost exactly as the Dux HP app does."""

    _attr_icon = "mdi:rocket-launch"

    @property
    def is_on(self) -> bool:
        return self.coordinator.modes[1] == "boost"

    async def async_turn_on(self, **kwargs: Any) -> None:
        c = self.coordinator
        tank = c.temperature(REG_T_TANK)
        target = c.temperature(REG_BOOST_SETPOINT)
        if tank is not None and target is not None and tank >= target:
            raise HomeAssistantError(
                f"Tank is already at {tank:.1f} °C, which is at or above the Boost "
                f"target of {target:.1f} °C. The heater ignores Boost in this case; "
                "raise the Boost target temperature first."
            )
        values = {REG_BOOST_WANTED: 1}
        # The app cancels any Holiday period when starting Boost.
        if c.value(REG_OUT_START) or c.value(REG_OUT_END):
            values[REG_OUT_END] = 0
            values[REG_OUT_START] = 0
        await c.async_send(values)
        if not self.is_on:
            raise HomeAssistantError("Boost command was sent but the heater did not start Boost.")

    async def async_turn_off(self, **kwargs: Any) -> None:
        c = self.coordinator
        # The app stops Boost by re-asserting the base mode with BOOST__mode_wanted = 0.
        mode = c.value(REG_MODE_WANTED)
        if mode is None:
            mode = MODE_WANTED_VALUES["auto"]
        await c.async_send({REG_MODE_WANTED: int(mode), REG_BOOST_WANTED: 0})
        if self.is_on:
            raise HomeAssistantError("Stop command was sent but Boost is still active.")
