# Fibaro Cloud for Home Assistant

An **unofficial integration under active development** that connects Home Assistant to a Fibaro / Home Center hub through Fibaro / Yubii Cloud. It is useful for cabins, second homes, and other installations where Home Assistant cannot reach the hub on its local network.

This project is not affiliated with or endorsed by Fibaro, Yubii, Nice, or Home Assistant. Device support depends on the types, properties, and actions reported by your hub. It does not support every Fibaro device or provide feature parity with the official integration.

## Why use this?

The [official Fibaro integration](https://www.home-assistant.io/integrations/fibaro/) uses a local connection to the hub. Prefer that integration when local access meets your needs. Fibaro Cloud provides remote reads and device commands through the cloud instead, without requiring a direct connection from Home Assistant to the hub's LAN.

Both Home Assistant and the hub need working internet access, and the hub must be accessible through your Fibaro / Yubii account. The only hub model confirmed in live use so far is **HC3 Lite**; other models and firmware versions are unverified.

## Installation

### Manual installation

1. Download this repository from [GitHub](https://github.com/bkflatekvaal/ha-fibaro-cloud).
2. Copy only `custom_components/fibaro_cloud/` into your Home Assistant configuration directory, so the result is `<config>/custom_components/fibaro_cloud/manifest.json`. Avoid an extra nested directory.
3. Restart Home Assistant when you are ready to load the installed integration.
4. Open **Settings → Devices & services → Add integration → Fibaro Cloud**.

The code and compatibility tests target Home Assistant **2026.11** APIs and Python **3.14**. Earlier HA versions have not been verified. There are no extra integration-specific pip requirements; Home Assistant supplies the runtime dependencies.

### Marketplace custom repository

Once this repository is public, open **Settings → Marketplace → Add from link** and enter `https://github.com/bkflatekvaal/ha-fibaro-cloud`. Connect GitHub if prompted, then install Fibaro Cloud. Follow any restart prompt and add the integration under **Settings → Devices & services**.

See the [official Marketplace instructions](https://www.home-assistant.io/integrations/marketplace#custom-repositories). Installation through Marketplace has **not yet been verified**, and this project is not listed in its catalog. The repository includes the expected integration layout and the required metadata file, which is still named [`hacs.json`](https://contributors.home-assistant.io/marketplace/reference/hacs-json/) by Marketplace. No separate store installation is needed.

## Setup and device selection

1. Enter your Fibaro / Yubii **cloud account** username and password.
2. Select a hub from the account's reported hubs.
3. Enter the **local hub username and password** used to authorize hub API access. These are separate from cloud credentials, even if you happen to use the same values. The user needs permission to read and control the intended devices.
4. Select the **main devices** you want to expose in Home Assistant in a single selection step. The initial selection is empty.

All recognized entities belonging to a selected main device are included automatically, including supported entities discovered later. New main devices are not selected automatically. Use the integration's **Configure / options** flow to change the selection; saving reloads the integration. Deselecting a main device removes its registered entities, so reselecting it may not preserve customizations associated with removed entries.

Fibaro API endpoints/channels are grouped under their main physical device. The HA device name follows the main device name in Fibaro, while names explicitly set by the user in HA are retained. Individual entity names can still reflect endpoint names. Battery readings repeated across endpoints are consolidated into **one battery entity per main device**, if a battery property is reported. Invalid battery values such as `255` are shown as unknown.

Existing unique-ID formats and registry migrations preserve existing entity IDs for retained entities. When old duplicate battery entities are consolidated, one existing entity ID is kept and the duplicates are removed. Avoid removing and re-adding the integration merely to change device selection.

## Supported functions and testing

Capabilities are inferred from reported device types, properties, and advertised actions; availability on one device does not establish support for every model in its category.

| Platform / feature | Implemented behavior, where reported | Confirmed live testing |
| --- | --- | --- |
| Numeric sensors | Temperature, humidity, illuminance, power, energy, battery, voltage, current, frequency, pressure, CO₂ | No separate live validation confirmed |
| Binary sensors | Recognized motion, opening/door/window, water, smoke, heat, gas, CO and generic binary states | No separate live validation confirmed |
| Switches | On/off state and commands | User confirmed actual control via cloud on HC3 Lite |
| Lights | On/off; brightness and RGB/RGBW when advertised | Simulated hub only; no live validation |
| Climate | Reported temperature and setpoint; supported HVAC modes and setpoint commands | User confirmed actual thermostat control via cloud on HC3 Lite; all modes and variants unverified |
| Covers | Open/close; optional stop and position | Simulated hub only; no live validation |
| Grouping and diagnostics | Main-device grouping, selection, battery consolidation, supported-device count | Automated tests; no broader hardware certification |

The diagnostic device-count sensor counts supported main devices across the hub, including unselected ones. Its `selected_devices` attribute counts selected main-device IDs and `fibaro_api_objects` counts raw API objects. These numbers can differ substantially. This sensor is not a downloadable, automatically anonymized diagnostic report.

## Cloud behavior and limitations

- Updates are polled every **60 seconds**. Each snapshot checks the cloud session and reads hub information and the full device list, even when only a few devices are selected. There is no push subscription or configurable polling interval.
- After a successful command, the integration requests a refresh immediately and schedules another approximately two seconds later. State comes from the hub rather than an optimistic local update; cloud propagation can delay confirmation.
- Commands are serialized. A failed or timed-out write is **never automatically replayed**, because the hub may already have executed it. Check the actual state before manually retrying.
- Expired sessions can trigger a fresh login before a read or command. Authentication failures require credential verification / HA reauthentication. Interactive verification, MFA, CAPTCHA, or changed login flows are not handled by the integration.
- The client implements the remote-access web protocol using `home.fibaro.com/cmh/api/authorize`, `/cmh/api/session`, `/cmh/api/hc/list`, `id.cloud.fibaro.com/login`, and `home.fibaro.com/newProxyLite`. These are treated here as **undocumented web endpoints**: this project has no verified public API contract for them. This description comes from the client implementation, not a vendor compatibility guarantee. Cloud changes can break access without notice.
- Requests use HTTPS with a restricted destination allowlist and a default 30-second timeout per request. Local hub credentials authorize proxied API requests through the cloud. HA stores both cloud and local credentials in the configuration entry; protect HA's configuration and backups.
- Unsupported or disabled device objects are not exposed. Temperature sensors require a recognized unit; climate entities are unavailable without a recognized temperature unit. Hub objects marked dead are unavailable.
- Scenes, locks, events, tilt controls, schedules, and arbitrary hub actions are not implemented. No guarantee is made for every thermostat mode, RGBW variant, or cover calibration. Cloud polling is unsuitable as the sole source for time-critical or safety-critical automation.

## Troubleshooting and device reports

- **Cannot log in / authentication error:** verify the cloud account, remote hub availability, local hub credentials, and the local user's device permissions. Complete any interactive account verification in the vendor interface. Use HA's reauthentication prompt when offered; do not repeatedly submit commands to troubleshoot login.
- **No devices / missing entities:** open Configure and select the main device. A raw API object is not necessarily a supported physical device or entity. Check the device-count attributes, type, properties and advertised actions.
- **Unavailable / delayed state:** check internet access at both sites and hub availability in the vendor interface. Allow for polling and cloud latency. A timed-out command might have succeeded.
- **Integration not listed:** check the installation path, restart after installation, and inspect HA logs for load errors and version incompatibilities.

Report issues at the [project issue tracker](https://github.com/bkflatekvaal/ha-fibaro-cloud/issues). Include HA and integration versions, hub model and firmware, expected and observed behavior, and whether the issue concerns discovery, reading, or commands.

For missing device types, include a **small, manually anonymized** JSON excerpt containing `type`, `baseType`, `parentId`, `actions`, and only relevant `properties` (for example `value`, `unit`, battery or thermostat fields). Replace IDs consistently so parent/child and linked-temperature relationships remain understandable, and replace names with invented labels. Use synthetic values where possible.

Never attach full `/api/devices` responses, `.storage`, configuration entries, backups, credentials, serial numbers, account identifiers, IP/MAC addresses, location/room names, cookies, authorization headers, session keys, or complete proxy URLs. Review logs before sharing: third-party tracebacks can reveal data even when this client's errors are sanitized. There is no automatic diagnostic redaction/export feature.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for dependencies, safe test commands, and the publication checklist. Tests use synthetic data and mocked hub I/O; live controls are not part of the test suite.

## License

The existing repository license is [MIT](LICENSE), with the copyright attribution recorded there. No additional vendor affiliation or ownership is implied.
