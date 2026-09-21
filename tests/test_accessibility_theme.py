"""Accessibility contracts for the dashboard's light and dark presentation."""

from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from components.shared import LIGHT_PALETTE


def _relative_luminance(hex_color):
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground, background):
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_light_theme_core_text_pairs_meet_wcag_aa():
    pairs = (
        ("#172B46", "#F4F7FB"),
        ("#172B46", "#FFFFFF"),
        ("#526A82", "#FFFFFF"),
        ("#FFFFFF", "#101F39"),
    )

    assert all(_contrast_ratio(foreground, background) >= 4.5 for foreground, background in pairs)


def test_light_palette_replaces_primary_dark_surface_tokens():
    assert LIGHT_PALETTE["#101820"] == "#F4F7FB"
    assert LIGHT_PALETTE["#182430"] == "#FFFFFF"
    assert LIGHT_PALETTE["#F3F6F9"] == "#172B46"


def test_daylight_hero_matches_dark_hero_dimensions():
    assets = ROOT / "dashboard" / "assets"
    with Image.open(assets / "updated_hero.png") as dark_image:
        with Image.open(assets / "updated_hero_daylight.png") as daylight_image:
            assert daylight_image.size == dark_image.size
