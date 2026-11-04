"""Exercise the real HTTP client against a mocked server."""
from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.dux_hp import const as C
from custom_components.dux_hp.api import DuxApi, DuxAuthError

HUB = "0123456789abcdef0123456789abcdef"
DATA = f"{C.API_BASE}hubs/{HUB}/plugins/esp32/modules/esp32/devices/0/data"


async def test_login_read_write(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(f"{C.API_BASE}customers/connect/",
                        json={"status": "ok", "token": "T1", "customer": {"token": "T1"}})
    aioclient_mock.post(f"{C.NODE_BASE}/api/session/check",
                        json={"action": "session_check", "status": "ok"})
    aioclient_mock.get(f"{DATA}?register={C.REG_T_TANK},{C.REG_RUNNING_MODE}",
                       json={"data": [{"register": str(C.REG_T_TANK), "value": 5920},
                                      {"register": str(C.REG_RUNNING_MODE), "value": 6146}]})
    aioclient_mock.post(DATA, status=201, json={"status": "ok"})

    api = DuxApi(async_get_clientsession(hass), "e@x", "pw", HUB)
    vals = await api.read_registers([C.REG_T_TANK, C.REG_RUNNING_MODE])
    assert vals == {C.REG_T_TANK: 5920, C.REG_RUNNING_MODE: 6146}

    await api.write_registers({C.REG_BOOST_WANTED: 1})
    method, url, body, headers = aioclient_mock.mock_calls[-1]
    assert body == {"action": "command", "data": [{"register": 251658240, "value": 1}]}
    assert headers["Authorization"] == "Bearer T1"
    # login, session check, read, write (session check not repeated within 15 min)
    assert aioclient_mock.call_count == 4


async def test_token_refresh_on_401(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(f"{C.API_BASE}customers/connect/", json={"token": "T"})
    aioclient_mock.post(f"{C.NODE_BASE}/api/session/check", status=401)
    api = DuxApi(async_get_clientsession(hass), "e@x", "pw", HUB)
    with pytest.raises(DuxAuthError):
        await api.session_check(force=True)
    logins = [c for c in aioclient_mock.mock_calls if "customers/connect" in str(c[1])]
    assert len(logins) == 2  # first login + one retry, then gives up


async def test_bad_password(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(f"{C.API_BASE}customers/connect/", status=401)
    api = DuxApi(async_get_clientsession(hass), "e@x", "bad", HUB)
    with pytest.raises(DuxAuthError):
        await api.login()
