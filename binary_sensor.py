"""Binary sensors for Dux HP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .const import REG_ERROR, REG_RELAY_COMP, REG_RELAY_FAN, REG_RELAY_RES
from .coordinator import DuxCoordinator
from .entity import DuxEntity


@dataclass(frozen=True, kw_only=True)
class DuxBinaryDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[DuxCoordinator], bool | None]


def _flag(reg: int) -> Callable[[DuxCoordinator], bool | None]:
    def fn(c: DuxCoordinator) -> bool | None:
        v = c.value(reg)
        return None if v is None else bool(v)

    return fn


BINARY_SENSORS: tuple[DuxBinaryDescription, ...] = (
    DuxBinaryDescription(
        key="compressor", device_class=BinarySensorDeviceClass.RUNNING, is_on_fn=_flag(REG_RELAY_COMP)
    ),
    DuxBinaryDescription(
        key="element", device_class=BinarySensorDeviceClass.HEAT, is_on_fn=_flag(REG_RELAY_RES)
    ),
    DuxBinaryDescription(
        key="fan", device_class=BinarySensorDeviceClass.RUNNING, is_on_fn=_flag(REG_RELAY_FAN)
    ),
    DuxBinaryDescription(key="boost_active", is_on_fn=lambda c: c.modes[1] == "boost"),
    DuxBinaryDescription(key="holiday_active", is_on_fn=lambda c: c.modes[1] == "holiday"),
    DuxBinaryDescription(
        key="problem", device_class=BinarySensorDeviceClass.PROBLEM, is_on_fn=_flag(REG_ERROR)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(DuxBinarySensor(entry.runtime_data, d) for d in BINARY_SENSORS)


class DuxBinarySensor(DuxEntity, BinarySensorEntity):
    entity_description: DuxBinaryDescription

    def __init__(self, coordinator: DuxCoordinator, description: DuxBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator)
