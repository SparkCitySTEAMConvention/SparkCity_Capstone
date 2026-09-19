"""Tests for the convention planning baseline and archive response checks."""

import json
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from sparkcityx.convention_projection import (
    EVENT_DAYS,
    MAP_POINTS,
    _archive_year,
    summarize_projection,
)


def test_projection_averages_each_location_and_day_across_years() -> None:
    samples = [
        {
            "year": year,
            "day": day,
            "location": name,
            "lat": lat,
            "lon": lon,
            "temperature_f": 60.0 if year == 2025 else 70.0,
            "precipitation_mm": 1.0 if year == 2025 else 3.0,
        }
        for year in (2025, 2026)
        for day in EVENT_DAYS
        for name, lat, lon in MAP_POINTS
    ]

    projection = summarize_projection(samples, (2025, 2026))
    assert len(projection) == 27
    assert all(point["temperature_f"] == 65.0 for point in projection)
    assert all(point["precipitation_mm"] == 2.0 for point in projection)
    assert projection[0]["temperature_min_f"] == 60.0
    assert projection[0]["temperature_max_f"] == 70.0

    with pytest.raises(ValueError, match="Incomplete historical coverage"):
        summarize_projection(samples[:-1], (2025, 2026))


def test_archive_requests_matching_days_at_nine_locations() -> None:
    results = [
        {
            "daily": {
                "time": ["2025-04-06", "2025-04-07", "2025-04-08"],
                "temperature_2m_mean": [62.0, 64.0, 68.0],
                "precipitation_sum": [0.0, 2.0, 1.0],
            }
        }
        for _ in MAP_POINTS
    ]
    with patch("sparkcityx.convention_projection.urlopen") as open_url:
        open_url.return_value.__enter__.return_value = BytesIO(
            json.dumps(results).encode()
        )
        samples = _archive_year(2025)

    assert len(samples) == 27
    assert samples[0]["day"] == 6
    assert samples[-1]["day"] == 8
    params = parse_qs(urlparse(open_url.call_args.args[0]).query)
    assert params["daily"] == ["temperature_2m_mean,precipitation_sum"]
    assert params["temperature_unit"] == ["fahrenheit"]
    assert params["precipitation_unit"] == ["mm"]
    assert len(params["latitude"][0].split(",")) == 9
