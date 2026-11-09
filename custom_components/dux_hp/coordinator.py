"""Polling coordinator for Dux HP."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DuxApi, DuxAuthError, DuxConnectionError, DuxError
from .const import (
    AUTH_FAILURES_BEFORE_REAUTH,
    BOOST_SETPOINT_FALLBACK,
    COMMAND_SETTLE_SECONDS,
    DOMAIN,
    LIMIT_REGISTERS,
    POLL_REGISTERS,
    REG_BOOST_SETPOINT_MAX,
    REG_BOOST_SETPOINT_MIN,
    REG_RUNNING_MODE,
    RETRY_INTERVAL,
    decode_running_mode,
)

_LOGGER = logging.getLogger(__name__)

# Pause before the immediate in-poll retry.
RETRY_PAUSE_SECONDS = 5


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
        self._normal_interval = timedelta(seconds=interval)
        self._retry_delay = RETRY_INTERVAL
        self._auth_failures = 0
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

    async def _read_once(self) -> dict[int, float]:
        values = await self.api.read_registers(POLL_REGISTERS)
        if REG_RUNNING_MODE not in values:
            raise DuxConnectionError("Heater returned no data")
        return values

    async def _async_update_data(self) -> dict[int, float]:
        try:
            try:
                values = await self._read_once()
            except DuxConnectionError as err:
                # One immediate retry with a fresh login and session.
                _LOGGER.debug("Poll failed (%s), retrying with a fresh login", err)
                self.api.reset()
                await asyncio.sleep(RETRY_PAUSE_SECONDS)
                values = await self._read_once()
        except DuxAuthError as err:
            self._auth_failures += 1
            if self._auth_failures >= AUTH_FAILURES_BEFORE_REAUTH:
                raise ConfigEntryAuthFailed(str(err)) from err
            self._schedule_retry()
            raise UpdateFailed(f"{err} (will retry)") from err
        except DuxError as err:
            self._schedule_retry()
            raise UpdateFailed(str(err)) from err

        self._auth_failures = 0
        self._retry_delay = RETRY_INTERVAL
        self.update_interval = self._normal_interval
        return values

    def _schedule_retry(self) -> None:
        """Poll again soon instead of waiting the full interval (backs off)."""
        delay = min(self._retry_delay, self._normal_interval.total_seconds())
        self.update_interval = timedelta(seconds=delay)
        self._retry_delay = min(self._retry_delay * 2, self._normal_interval.total_seconds())

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
