# Dux HP for Home Assistant

Unofficial custom integration for Dux heat pump water heaters (EcoSmart range) that use the **Dux HP** app (Cotherm / Linkio cloud). It talks to the same cloud API as the app, so it works wherever the app works, and needs no extra hardware.

Not affiliated with Dux or Cotherm. The API is undocumented and could change without notice.

## What you get

| Entity | Notes |
|---|---|
| `sensor.dux_hp_tank_temperature` | Tank temperature (middle sensor) |
| `sensor.dux_hp_air_temperature` | Air inlet temperature |
| `sensor.dux_hp_evaporator_temperature` | Disabled by default |
| `sensor.dux_hp_current_mode` | Auto / Eco / Boost / Holiday / … |
| `sensor.dux_hp_heat_pump_energy_today` | kWh today, for the Energy dashboard |
| `sensor.dux_hp_element_energy_today` | kWh today, for the Energy dashboard |
| `button.dux_hp_refresh` | Read the heater now |
| `switch.dux_hp_boost` | Start/stop Boost |
| `number.dux_hp_boost_target_temperature` | Boost stops when the tank reaches this |
| `select.dux_hp_operating_mode` | Auto or Eco |
| `binary_sensor.dux_hp_compressor` / `_element` / `_fan` | What's running |
| `binary_sensor.dux_hp_boost_active` / `_holiday` / `_problem` | Status |
| Diagnostics | Auto setpoint, error code, raw running mode |

**Boost:** the heater ignores a Boost request if the tank is already at or above the Boost target. The switch checks this first and tells you to raise the Boost target, instead of silently doing nothing.

## Install

### HACS (custom repository)
1. HACS → ⋮ → Custom repositories → add `https://github.com/pappabosley/heatmywater`, type **Integration**.
2. Install **Dux HP**, then restart Home Assistant.

### Manual
Copy `custom_components/dux_hp` into your Home Assistant `config/custom_components/` folder and restart.

## Set up
Settings → Devices & services → Add integration → **Dux HP**, then enter:
- your Dux HP app email and password
- the **hub ID**: a 32-character hex ID. To find it, connect your phone with USB debugging, open the app, and run
  `adb logcat | findstr "api/v1/hubs"` (Windows) or `adb logcat | grep api/v1/hubs` (Linux/macOS).
  The ID is the part after `/hubs/`.

The heater is polled every **30 minutes** by default. You can change this under the integration's **Configure** button (10 s to 24 h). Press **Refresh** (`button.dux_hp_refresh`, also on the wall display dashboard) for an immediate reading. The integration also re-reads the heater automatically 8 s after any Boost, mode or target change.

## Shelly Wall Display dashboard
`dashboard/shelly_wall_display.yaml` is a one-column dashboard built from standard cards only. It has a tank gauge, a large Boost button, the Boost target, mode selection, the relay states and today's energy.

To use it, create a new dashboard, open the **Raw configuration editor**, paste the file in, then select that dashboard on the Wall Display.

## How it works
The integration polls the Cotherm cloud API (`/api/v1/hubs/<hub>/plugins/esp32/modules/esp32/devices/0/data`) for register values, and sends commands to the same endpoint. See `DUX_API_NOTES.md` and `register_map.csv` for the full protocol notes.
