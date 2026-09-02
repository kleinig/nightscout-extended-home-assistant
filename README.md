# Nightscout AAPS for Home Assistant

A Home Assistant custom integration that reads pump and AAPS status from a publicly accessible Nightscout instance.

## Features

- Insulin reservoir in units
- Reservoir percentage
- Pump battery
- Pump closed-loop/status state
- Active AAPS profile
- Base basal rate
- Temporary basal rate and remaining time
- Last bolus amount
- AAPS phone/uploader battery
- Nightscout pump data age
- Average daily insulin usage
- Estimated reservoir remaining in hours and days
- Reservoir low/critical binary sensors
- Pump battery low binary sensor
- AAPS phone battery low binary sensor
- Stale Nightscout data binary sensor

## No API secret required

This integration uses the Nightscout REST API. If `/api/v1/devicestatus.json` is publicly readable on your instance, no API secret or token is required.

## Installation with HACS

1. Open HACS.
2. Select **Integrations**.
3. Add this repository as a custom repository if it is not yet in HACS.
4. Search for **Nightscout AAPS**.
5. Install it.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add Integration**.
8. Search for **Nightscout AAPS**.

## Configuration

Enter your Nightscout URL, for example:

`https://kleinig.nightscoutpro.com`

The integration defaults to a 300 U cartridge and 40 U/day fallback usage.

### Dynamic daily usage

The integration requests recent Nightscout device-status history and estimates average daily insulin usage from decreases in the pump reservoir.

Upward reservoir jumps are treated as cartridge changes/refills and are not counted as insulin consumption.

If there is insufficient valid reservoir history, the configured fallback daily usage is used.

## Safety

This integration is intended for monitoring and display. Do not use it as the sole source for insulin dosing decisions. Verify pump status and reservoir directly on the pump/AAPS when needed.

## Data source

Nightscout API v1 device status endpoint.
