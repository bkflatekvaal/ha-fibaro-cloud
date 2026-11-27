# Integration branding

The display name is **FIBARO / Yubii Cloud**. The integration domain remains
`fibaro_cloud` and the repository remains `ha-fibaro-cloud`. Existing hub titles,
unique IDs and entity IDs are unchanged.

The icon combines the recognizable FIBARO roof/monogram with a blue cloud badge
to identify this unofficial cloud integration. It is not an official FIBARO,
Yubii or Nice logo or endorsement. The underlying FIBARO mark belongs to its
respective owner; the project's MIT license does not grant trademark rights.

Reference: [FIBARO icon in Home Assistant's brands repository](https://github.com/home-assistant/brands/blob/master/core_integrations/fibaro/icon%402x.png).
The derivative icons were produced with the built-in ImageGen tool and resized
to Home Assistant's PNG dimensions using Pillow.

Final design brief: preserve the FIBARO roof and monogram, omit the small text
and registration mark, and add a blue cloud with a white outline at the lower
right. Use a transparent background for the black symbol. The dark-theme
variant uses a white symbol on charcoal; transparent white exports were
discarded because they had visible artifacts.

Files are shipped inside `custom_components/fibaro_cloud/brand/`:

- `icon.png` and `icon@2x.png`: 256 and 512 pixels, respectively.
- `dark_icon.png` and `dark_icon@2x.png`: distinct dark-theme versions.

There are no duplicate logo files: Home Assistant falls back to the icon.
See [Home Assistant's brand image requirements](https://contributors.home-assistant.io/core/integrations/brands/).

The exports are trimmed to the artwork bounds and normalized to square icons.
PNG files are losslessly compressed and have no embedded metadata. Transparency
is preferred by Home Assistant, not required; the dark variant retains its
charcoal background. The branding tests enforce the filenames, dimensions,
absence of duplicate images, and consistent names in Marketplace and HA.
These checks run in the existing test workflow; they do not constitute a full
hassfest or Marketplace catalog approval.
