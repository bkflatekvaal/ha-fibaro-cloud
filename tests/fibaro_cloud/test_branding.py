"""Guard the brand-image rules used by Home Assistant and Marketplace."""
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "custom_components" / "fibaro_cloud"


def test_brand_images_have_supported_names_sizes_and_no_duplicates():
    brand = INTEGRATION / "brand"
    expected = {
        "icon.png": 256,
        "icon@2x.png": 512,
        "dark_icon.png": 256,
        "dark_icon@2x.png": 512,
    }
    # No SVG, redundant logo copies, source files or metadata in this folder.
    assert {path.name for path in brand.iterdir()} == set(expected)
    pixels = set()
    for filename, size in expected.items():
        with Image.open(brand / filename) as image:
            assert image.format == "PNG"
            assert image.size == (size, size)
            assert not image.info
            signature = image.convert("RGBA").tobytes()
            assert signature not in pixels, f"Redundant brand image: {filename}"
            pixels.add(signature)


def test_marketplace_and_integration_display_names_match():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    marketplace = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == "fibaro_cloud"
    assert manifest["name"] == marketplace["name"] == "FIBARO / Yubii Cloud"
    for path in [INTEGRATION / "strings.json", *sorted((INTEGRATION / "translations").glob("*.json"))]:
        assert json.loads(path.read_text(encoding="utf-8"))["title"] == manifest["name"]
