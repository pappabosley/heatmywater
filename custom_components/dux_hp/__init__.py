"""Dux HP heat pump water heater integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuxApi, DuxAuthError, DuxError
from .const import CONF_HUB_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import DuxCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type DuxConfigEntry = ConfigEntry[DuxCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DuxConfigEntry) -> bool:
    api = DuxApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_HUB_ID],
    )
    try:
        await api.login()
        await api.session_check(force=True)
    except DuxAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except DuxError as err:
        raise ConfigEntryNotReady(str(err)) from err

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = DuxCoordinator(hass, entry, api, interval)
    await coordinator.async_load_limits()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DuxConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: DuxConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
