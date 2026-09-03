# Nightscout Extended

A community Home Assistant custom integration for **Nightscout** that
keeps the primary blood glucose experience familiar while exposing
substantially more of the data Nightscout can provide.

Nightscout Extended is designed as a **true extended integration**
rather than an AAPS-only integration. Core Nightscout concepts remain
first-class Home Assistant entities, while source-specific data such as
AAPS/OpenAPS is separated into diagnostic entities so the integration
can be expanded to support other ecosystems, including Loop, without
making the primary entity set source-dependent.

> **Medical / safety notice:** This project is a software integration
> for displaying and automating around data retrieved from Nightscout.
> It is **not a medical device**, does not validate the correctness of
> diabetes-management data, and must not be relied upon for diagnosis,
> treatment, insulin dosing, or other medical decisions. Always verify
> critical values against an appropriate source/device and follow your
> clinical care plan.

------------------------------------------------------------------------

## Current release

**v1.2.1 — correctness and data-normalization release**

This release audits glucose thresholds, profile units, AAPS units, glucose deltas/ticks, boolean parsing, Socket.IO delta merging, timestamps, and age display. Source values are normalized once internally before Home Assistant display-unit conversion.

## Features

### Blood glucose compatibility

The primary **Blood Glucose** sensor is deliberately kept simple and
compatible with the normal Home Assistant Nightscout experience:

-   Current Nightscout glucose value.
-   Selectable display in `mg/dL` or `mmol/L`.
-   `device` attribute.
-   `date` attribute.
-   `delta` attribute.
-   `direction` attribute.
-   Direction-aware icon.
-   Current reading is sourced from Nightscout glucose entries rather
    than an AAPS-only feed.

This means you can use the primary glucose entity in dashboards and
automations without having to understand which uploader, pump or
algorithm produced the data.

### Extended Nightscout data

Depending on what your Nightscout instance publishes, the integration
can expose information including:

-   Glucose delta and direction.
-   Glucose reading age.
-   Sensor age.
-   Cannula age.
-   Insulin cartridge age.
-   Pump battery age.
-   Insulin on Board (IOB).
-   Basal IOB.
-   Bolus IOB.
-   Carbs on Board (COB).
-   Eventual BG.
-   Insulin required.
-   Sensitivity ratio.
-   Variable sensitivity.
-   Current insulin sensitivity.
-   Carb ratio.
-   DIA.
-   Basal profile.
-   Current/base basal.
-   Temporary basal rate.
-   Temporary basal percentage.
-   Temporary basal remaining.
-   Last bolus amount.
-   Pump reservoir.
-   Pump battery.
-   Pump status.
-   Pump manufacturer/model/device information.
-   Uploader battery and charging status.
-   Nightscout profile information.
-   OpenAPS/AAPS predictions.
-   OpenAPS/AAPS dosing information.
-   AAPS decision information.
-   AAPS suggested and enacted values.
-   Dynamic ISF information.
-   SMB information.
-   Meal Assist information.
-   Carb Impact and UAM information.
-   AAPS Autosens and Autosens-in-algorithm information.
-   AAPS ISF for Calculator and Carbs Absorption.
-   MMTune information.
-   AAPS delivery status.
-   Additional Nightscout device/treatment information.

The exact entities available depend on what your Nightscout server and
uploader actually publish.

------------------------------------------------------------------------

## Design philosophy

Nightscout supports multiple data sources and treatment ecosystems. A
Nightscout instance may contain information from AAPS, OpenAPS, Loop,
xDrip and pump integrations at different times.

Nightscout Extended therefore separates data into two broad groups.

### Main entities

Main entities represent concepts that are useful independently of a
particular algorithm or uploader.

Examples:

-   Blood Glucose
-   BG Delta
-   BG Direction
-   IOB
-   COB
-   Eventual BG
-   Insulin Required
-   Pump Status
-   Pump Reservoir
-   Pump Battery
-   Base Basal Rate
-   Temp Basal Rate
-   Temp Basal Percentage
-   Profile / ISF / Carb Ratio
-   Sensor, cannula, cartridge and pump ages

### Diagnostic entities

Entities explicitly tied to a particular treatment algorithm or
implementation are marked **Diagnostic**.

Examples:

