# Nightscout Extended v0.7.0

Read-only Home Assistant custom integration for Nightscout data.

## Endpoint model

- `/api/v1/status.json` — Nightscout version, units, thresholds and server settings
- `/api/v1/devicestatus.json` — AAPS/device status, pump, phone, predictions and AAPS configuration
- `/api/v1/entries.json` — glucose readings and history
- `/api/v1/treatments.json` — bolus/temp-basal/treatment history
- `/api/v1/profile.json` — active Nightscout profile, basal, sensitivity, carb ratio and targets

## Authentication

The API key is optional. When supplied, it is sent as the `API-SECRET` header. Leave it blank if the Nightscout server permits readable unauthenticated API requests.

## v0.7 highlights

- Separate parsing for each Nightscout endpoint.
- Optional API key in the config flow.
- Configurable history sizes.
- Correct parsing of the nested AAPS configuration object.
- Structured prediction parsing with targeted AAPS diagnostic parsing.
- Profile data sourced from `profile.json`.
- Treatment history used for bolus/treatment diagnostics.
- Pump and AAPS data remain read-only.
- Domain is `nightscout_extended`, so it can coexist with Home Assistant's official `nightscout` integration.

This integration does not control a pump or make treatment recommendations.
