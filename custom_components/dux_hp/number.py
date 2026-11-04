"""Boost target temperature for Dux HP."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .const import REG_BOOST_SETPOINT
from .entity import DuxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([DuxBoostTarget(entry.runtime_data, "boost_target")])


class DuxBoostTarget(DuxEntity, NumberEntity):
    """BOOST__setpoint (degC x 100). Boost stops when the tank reaches this."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:thermometer-chevron-up"

    @property
    def native_min_value(self) -> float:
        return self.coordinator.boost_limits[0]

    @property
    def native_max_value(self) -> float:
        return self.coordinator.boost_limits[1]

    @property
    def native_value(self) -> float | None:
        return self.coordinator.temperature(REG_BOOST_SETPOINT)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send({REG_BOOST_SETPOINT: int(round(value * 100))})