-   AAPS Suggested Units
-   AAPS Enacted Units
-   AAPS Decision
-   AAPS Decision Reason
-   AAPS Suggested Sensitivity Ratio
-   AAPS Enacted Sensitivity Ratio
-   AAPS Dynamic ISF
-   AAPS Meal Assist
-   AAPS SMB
-   AAPS MMTune
-   AAPS Delivery Received
-   AAPS Phone Charging
-   other explicitly AAPS-specific values

This is intentional. It keeps the integration useful if your Nightscout
setup changes from AAPS to another ecosystem.

------------------------------------------------------------------------

## Real-time updates

Nightscout Extended supports Nightscout's Socket.IO data stream in
addition to REST API retrieval.

The integration uses the REST API to establish and recover state, then
consumes live Nightscout updates when available.

This allows changes such as:

-   new glucose readings,
-   treatment updates,
-   device-status changes,
-   OpenAPS/AAPS updates,
-   retrospective device-status updates,
-   Nightscout alarm notifications

to reach Home Assistant without relying exclusively on periodic polling.

If the live connection is unavailable, REST data remains the recovery
path.

### Authentication

The integration supports Nightscout authentication using the configured
API key/token.

For API-secret based Nightscout installations, the API secret is hashed
as required by Nightscout rather than sent as the plaintext secret.

For token/JWT-based installations, the token is used for authenticated
requests.

------------------------------------------------------------------------

## Requirements

-   Home Assistant with support for custom integrations.
-   A working Nightscout instance.
-   A Nightscout URL reachable from Home Assistant.
-   An API secret or token if your Nightscout instance requires
    authentication.
-   Nightscout data being uploaded by your CGM/pump/uploader.

The integration does not itself collect CGM data. It reads data that
already exists in Nightscout.

------------------------------------------------------------------------

# Installation

## HACS --- recommended

Nightscout Extended is intended to be distributed as a HACS custom
integration.

### 1. Add the repository

In Home Assistant:

1.  Open **HACS**.
2.  Open **Integrations**.
3.  Select the three-dot menu.
4.  Select **Custom repositories**.
5.  Enter the GitHub repository URL for Nightscout Extended.
6.  Select **Integration** as the category.
7.  Add the repository.

> If the repository is already listed by HACS, you can simply search for
> **Nightscout Extended** and install it.

### 2. Install

Search for **Nightscout Extended**, open the integration, and select
**Download**.

Restart Home Assistant after installation if HACS requests it.

### 3. Add the integration

Go to:

**Settings → Devices & services → Add Integration**

Search for:

**Nightscout Extended**

Enter:

-   **Nightscout URL** --- the base URL of your Nightscout site.
-   **API key** --- your Nightscout API secret/token when required.
-   **Glucose entries to retrieve** --- the amount of recent glucose
    history to retrieve during startup/recovery.

The integration will then create the available sensors and binary
sensors.

------------------------------------------------------------------------

# Manual installation

1.  Download the latest release.
2.  Copy:

``` text
custom_components/nightscout_extended
```

into:

``` text
/config/custom_components/nightscout_extended
```

Your Home Assistant configuration should contain:

``` text
/config/
└── custom_components/
    └── nightscout_extended/
        ├── __init__.py
        ├── binary_sensor.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── manifest.json
        ├── sensor.py
        └── translations/
```

3.  Restart Home Assistant.
4.  Add **Nightscout Extended** from the Integrations page.

------------------------------------------------------------------------

# Configuration

The integration uses Home Assistant's UI config flow.

## Nightscout URL

Enter the base URL of the Nightscout instance.

Examples:

``` text
https://nightscout.example.com
```

or:

``` text
https://my-nightscout.example.com
```

Do not normally include the `/api/v1` path; the integration builds the
required API endpoints itself.

## API key

Enter the API secret or token required by your Nightscout installation.

If your Nightscout instance allows unauthenticated read access, the API
key may be left blank.

For security, avoid posting your API secret in Home Assistant logs,
screenshots, GitHub issues or public configuration files.

## Glucose history

The integration retrieves a configurable number of recent glucose
entries during REST bootstrap/recovery.

The default is:

``` text
288
```

This is approximately 24 hours when glucose data is recorded every five
minutes.

More history increases the amount of data transferred and processed
during startup.

------------------------------------------------------------------------

# Display units

Nightscout Extended supports user-selectable units for glucose-related
measurements.

## Glucose

Supported display units:

-   `mg/dL`
-   `mmol/L`

The conversion is performed for display; the underlying Nightscout data
remains represented according to the source data.

## Insulin sensitivity

