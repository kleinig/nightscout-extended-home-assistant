# Nightscout Extended

Home Assistant custom integration for read-only monitoring of Nightscout data, including glucose, AAPS status, pump status, treatment statistics, predictions, profile data and configuration.

## Version
0.8.1

## Nightscout endpoints
- `/api/v1/status.json`
- `/api/v1/devicestatus.json`
- `/api/v1/entries.json`
- `/api/v1/treatments.json`
- `/api/v1/profile.json`

API key is optional. No pump commands or treatment actions are performed by this integration.

## Installation
Install the `custom_components/nightscout_extended` directory through HACS or manually copy it into `/config/custom_components/`.
