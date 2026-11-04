"""Load the integration in a real Home Assistant core with a fake cloud API."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.config_entries import ConfigEntryState

from custom_components.dux_hp import const as C
from custom_components.dux_hp.api import DuxAuthError

HUB = "1a8f3b4e97da11ed9d6c005056983573"

# Values from Roy's live heater, 2026-11-04
LIVE = {
    C.REG_RUNNING_MODE: 6146,
    C.REG_MODE_WANTED: 1,
    C.REG_BOOST_WANTED: 0,
    C.REG_T_TANK: 5920,
    C.REG_T_AIR: 1970,
    C.REG_T_EVAP: 1800,
    C.REG_RELAY_COMP: 0,
    C.REG_RELAY_RES: 0,
    C.REG_RELAY_FAN: 0,
    C.REG_ERROR: 0,
    C.REG_BOOST_SETPOINT: 6400,
    C.REG_AUTO_SETPOINT: 5900,
    C.REG_OUT_START: 0,
    C.REG_OUT_END: 0,
    C.REG_ENERGY_HP_TODAY: 4588,
    C.REG_ENERGY_RES_TODAY: 0,
}


class FakeHeater:
    """Mimics the cloud: writes change the state like the real heater did."""

    def __init__(self):
        self.state = dict(LIVE)
        self.writes: list[dict] = []

    async def read(self, regs):
        if regs == C.LIMIT_REGISTERS:
            return {C.REG_BOOST_SETPOINT_MIN: 5000, C.REG_BOOST_SETPOINT_MAX: 6500}
        return {r: self.state[r] for r in regs if r in self.state}

    async def write(self, values):
        self.writes.append(dict(values))
        if values.get(C.REG_BOOST_WANTED) == 1 and self.state[C.REG_T_TANK] < self.state[C.REG_BOOST_SETPOINT]:
            self.state.update({C.REG_RUNNING_MODE: 6306, C.REG_BOOST_WANTED: 1, C.REG_RELAY_RES: 1})
        if values.get(C.REG_BOOST_WANTED) == 0:
            self.state.update({C.REG_RUNNING_MODE: 6146, C.REG_BOOST_WANTED: 0, C.REG_RELAY_RES: 0})
        if C.REG_MODE_WANTED in values:
            m = values[C.REG_MODE_WANTED]
            self.state[C.REG_MODE_WANTED] = m
            base = {1: 3, 0: 1}[m]
            self.state[C.REG_RUNNING_MODE] = (self.state[C.REG_RUNNING_MODE] & ~(0x1F << 11)) | (base << 11) | 2
        if C.REG_BOOST_SETPOINT in values:
            self.state[C.REG_BOOST_SETPOINT] = values[C.REG_BOOST_SETPOINT]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def heater():
    fake = FakeHeater()
    with (
        patch("custom_components.dux_hp.api.DuxApi.login", AsyncMock()),
        patch("custom_components.dux_hp.api.DuxApi.session_check", AsyncMock()),
        patch("custom_components.dux_hp.api.DuxApi.read_registers", side_effect=fake.read),
        patch("custom_components.dux_hp.api.DuxApi.write_registers", side_effect=fake.write),
        patch("custom_components.dux_hp.coordinator.COMMAND_SETTLE_SECONDS", 0),
    ):
        yield fake


async def _setup(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=C.DOMAIN,
        unique_id=HUB,
        data={"email": "x@example.com", "password": "pw", "hub_id": HUB},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, heater):
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    s = hass.states
    assert s.get("sensor.dux_hp_tank_temperature").state == "59.2"
    assert s.get("sensor.dux_hp_air_temperature").state == "19.7"
    assert s.get("sensor.dux_hp_current_mode").state == "auto"
    assert s.get("switch.dux_hp_boost").state == "off"
    assert s.get("select.dux_hp_operating_mode").state == "auto"
    num = s.get("number.dux_hp_boost_target_temperature")
    assert num.state == "64.0"
    assert num.attributes["min"] == 50 and num.attributes["max"] == 65
    assert s.get("binary_sensor.dux_hp_compressor").state == "off"
    assert s.get("binary_sensor.dux_hp_problem").state == "off"
    energy = s.get("sensor.dux_hp_heat_pump_energy_today")
    assert energy.attributes["unit_of_measurement"] == "kWh"
    assert float(energy.state) == pytest.approx(4.588)


async def test_boost_on_off(hass: HomeAssistant, heater):
    await _setup(hass)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.dux_hp_boost"}, blocking=True)
    assert heater.writes[-1] == {C.REG_BOOST_WANTED: 1}
    assert hass.states.get("switch.dux_hp_boost").state == "on"
    assert hass.states.get("sensor.dux_hp_current_mode").state == "boost"
    assert hass.states.get("binary_sensor.dux_hp_element").state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.dux_hp_boost"}, blocking=True)
    # exactly what the app sent (and what Roy's live test sent)
    assert heater.writes[-1] == {C.REG_MODE_WANTED: 1, C.REG_BOOST_WANTED: 0}
    assert hass.states.get("switch.dux_hp_boost").state == "off"


async def test_boost_refused_when_tank_at_target(hass: HomeAssistant, heater):
    heater.state[C.REG_BOOST_SETPOINT] = 5900
    await _setup(hass)
    with pytest.raises(HomeAssistantError, match="Boost target"):
        await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.dux_hp_boost"}, blocking=True)
    assert heater.writes == []


async def test_set_boost_target_and_mode(hass: HomeAssistant, heater):
    await _setup(hass)
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": "number.dux_hp_boost_target_temperature", "value": 62}, blocking=True,
    )
    assert heater.writes[-1] == {C.REG_BOOST_SETPOINT: 6200}
    assert hass.states.get("number.dux_hp_boost_target_temperature").state == "62.0"

    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.dux_hp_operating_mode", "option": "eco"}, blocking=True,
    )
    assert heater.writes[-1] == {C.REG_MODE_WANTED: 0}
    assert hass.states.get("select.dux_hp_operating_mode").state == "eco"


async def test_auth_failure_starts_reauth(hass: HomeAssistant):
    with patch("custom_components.dux_hp.api.DuxApi.login", AsyncMock(side_effect=DuxAuthError("no"))):
        entry = MockConfigEntry(domain=C.DOMAIN, unique_id=HUB,
                                data={"email": "x@example.com", "password": "bad", "hub_id": HUB})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == "reauth" for f in flows)


async def test_config_flow(hass: HomeAssistant, heater):
    result = await hass.config_entries.flow.async_init(C.DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"email": "x@example.com", "password": "pw", "hub_id": HUB.upper()},
    )
    assert result["type"] == "create_entry"
    assert result["data"]["hub_id"] == HUB


async def test_refresh_button_and_default_interval(hass: HomeAssistant, heater):
    entry = await _setup(hass)
    assert entry.runtime_data.update_interval.total_seconds() == 1800
    heater.state[C.REG_T_TANK] = 5555
    await hass.services.async_call("button", "press", {"entity_id": "button.dux_hp_refresh"}, blocking=True)
    assert hass.states.get("sensor.dux_hp_tank_temperature").state == "55.55"


async def test_running_mode_decode():
    assert C.decode_running_mode(6146) == ("auto", None)
    assert C.decode_running_mode(6306) == ("auto", "boost")