The preferred ISF display unit can be configured separately.

This also affects related carbohydrate-sensitivity measurements where
appropriate.

## Ratios and percentages

Examples:

-   AAPS Autosens → `%`
-   AAPS Autosens in Algorithm → `%`
-   Sensitivity Ratio → `%`
-   Dynamic ISF Adjustment → `%`
-   Temp Basal Percentage → `%`
-   ISF for Calculator and Carbs Absorption → the configured ISF unit

### AAPS sensitivity diagnostics

Nightscout Extended exposes the AAPS sensitivity values when Nightscout
contains them. The integration prefers the structured AAPS/OpenAPS result
fields and uses the exact AAPS console labels only as a compatibility fallback.

- **AAPS Autosens** comes from the AAPS `Autosens ratio` diagnostic when
  available, otherwise the structured `sensitivityRatio` value.
- **AAPS Autosens in Algorithm** comes from the structured
  `sensitivityRatio` value supplied in the AAPS/OpenAPS algorithm result.
- **ISF for Calculator and Carbs Absorption** comes from the structured
  `isfMgdlForCarbs` field when present, otherwise the exact
  `isfMgdlForCarbs` console diagnostic.

The `isfMgdlForCarbs` field is explicitly expressed by AAPS in mg/dL/U and is
converted to the integration's selected ISF display unit. These are Diagnostic
entities because they describe AAPS-specific algorithm state rather than a
generic Nightscout profile setting.

Insulin-to-carbohydrate ratio remains expressed as:

``` text
g/U
```

------------------------------------------------------------------------

# Temporary basal handling

Nightscout Extended treats temporary basal information as a
time-dependent value.

While a temporary basal is active:

-   **Temp Basal Rate** reports the active temporary rate.
-   **Temp Basal Remaining** reports the remaining duration.
-   **Temp Basal Percentage** is calculated from the temporary rate
    relative to the base basal rate.

When the temporary basal expires:

-   **Temp Basal Rate** returns to the **Base Basal Rate**.
-   **Temp Basal Percentage** returns to `100%`.

The displayed temporary basal percentage is rounded to the nearest
**5%** by default.

For example:

``` text
1.05 U/h ÷ 2.10 U/h = 50%
```

produces:

``` text
50%
```

------------------------------------------------------------------------

# Age sensors

Age sensors are intentionally displayed as human-readable text rather
than decimal hours.

Examples:

``` text
5h 12m
```

``` text
42m
```

This applies to:

-   CGM Sensor Age
-   Cannula Age
-   Insulin Cartridge Age
-   Pump Battery Age

This avoids displays such as `5.2 h` and makes the values easier to read
in dashboards.

------------------------------------------------------------------------

# AAPS / OpenAPS support

Nightscout Extended can expose AAPS/OpenAPS information when it is
present in Nightscout device-status and related records.

This includes structured information from dosing decisions such as:

-   dosing sensitivity,
-   BG source,
-   COB,
-   deviation,
-   BGI,
-   ISF,
-   carb ratio,
-   target,
-   predicted BG values,
-   eventual BG,
-   insulin requirement,
-   sensitivity ratio,
-   IOB,
-   basal IOB,
-   requested basal rate,
-   requested duration,
-   SMB amount.

The **AAPS Decision Reason** entity does not place the entire long
decision explanation into the Home Assistant state.

Home Assistant entity states have a length limit, so the integration
keeps the state short and exposes the complete reason and structured
values as attributes.

This allows dashboards to display the full explanation without losing
data or generating state-length warnings.

------------------------------------------------------------------------

# Why AAPS entities are Diagnostic

Nightscout is not synonymous with AAPS.

A user may have:

-   AAPS uploading to Nightscout,
-   Loop uploading to Nightscout,
-   OpenAPS-derived records,
-   pump-only Nightscout data,
-   xDrip data,
-   or a mixture of sources.

For that reason, entities whose meaning is explicitly tied to AAPS are
marked as **Diagnostic**.

This does **not** mean they are unimportant.

It means they are implementation-specific rather than universal
Nightscout concepts.

The same approach leaves room for future Loop-specific diagnostic
entities without replacing or confusing the generic Nightscout entities.

------------------------------------------------------------------------

# Entity categories

