"""Checks for the Environment page's external data loaders."""

import json
from io import BytesIO
from unittest.mock import patch

from sparkcityx.current_air_quality import (
    aqi_category,
    load_current_air_quality,
)
from sparkcityx.lunar_data import load_lunar_details


def response(data: dict) -> BytesIO:
    return BytesIO(json.dumps(data).encode())


def test_aqi_category_boundaries() -> None:
    assert aqi_category(50)[0] == "Good"
    assert aqi_category(51)[0] == "Moderate"
    assert aqi_category(100)[0] == "Moderate"
    assert aqi_category(101)[0] == "Unhealthy for sensitive groups"
    assert aqi_category(150)[0] == "Unhealthy for sensitive groups"
    assert aqi_category(151)[0] == "Unhealthy"
    assert aqi_category(300)[0] == "Very unhealthy"
    assert aqi_category(301)[0] == "Hazardous"


def test_current_air_quality_reads_modeled_aqi() -> None:
    payload = {
        "current": {
            "us_aqi": 63,
            "pm2_5": 7.7,
            "time": "2026-09-18T14:00",
        }
    }
    with patch(
        "sparkcityx.current_air_quality.urlopen",
        return_value=response(payload),
    ):
        result = load_current_air_quality()

    assert result["us_aqi"] == 63
    assert result["category"] == "Moderate"
    assert result["pm25_ug_m3"] == 7.7


def test_lunar_details_convert_full_moon_to_new_york_time() -> None:
    daily = {
        "properties": {
            "data": {
                "curphase": "Waxing Crescent",
                "fracillum": "49%",
            }
        }
    }
    phases = {
        "phasedata": [{
            "year": 2026,
            "month": 9,
            "day": 26,
            "time": "16:49",
            "phase": "Full Moon",
        }]
    }
    with patch(
        "sparkcityx.lunar_data.urlopen",
        side_effect=[response(daily), response(phases)],
    ):
        result = load_lunar_details()

    assert result["phase"] == "Waxing Crescent"
    assert result["illumination"] == "49%"
    assert result["next_full_moon"] == "Sep 26"
    assert result["next_full_moon_time"] == "12:49 PM"
