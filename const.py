"""Constants for the Dux HP integration.

Register IDs and value encodings were recovered from the Dux HP Android app
(net.linkio.dux, Cotherm/Linkio) and confirmed against a live heater.
"""
from __future__ import annotations

DOMAIN = "dux_hp"

API_BASE = "https://django-staging-elasticbeanstalk.cotherm.lab-io.net/api/v1/"
NODE_BASE = "https://nodejs-staging-elasticbeanstalk.cotherm.lab-io.net"

CONF_HUB_ID = "hub_id"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 1800  # seconds (30 min); use the Refresh button for an immediate update
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 86400
SESSION_CHECK_INTERVAL = 900  # seconds between /api/session/check calls

# How long to wait after a command before checking the heater acted on it.
COMMAND_SETTLE_SECONDS = 8

# --- Registers (id -> meaning) ---------------------------------------------
REG_RUNNING_MODE = 0x0A000004   # bitfield, see decode_running_mode()
REG_MODE_WANTED = 0x0A000000    # write: base mode (MODE_WANTED_VALUES)
REG_BOOST_WANTED = 0x0F000000   # write: 1 = start boost, 0 = stop
REG_BOOST_SETPOINT = 0x0F000001  # degC x 100
REG_BOOST_SETPOINT_MIN = 0x0F000002
REG_BOOST_SETPOINT_MAX = 0x0F000003
REG_AUTO_SETPOINT = 0x17000000  # degC x 100
REG_T_TANK = 0x07010000         # tank (middle) sensor, degC x 100
REG_T_AIR = 0x07000000          # fan air inlet, degC x 100
REG_T_EVAP = 0x07020000         # evaporator, degC x 100
REG_RELAY_COMP = 0x02000000
REG_RELAY_RES = 0x02000002      # electric element
REG_RELAY_FAN = 0x02000004
REG_ERROR = 0x09000001          # ERROR_BITS__global_state
REG_OUT_START = 0x10000001      # holiday start (unix ts, 0 = none)
REG_OUT_END = 0x10000002        # holiday end (unix ts, 0 = none)
REG_ENERGY_HP_TODAY = 0x1B000000   # Wh, today so far (heat pump)
REG_ENERGY_RES_TODAY = 0x1B000001  # Wh, today so far (element)

POLL_REGISTERS: list[int] = [
    REG_RUNNING_MODE,
    REG_MODE_WANTED,
    REG_BOOST_WANTED,
    REG_BOOST_SETPOINT,
    REG_AUTO_SETPOINT,
    REG_T_TANK,
    REG_T_AIR,
    REG_T_EVAP,
    REG_RELAY_COMP,
    REG_RELAY_RES,
    REG_RELAY_FAN,
    REG_ERROR,
    REG_OUT_START,
    REG_OUT_END,
    REG_ENERGY_HP_TODAY,
    REG_ENERGY_RES_TODAY,
]

# Read once at start-up (not needed every poll).
LIMIT_REGISTERS: list[int] = [REG_BOOST_SETPOINT_MIN, REG_BOOST_SETPOINT_MAX]
BOOST_SETPOINT_FALLBACK = (50.0, 70.0)

# Values written to REG_MODE_WANTED (from the app's Heater model).
MODE_WANTED_VALUES: dict[str, int] = {
    "eco": 0,
    "auto": 1,
    "manual": 2,
    "smart": 3,
    "cold": 5,
}
# Modes offered in the select entity (the Dux HP app exposes Auto and Eco).
SELECTABLE_MODES = ["auto", "eco"]

# running_mode bits 11-15
BASE_MODES: dict[int, str] = {
    0: "frost_protection",
    1: "eco",
    2: "smart",
    3: "auto",              # auto standard
    4: "auto_performance",
    5: "auto_economic",
    6: "auto_ecologic",
    7: "manual",
    8: "cold",
}
# running_mode bits 6-10 (valid when bit 5 is set)
TEMP_MODES: dict[int, str] = {
    0: "rescue",
    1: "maintenance",
    2: "boost",
    3: "holiday",
    4: "anti_legionella",
    5: "pv",
}

CURRENT_MODE_OPTIONS = sorted(set(BASE_MODES.values()) | set(TEMP_MODES.values()) | {"unknown"})


def decode_running_mode(value: int | float | None) -> tuple[str, str | None]:
    """Return (base_mode, temporary_mode or None) from MODE_MAN__running_mode."""
    if value is None:
        return "unknown", None
    v = int(value)
    base = BASE_MODES.get((v >> 11) & 0x1F, "unknown")
    temp = TEMP_MODES.get((v >> 6) & 0x1F, "unknown") if (v >> 5) & 1 else None
    return base, temp
