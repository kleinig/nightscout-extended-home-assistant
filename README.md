# Nightscout Home Assistant Integration

A HACS-style custom Home Assistant integration for a Nightscout site.

## Features

- Nightscout status/version
- Current glucose in mg/dL and mmol/L
- Delta, direction, average, SD and CV
- Glucose data age
- Eventual BG, target BG and AAPS prediction diagnostics
- IOB, basal IOB, insulin activity and COB
- AAPS decision diagnostics (read-only)
- Dynamic ISF and sensitivity diagnostics
- Pump reservoir, battery, status, profile and firmware
- Temp basal and last bolus information
- AAPS uploader battery/charging/device
- Daily treatment totals
- AAPS configuration/threshold diagnostics
- Binary sensors for glucose state, closed loop, pump/uploader state and warnings

## Installation

### HACS custom repository

1. Add this repository as a custom integration repository in HACS.
2. Select **Integration**.
3. Install **Nightscout**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **Nightscout**.

The integration supports Nightscout sites that do not require an API secret.

## Important

This integration is for monitoring and diagnostics. It does not send dosing commands to AAPS or a pump and does not provide treatment recommendations.

## Data

The integration reads Nightscout API endpoints including status, devicestatus, entries, treatments and profile.
