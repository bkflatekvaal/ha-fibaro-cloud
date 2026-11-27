# Fibaro Cloud for Home Assistant

An unofficial integration that connects Home Assistant to your Fibaro / Yubii hub through the cloud. Useful for cabins and other homes where Home Assistant cannot reach the hub locally.

Both Home Assistant and the hub need internet access. If they are on the same network, consider the [official Fibaro integration](https://www.home-assistant.io/integrations/fibaro/).

This project is under active development and is not affiliated with Fibaro, Yubii, Nice or Home Assistant. HC3 Lite is the only hub model confirmed in live use so far.

## Installation

Requires Home Assistant **2026.11**. Earlier versions have not been verified.

1. Download this repository from [GitHub](https://github.com/bkflatekvaal/ha-fibaro-cloud).
2. Copy the `custom_components/fibaro_cloud` folder into your Home Assistant configuration's `custom_components` folder.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Fibaro Cloud**.

For Marketplace, add the repository URL using **Settings → Marketplace → Add from link**, then install and follow the restart prompt. Installation through Marketplace has not yet been verified; the integration is not listed in its catalog.

## Setup

1. Enter your Fibaro / Yubii **cloud account** username and password.
2. Select your hub.
3. Enter the **local hub username and password**. This user must have permission to access the devices you want to use.
4. Select the **main devices** to include in Home Assistant. Nothing is selected by default.

**Tip:** Give each **main device** a recognizable name in Fibaro Home Center, such as “Living room thermostat” or “Entrance light”. Naming the main device itself makes it easier to identify here, even if its individual endpoints already have names.

Supported sensors and controls are grouped under their main device. Device names follow Fibaro, while names you customize in Home Assistant are retained. Repeated battery readings are combined into one battery sensor per main device.

To change your selection, open the integration's **Configure / options**. New main devices must be selected manually. Removing a device from the selection also removes its entities; adding it back may not preserve their customizations.

## What is supported?

Depending on what your hub reports:

- Sensors, including temperature, humidity, power, energy and battery.
- Binary sensors, including motion, door/window and leak detection.
- Switches, lights, thermostats and covers.

Switch and thermostat control have been confirmed on HC3 Lite. Lights and covers have only been tested with simulated devices. Not every device or function is supported.

## Everyday use and troubleshooting

- Device states update about once a minute. Cloud delays can affect how quickly changes appear.
- Expired sessions are renewed automatically using your saved login details. If Home Assistant asks you to sign in again, check both your cloud and local hub credentials and follow the reauthentication prompt.
- If a command fails, check the device's actual state before trying again. Commands are never resent automatically.
- For connection problems, check internet access and confirm you can access the hub in Fibaro / Yubii. Cloud service changes can also interrupt access.
- Additional verification such as MFA or CAPTCHA may require action in the vendor's interface and is not automated by this integration.

Protect your Home Assistant configuration and backups: they contain your saved login details.

## Help and further reading

Report problems through [GitHub Issues](https://github.com/bkflatekvaal/ha-fibaro-cloud/issues). Include your Home Assistant and integration versions, hub model, and a short description. Never share passwords, cookies, configuration files, backups or raw hub responses. Review any logs or diagnostic files before attaching them.

For implementation details, see [authentication, diagnostics and limitations](docs/technical.md). For tests and development, see [CONTRIBUTING.md](CONTRIBUTING.md).
