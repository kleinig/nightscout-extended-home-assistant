# Nightscout Home Assistant

A broad Home Assistant integration for Nightscout, with optional AAPS/OpenAPS/pump data when those fields are present.

## Data sources

The integration reads:
- `/api/v1/status.json`
- `/api/v1/devicestatus.json`
- `/api/v1/entries.json`
- `/api/v1/treatments.json`
- `/api/v1/profile.json` (optional)

## Entity groups

### Glucose
BG mg/dL and mmol/L, delta, direction, average, SD, CV, data age, eventual BG, target BG and prediction curves.

### Therapy
IOB, basal IOB, activity, COB, ISF, dynamic sensitivity, sensitivity ratio, carb sensitivity, insulin required and carb impact.

### AAPS/OpenAPS
Algorithm, dynamic ISF, SMB, dosing decision/reason, requested temp basal, delivery state and prediction arrays.

### Pump
Reservoir, battery, basal rate, temp basal, last bolus, profile, status and firmware.

### Uploader
Phone battery, charging, device and communication age.

### Configuration
Pump/APS type, AAPS version, units, safety limits, glucose marks, reservoir/battery warning thresholds and sensitivity settings.

### Statistics
History-window insulin, bolus and carb totals plus average daily insulin/carbs and glucose statistics.

## Safety

Monitoring only. This integration does not control a pump, issue dosing commands or make treatment recommendations.

## Installation

Copy `custom_components/nightscout` into your Home Assistant `config/custom_components/` directory, or add the repository to HACS as a custom integration. Restart Home Assistant and add **Nightscout** under Settings → Devices & services.

Configure the base URL, e.g. `https://your-nightscout.example.com`.

The integration is designed to tolerate missing optional Nightscout/AAPS fields rather than fabricating values.
