# Nightscout Extended

Home Assistant custom integration for read-only monitoring of Nightscout data, including glucose, AAPS status, pump status, treatment statistics, predictions, profile data and configuration.

## Version
0.8.4

## Nightscout endpoints
- `/api/v1/status.json`
- `/api/v1/devicestatus.json`
- `/api/v1/entries.json`
- `/api/v1/treatments.json`
- `/api/v1/profile.json`

API key is optional. No pump commands or treatment actions are performed by this integration.

## Installation
Install the `custom_components/nightscout_extended` directory through HACS or manually copy it into `/config/custom_components/`.


### 0.8.4 connection-flow fix

The setup flow now performs a lightweight connection test against only:
- `/api/v1/status.json`
- `/api/v1/entries.json?count=1`

It no longer runs the complete data coordinator during setup, so an unrelated optional
Nightscout endpoint cannot prevent the integration from being added. API-key errors and
invalid responses are reported separately, and the integration supports reconfiguration.


### Unit preferences
The integration Options flow lets you choose mmol/L or mg/dL for preferred glucose sensors and mmol/L/U or mg/dL/U for insulin sensitivity. Insulin-to-carb ratio (IC / Carb Ratio) is always exposed as g/U.


## v0.8.5

- Added CAGE / SAGE / IAGE / BAGE-style age sensors:
  - Cannula Age
  - CGM Sensor Age
  - Insulin Cartridge Age
  - Pump Battery Age
- Added timestamp sensors showing the last change event used by each timer.
- Age timers are calculated from Nightscout treatment events:
  - Site Change / Cannula Change
  - Sensor Change / Sensor Start
  - Insulin Change / Cartridge Change
  - Pump Battery Change / Battery Change
- Added AAPS warning and critical thresholds as sensor attributes.
- Options changes now automatically reload the integration.
- Fixed handling of `profile.json` when Nightscout returns historical profiles as a list.
- Improved selection of the newest AAPS devicestatus record.
