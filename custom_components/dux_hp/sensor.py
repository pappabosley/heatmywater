"""Sensors for Dux HP."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuxConfigEntry
from .const import (
    CURRENT_MODE_OPTIONS,
    REG_AUTO_SETPOINT,
    REG_ENERGY_HP_TODAY,
    REG_ENERGY_RES_TODAY,
    REG_ERROR,
    REG_RUNNING_MODE,
    REG_T_AIR,
    REG_T_EVAP,
    REG_T_TANK,
)
from .coordinator import DuxCoordinator
from .entity import DuxEntity


@dataclass(frozen=True, kw_only=True)
class DuxSensorDescription(SensorEntityDescription):
    value_fn: Callable[[DuxCoordinator], float | str | None]


def _temp(key: str, reg: int, **kw) -> DuxSensorDescription:
    return DuxSensorDescription(
        key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda c, r=reg: c.temperature(r),
        **kw,
    )


def _energy(key: str, reg: int) -> DuxSensorDescription:
    return DuxSensorDescription(
        key=key,
        device_class=SensorDeviceClass.ENERGY,
        # Daily counter that resets at midnight: total_increasing handles the reset.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda c, r=reg: c.value(r),
    )


def _current_mode(c: DuxCoordinator) -> str:
    base, temp = c.modes
    return temp or base


SENSORS: tuple[DuxSensorDescription, ...] = (
    _temp("tank_temperature", REG_T_TANK),
    _temp("air_temperature", REG_T_AIR),
    _temp("evaporator_temperature", REG_T_EVAP, entity_registry_enabled_default=False),
    _temp("auto_setpoint", REG_AUTO_SETPOINT, entity_category=EntityCategory.DIAGNOSTIC),
    _energy("heat_pump_energy_today", REG_ENERGY_HP_TODAY),
    _energy("element_energy_today", REG_ENERGY_RES_TODAY),
    DuxSensorDescription(
        key="current_mode",
        device_class=SensorDeviceClass.ENUM,
        options=CURRENT_MODE_OPTIONS,
        value_fn=_current_mode,
    ),
    DuxSensorDescription(
        key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.value(REG_ERROR),
    ),
    DuxSensorDescription(
        key="running_mode_raw",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.value(REG_RUNNING_MODE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DuxConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(DuxSensor(entry.runtime_data, d) for d in SENSORS)


class DuxSensor(DuxEntity, SensorEntity):
    entity_description: DuxSensorDescription

    def __init__(self, coordinator: DuxCoordinator, description: DuxSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key != "current_mode":
            return None
        base, temp = self.coordinator.modes
        return {"base_mode": base, "temporary_mode": temp}