The integration broadly exposes the following groups.

  Category       Examples
  -------------- -----------------------------------------------------
  Glucose        Blood Glucose, BG Delta, BG Direction, glucose age
  Nightscout     Variable Sensitivity, COB, Eventual BG, IOB
  Pump           Reservoir, battery, status, basal, temp basal
  Profile        Profile name, ISF, sensitivity, carb ratio, DIA
  Treatment      Bolus amount, treatment information, ages
  Predictions    Predicted BG series and associated values
  AAPS/OpenAPS   Decision, dosing, Dynamic ISF, SMB, Meal Assist
  Device         Uploader battery, charging, device information
  Diagnostics    Source-specific AAPS/OpenAPS implementation details

Entity availability depends on the records supplied by your Nightscout
instance.

------------------------------------------------------------------------

# Binary sensors

Nightscout Extended also provides binary information where a boolean
representation is more useful than a numeric sensor.

Examples include:

-   AAPS Delivery Received
-   AAPS Phone Charging
-   Dynamic ISF Active
-   AAPS Dynamic ISF Running
-   SMB Enabled
-   other Nightscout/device status indicators

AAPS-specific binary sensors are classified as Diagnostic.

------------------------------------------------------------------------

# Troubleshooting

## The integration cannot connect

Check:

1.  The Nightscout URL is correct.
2.  Home Assistant can reach the URL.
3.  HTTPS certificates are valid.
4.  Your reverse proxy allows API access.
5.  The API secret/token is correct.
6.  Nightscout authentication settings permit the requested API access.

Try opening the Nightscout site from the Home Assistant host/network if
possible.

------------------------------------------------------------------------

## Blood glucose is unavailable

Check that Nightscout is receiving current CGM entries.

The primary Blood Glucose sensor intentionally follows the current
Nightscout glucose entry rather than fabricating a value from AAPS
predictions.

If Nightscout has stopped receiving CGM data, the sensor may become
unavailable/stale.

------------------------------------------------------------------------

## AAPS values are unavailable

AAPS-specific values depend on AAPS/OpenAPS data actually being uploaded
to Nightscout.

Check:

-   AAPS is connected to Nightscout.
-   OpenAPS/device-status records are being uploaded.
-   The Nightscout instance has the relevant data.
-   Your Nightscout configuration has not disabled the relevant
    plugin/data.

The integration will not infer missing AAPS data from unrelated values.

------------------------------------------------------------------------

## Phone/uploader battery is unavailable

Uploader information is obtained from recent Nightscout device-status
records.

Depending on the uploader and Nightscout version, the value may appear
under different fields.

The integration checks the supported uploader battery representations
rather than assuming the most recent OpenAPS record contains the
uploader information.

------------------------------------------------------------------------

## Socket.IO live updates are not working

REST data should still provide bootstrap/recovery data.

If live updates are not arriving:

1.  Check the Home Assistant log for Nightscout Extended messages.
2.  Verify that your reverse proxy permits the required long-lived
    connection/polling traffic.
3.  Check that the Nightscout server supports its Socket.IO endpoint.
4.  Verify authentication.
5.  Check whether a firewall or proxy is terminating the connection.

The integration uses REST as a recovery path rather than depending
exclusively on the live connection.

------------------------------------------------------------------------

# Reverse proxy considerations

If Nightscout is behind nginx, Nginx Proxy Manager, Traefik, Cloudflare
or another reverse proxy, make sure the Nightscout API and Socket.IO
traffic can pass through correctly.

A proxy that permits normal web page access but blocks
long-lived/polling connections may result in:

-   Blood Glucose working,
-   historical data working,
-   but live updates failing.

If this occurs, test the REST API and Socket.IO connectivity
independently.

------------------------------------------------------------------------

# Privacy and security

Nightscout contains highly sensitive health-related information.

Treat your Nightscout URL, API secret/token and Home Assistant instance
accordingly.

Recommendations:

-   Use HTTPS.
-   Use a dedicated Nightscout token where supported.
-   Do not publish API secrets in GitHub issues.
-   Do not include secrets in screenshots.
-   Restrict access to your Home Assistant instance.
-   Review reverse-proxy access controls.
-   Avoid exposing Nightscout publicly unless you understand the
    security implications.
-   Remove secrets before sharing debug logs.

Nightscout itself documents authentication and API-secret behaviour in
its server configuration documentation.

------------------------------------------------------------------------

# Logging and diagnostics

When reporting an issue, include:

