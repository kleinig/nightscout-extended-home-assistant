# Nightscout Extended

A read-only HACS-style Home Assistant integration that extends the official Nightscout integration with advanced AAPS, pump and Nightscout diagnostics.

## Why this is a separate integration

Home Assistant already provides an official `nightscout` integration for basic CGM data. This project intentionally uses the separate `nightscout_extended` domain so it can coexist with the official integration.

## Features

- CGM glucose, delta and direction
- IOB, basal IOB, activity and COB
- Eventual BG and target BG
- AAPS algorithm/decision diagnostics
- Dynamic ISF and sensitivity diagnostics
- Prediction arrays as AAPS Decision attributes
- Pump reservoir, battery, status, profile and firmware
- Temp basal and last bolus
- AAPS phone/uploader status
- AAPS and Nightscout versions
- TIR/TBR/TAR/very-high statistics and GMI
- Configuration/threshold diagnostics
- Glucose/pump/reservoir/battery warning states
- Public Nightscout sites supported without an API secret

## Installation

1. Add this repository to HACS as a custom integration.
2. Install **Nightscout Extended**.
3. Restart Home Assistant.
4. Add **Nightscout Extended** from Settings → Devices & services.
5. Enter your Nightscout URL.
6. Leave API secret blank if your site permits public API reads.

## Existing v0.x users

v0.6 uses a new Home Assistant domain:

`nightscout_extended`

It does not conflict with Home Assistant's official `nightscout` integration. Remove the old custom `nightscout` integration before installing v0.6 if you previously installed this project's older versions.

## Safety

This integration is read-only monitoring and diagnostics. It does not issue dosing recommendations, alter AAPS settings, or control a pump.
