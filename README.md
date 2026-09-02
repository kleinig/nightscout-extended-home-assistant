# Nightscout Home Assistant Integration v0.5.0

A HACS-style Home Assistant custom integration for Nightscout.

## v0.5 highlights

- More robust AAPS `enacted` / `suggested` / `requested` parsing
- Current glucose and delta from Nightscout entries
- 24-hour/loaded-window glucose statistics
- Time in range / below range / above range
- GMI estimate
- IOB, basal IOB, activity and COB
- AAPS decision diagnostics
- Prediction arrays exposed as attributes
- Pump reservoir, battery, status, profile, firmware and temp basal
- Last bolus details from both pump status and treatments
- AAPS phone/uploader information
- AAPS and Nightscout versions
- AAPS configuration diagnostics
- Warning/critical binary sensors
- Public Nightscout sites supported without an API secret
- Monitoring/diagnostics only; no dosing or pump-control commands

## Installation

1. Add the repository to HACS as a custom integration repository.
2. Install **Nightscout**.
3. Restart Home Assistant.
4. Add **Nightscout** from Settings → Devices & services.
5. Enter your Nightscout URL.
6. Leave API secret blank if your site allows public API reads.

## Safety

This integration is read-only monitoring. It does not issue treatment recommendations, change AAPS settings, or control a pump.
