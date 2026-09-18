"""Current modeled weather for a small set of SparkCity map locations."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen


MAP_LOCATIONS = (
    ("Center", 40.76, -73.97),
    ("North", 40.82, -73.97),
    ("South", 40.70, -73.97),
    ("West", 40.76, -74.02),
    ("East", 40.76, -73.91),
)


def weather_symbol(code: int) -> tuple[str, str, list[int]]:
    """Return a readable condition, icon, and map-marker color."""
    if code >= 95:
        return "Thunderstorm", "⛈️", [168, 85, 247, 220]
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow", "❄️", [99, 179, 237, 220]
    if 51 <= code <= 82:
        return "Rain or showers", "🌧️", [37, 99, 235, 220]
    if code in (1, 2, 3, 45, 48):
        return "Cloudy or partly cloudy", "⛅", [100, 116, 139, 220]
    if code == 0:
        return "Clear", "☀️", [245, 158, 11, 220]
    return "Conditions unavailable", "🌤️", [100, 116, 139, 220]


def load_current_weather_points() -> list[dict]:
    """Fetch current modeled conditions at five map locations."""
    params = urlencode(
        {
            "latitude": ",".join(
                str(latitude) for _, latitude, _ in MAP_LOCATIONS
            ),
            "longitude": ",".join(
                str(longitude) for _, _, longitude in MAP_LOCATIONS
            ),
            "current": "temperature_2m,precipitation,weather_code",
            "timezone": "America/New_York",
            "temperature_unit": "fahrenheit",
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"

    with urlopen(url, timeout=15) as response:
        results = json.load(response)

    if not isinstance(results, list) or len(results) != len(MAP_LOCATIONS):
        raise ValueError("Unexpected current weather response")

    points = []
    for (name, latitude, longitude), result in zip(
        MAP_LOCATIONS, results, strict=True
    ):
        current = result["current"]
        description, icon, color = weather_symbol(
            int(current["weather_code"])
        )
        points.append(
            {
                "location": name,
                "lat": latitude,
                "lon": longitude,
                "temperature_f": current["temperature_2m"],
                "precipitation_mm": current["precipitation"],
                "reported_at": current["time"],
                "description": description,
                "icon": icon,
                "color": color,
            }
        )

    return points
