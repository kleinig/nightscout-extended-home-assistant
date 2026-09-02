# Nightscout Extended

Home Assistant custom integration for read-only monitoring of Nightscout data, including glucose, AAPS status, pump status, treatment statistics, predictions, profile data and configuration.

## Version
0.8.2.2

## Nightscout endpoints
- `/api/v1/status.json`
- `/api/v1/devicestatus.json`
- `/api/v1/entries.json`
- `/api/v1/treatments.json`
- `/api/v1/profile.json`

API key is optional. No pump commands or treatment actions are performed by this integration.

## Installation
Install the `custom_components/nightscout_extended` directory through HACS or manually copy it into `/config/custom_components/`.


### 0.8.2.2 connection-flow fix

The setup flow now performs a lightweight connection test against only:
- `/api/v1/status.json`
- `/api/v1/entries.json?count=1`

It no longer runs the complete data coordinator during setup, so an unrelated optional
Nightscout endpoint cannot prevent the integration from being added. API-key errors and
invalid responses are reported separately, and the integration supports reconfiguration.


### 0.8.2.2 parser fixes

- Selects the populated AAPS configuration record.
- Correctly maps configuration sensors to the parsed AAPS configuration.
- Parses scheduled profile values using the active profile timezone.
- Corrects average BG sensor mappings.
- Reads nested AAPS requested rate, duration and SMB values.
- Parses zero-temp diagnostics.
- Uses the profile timezone for timezone-less pump timestamps.
- Prefers the explicit AAPS configuration version.
