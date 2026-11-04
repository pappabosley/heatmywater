"""Polling coordinator for Dux HP."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DuxApi, DuxAuthError, DuxError
from .const import (
    BOOST_SETPOINT_FALLBACK,
    COMMAND_SETTLE_SECONDS,
    DOMAIN,
    LIMIT_REGISTERS,
    POLL_REGISTERS,
    REG_BOOST_SETPOINT_MAX,
    REG_BOOST_SETPOINT_MIN,
    REG_RUNNING_MODE,
    decode_running_mode,
)

_LOGGER = logging.getLogger(__name__)


class DuxCoordinator(DataUpdateCoordinator[dict[int, float]]):
    """Fetches register values from the cloud."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: DuxApi, interval: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.api = api
        self.boost_limits: tuple[float, float] = BOOST_SETPOINT_FALLBACK

    async def async_load_limits(self) -> None:
        """Read the Boost setpoint range once (falls back to 50-70 degC)."""
        try:
            values = await self.api.read_registers(LIMIT_REGISTERS)
        except DuxError as err:
            _LOGGER.debug("Could not read Boost limits: %s", err)
            return
        lo = values.get(REG_BOOST_SETPOINT_MIN)
        hi = values.get(REG_BOOST_SETPOINT_MAX)
        if lo and hi and 0 < lo < hi:
            self.boost_limits = (lo / 100, hi / 100)

    async def _async_update_data(self) -> dict[int, float]:
        try:
            values = await self.api.read_registers(POLL_REGISTERS)
        except DuxAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DuxError as err:
            raise UpdateFailed(str(err)) from err
        if REG_RUNNING_MODE not in values:
            raise UpdateFailed("Heater returned no data")
        return values

    # --- helpers used by entities ------------------------------------------
    def value(self, register: int) -> float | None:
        return (self.data or {}).get(register)

    def temperature(self, register: int) -> float | None:
        v = self.value(register)
        return None if v is None else round(v / 100, 2)

    @property
    def modes(self) -> tuple[str, str | None]:
        return decode_running_mode(self.value(REG_RUNNING_MODE))

    async def async_send(self, values: dict[int, int]) -> None:
        """Send a command, wait for the heater to act, then refresh."""
        try:
            await self.api.write_registers(values)
        except DuxError as err:
            raise HomeAssistantError(f"Dux HP command failed: {err}") from err
        await asyncio.sleep(COMMAND_SETTLE_SECONDS)
        await self.async_refresh()
