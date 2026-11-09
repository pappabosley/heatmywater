# Dux HP (Cotherm / Linkio) cloud API – findings

Source: decompiled `libapp.so` (Flutter, Dart 3.9.2) from the Dux HP app (net.linkio.dux), cross-checked against a logcat capture of a Boost on/off cycle (2026-11-03).
Status: **read path confirmed by log; login and write format recovered from code but not yet tested live.**

## Hosts
- Django API: `https://django-staging-elasticbeanstalk.cotherm.lab-io.net/api/v1/` (app default; a heater record can override the host)
- Node API: `https://nodejs-staging-elasticbeanstalk.cotherm.lab-io.net`
- Dev hosts also exist in the app (`django-dev-…`, `nodejs-dev-…`) – not used in production.

## Auth
- `POST {django}/api/v1/customers/connect/` with JSON `{"email": "...", "password": "..."}`
- Response contains `customer` → user object with `token` (also email, first_name, last_name, phone, address, city, zipcode, country, manufacturer_id).
- All further calls: `Authorization: Bearer <token>`, `Content-Type: application/json`.

## Session
- `POST {node}/api/session/check` with `{"hub": "<hub id>"}` – called before polling.

## Read registers
- `GET {django}/api/v1/hubs/<hub>/plugins/esp32/modules/esp32/devices/0/data?register=<id>,<id>,...`
- Response: `{"data": [{"register": "<id>", "value": <num>}, ...]}`
- App polls ~every 10 s.

## Write registers
- `POST {django}/api/v1/hubs/<hub>/plugins/esp32/modules/esp32/devices/0/data`
- Body: `{"action": "command", "data": [{"register": <id>, "value": <num>}, ...]}`

## Commands (from Heater model code)
| Action | Writes |
|---|---|
| Boost on | `BOOST__mode_wanted` (0x0F000000) = 1; if Holiday active, also `OUT__end_timestamp` = 0 and `OUT__start_timestamp` = 0 |
| Boost off / set permanent mode | `MODES_MAN__mode_wanted` (0x0A000000) = mode; if Boost active, also `BOOST__mode_wanted` = 0; if Holiday active, also OUT timestamps = 0 |

`MODES_MAN__mode_wanted` values: 0 = Eco, 1 = Auto, 2 = Manual, 3 = Smart, 5 = Cold.
Holiday = `OUT__start_timestamp` / `OUT__end_timestamp` (Unix timestamps; 0 = none).

## Mode enums in the app
- NormalMode: unknown 0, frostProtection 1, autoStandard 2, autoPerformance 3, autoEconomic 4, autoEcologic 5, eco 6, manual 7, smart 8, cold 9, error 10
- TemporaryFuncMode: rescue 0, maintenance 1, boost 2, holidays 3, antiLegionella 4, pv 5

### `MODE_MAN__running_mode` bitfield (from `HeaterValues._parseMode`)
| Bits | Meaning |
|---|---|
| 5 | temporary mode active |
| 6–10 | temporary mode id: 0 rescue, 1 maintenance, 2 boost, 3 holiday, 4 anti-legionella, 5 PV |
| 11–15 | base mode id: 0 frost protection, 1 eco, 2 smart, 3 auto standard, 4 auto performance, 5 auto economic, 6 auto ecologic, 7 manual, 8 cold |
| 21 | flag (meaning unknown) |
| 0, 1, 2–4, 16–20 | parsed by app, meaning unknown |

Checked: 0x1802 = auto (standard); 0x18A2 = auto (standard) + boost active.
Note the running-mode ids differ from the `mode_wanted` write values.

## Live test 2026-11-04 (read-only) – confirmed
- Login returns `{"status", "token", "customer"}`; token also inside `customer`.
- session/check → `{"action":"session_check","status":"ok"}`
- Tank top/bottom sensors read 0 on this unit (not fitted). Middle sensor is the tank temperature.
- `STATS__energy_pac_day_Wh_p` = 4588. Still to confirm whether this is today so far or the previous day.

## Units
- Temperatures and setpoints: °C × 100 (5699 = 56.99 °C)
- Energy: `STATS__energy_pac_day_Wh_p` (heat pump) and `STATS__energy_res_day_Wh_p` (element), Wh – semantics to confirm
- Consumption history: `GET {django}/api/v1/hub/<hub>/consumption?start_timestamp=..&end_timestamp=..` → items with `timestamp`, `resistor`, `thermal_pump`

## Other
- Device has an ESP32; app also supports BLE (used for pairing/Wi-Fi setup; Linkio LMS/LMP framing).
- Full register map (224 registers): `register_map.csv`.