-   Home Assistant version.
-   Nightscout version.
-   Nightscout Extended version.
-   How Nightscout is hosted.
-   Whether AAPS/OpenAPS/Loop/xDrip or another uploader is being used.
-   Which entity is affected.
-   Relevant Home Assistant log messages.

Never include:

-   API secrets,
-   JWT tokens,
-   passwords,
-   private URLs containing credentials,
-   personal health information unless you have deliberately removed
    identifying information.

------------------------------------------------------------------------

# Compatibility

Nightscout Extended is designed around the Nightscout REST and Socket.IO
interfaces rather than a single uploader.

The integration can therefore work with Nightscout installations
receiving data from different ecosystems, provided the required records
are available.

The quality and availability of extended entities depend on the data
your Nightscout instance publishes.

------------------------------------------------------------------------

# Project structure

The Home Assistant integration lives at:

``` text
custom_components/nightscout_extended/
```

Important files:

  File                 Purpose
  -------------------- ----------------------------------------
  `__init__.py`        Integration setup and lifecycle
  `config_flow.py`     Home Assistant UI configuration
  `const.py`           Integration constants and defaults
  `coordinator.py`     REST, Socket.IO and data normalization
  `sensor.py`          Sensor entity definitions
  `binary_sensor.py`   Binary sensor entity definitions
  `manifest.json`      Home Assistant integration metadata
  `translations/`      Config-flow translations

Home Assistant custom integrations use the standard
`custom_components/<domain>` layout and require integration metadata in
`manifest.json`. See the Home Assistant developer documentation for
current integration requirements.

------------------------------------------------------------------------

# Development

## Local checkout

Clone the repository and copy the integration into:

``` text
/config/custom_components/nightscout_extended
```

Restart Home Assistant after making code changes, or use the appropriate
development/reload workflow.

## Testing

Before submitting changes:

-   Check Python syntax.
-   Restart Home Assistant.
-   Confirm the integration loads without errors.
-   Test config flow.
-   Test REST bootstrap.
-   Test Socket.IO updates.
-   Confirm entities are created.
-   Check entity units and device classes.
-   Check that Diagnostic entities remain correctly classified.
-   Test with missing optional Nightscout/AAPS fields.
-   Test both `mg/dL` and `mmol/L` display settings where relevant.

------------------------------------------------------------------------

# Versioning

Nightscout Extended follows semantic versioning where practical:

``` text
MAJOR.MINOR.PATCH
```

Examples:

-   `1.2.0` --- feature release.
-   `1.2.1` --- bug-fix release.
-   `2.0.0` --- potentially breaking release.

Changes affecting entity IDs, state formats, units or attributes should
be treated as potentially breaking because existing Home Assistant
dashboards and automations may depend on them.

------------------------------------------------------------------------

# Roadmap

Possible future improvements include:

-   Additional Loop-specific diagnostic entities.
-   Additional Nightscout plugin coverage.
-   More complete pump integrations.
-   Better device/source identification.
-   More structured prediction entities.
-   More comprehensive tests using captured Nightscout fixtures.
-   Improved Socket.IO reconnection and state reconciliation.
-   Additional translations.
-   Improved diagnostics for unsupported/missing Nightscout data.
-   Broader compatibility testing across Nightscout versions and
    uploaders.

------------------------------------------------------------------------

# Contributing

Contributions, bug reports and improvements are welcome.

When submitting a change:

1.  Explain what problem it solves.
2.  Include the affected Nightscout data structure where possible.
3.  Avoid including private health data or credentials.
4.  Keep source-specific functionality clearly separated from generic
    Nightscout functionality.
5.  Preserve compatibility with the primary Blood Glucose entity unless
    a breaking change is explicitly intended.
6.  Include testing information.

------------------------------------------------------------------------

# Acknowledgements

This project builds on the open-source Nightscout ecosystem and the Home
Assistant custom-integration architecture.

Nightscout provides the underlying diabetes data platform and APIs.

Home Assistant provides the home-automation platform and entity model.

AAPS/OpenAPS and other Nightscout-compatible projects provide data
structures that may be published through Nightscout.

This project is independent of and is not officially endorsed by:

-   Nightscout
-   Home Assistant
-   AndroidAPS (AAPS)
-   OpenAPS
-   Loop
-   xDrip

------------------------------------------------------------------------

# License

Nightscout Extended is released under the **MIT License**.

See [`LICENSE`](LICENSE) for the full license text.

Third-party software, libraries, trademarks and services referenced by
this project remain subject to their respective licenses and terms.
