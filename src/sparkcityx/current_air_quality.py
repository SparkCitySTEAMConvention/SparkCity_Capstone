"""Current modeled air quality for the SparkCity Center location."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

from sparkcityx.current_weather import MAP_LOCATIONS


def aqi_category(value: int) -> tuple[str, str]:
    """Return the standard US AQI category and its display color."""
    if value <= 50:
        return "Good", "#22C55E"
    if value <= 100:
        return "Moderate", "#EAB308"
    if value <= 150:
        return "Unhealthy for sensitive groups", "#F97316"
    if value <= 200:
        return "Unhealthy", "#EF4444"
    if value <= 300:
        return "Very unhealthy", "#A855F7"
    return "Hazardous", "#7F1D1D"


def load_current_air_quality() -> dict:
    """Fetch current modeled US AQI and PM2.5 for SparkCity Center."""
    _, latitude, longitude = MAP_LOCATIONS[0]
    params = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi,pm2_5",
            "timezone": "America/New_York",
        }
    )
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?{params}"

    with urlopen(url, timeout=15) as response:
        result = json.load(response)

    current = result["current"]
    value = current["us_aqi"]
    if value is None:
        raise ValueError("Current modeled US AQI is unavailable")

    category, color = aqi_category(int(value))
    return {
        "us_aqi": int(value),
        "category": category,
        "color": color,
        "pm25_ug_m3": current.get("pm2_5"),
        "reported_at": current["time"],
    }
