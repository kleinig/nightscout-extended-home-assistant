# Nightscout Extended

Home Assistant custom integration for read-only monitoring of Nightscout data, including glucose, AAPS status, pump status, treatment statistics, predictions, profile data and configuration.

## Version
1.0.0

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

### CAGE / SAGE / IAGE / BAGE

Version 0.8.6 listens to the Nightscout Socket.IO dataUpdate/retroUpdate stream and uses the latest valid Site Change, Sensor Change/Sensor Start, Insulin Change, and Pump Battery Change events for device-age sensors.


## REST + Socket.IO

Version 1.0.0 combines the REST API implementation with the Nightscout Socket.IO
live stream. REST provides initial/full state and periodic fallback; Socket.IO
provides live `dataUpdate`, `retroUpdate`, and `/alarm` notification events.

API secrets are SHA-1 hashed for the Socket.IO `secret` field, matching the
Nightscout web client. JWT-like tokens are sent as `token`.

The integration is read-only and does not send pump or treatment commands.

Live Socket.IO data includes glucose, AAPS device status, treatment
create/update/remove events, retro updates, alarm notifications, and
SAGE/BAGE/CAGE/IAGE age tracking.
