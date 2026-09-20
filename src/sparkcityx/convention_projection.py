"""Historical reanalysis baseline for the November 2027 convention map.

Each displayed point is the mean of matching calendar dates across prior years.
These values are planning projections, not meteorological forecasts.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from urllib.parse import urlencode
from urllib.request import urlopen

# Roughly 7 km spacing; the source reanalysis has approximately 9 km resolution.
MAP_POINTS = tuple(
    (name, latitude, longitude)
    for latitude, row in (
        (40.82, ("NW", "North", "NE")),
        (40.76, ("West", "Center", "East")),
        (40.70, ("SW", "South", "SE")),
    )
    for name, longitude in zip(row, (-74.03, -73.97, -73.91), strict=True)
)
HISTORY_YEARS = tuple(range(2021, 2027))
EVENT_DAYS = (3, 4, 5)


def _archive_year(year: int) -> list[dict]:
    """Load matching November days for all map points in one archive request."""
    params = urlencode(
        {
            "latitude": ",".join(str(lat) for _, lat, _ in MAP_POINTS),
            "longitude": ",".join(str(lon) for _, _, lon in MAP_POINTS),
            "start_date": f"{year}-11-03",
            "end_date": f"{year}-11-05",
            "daily": "temperature_2m_mean,precipitation_sum",
            "timezone": "America/New_York",
            "temperature_unit": "fahrenheit",
            "precipitation_unit": "mm",
        }
    )
    with urlopen(
        f"https://archive-api.open-meteo.com/v1/archive?{params}",
        timeout=15,
    ) as response:
        results = json.load(response)

    if not isinstance(results, list) or len(results) != len(MAP_POINTS):
        raise ValueError(f"Unexpected archive response for {year}")

    samples = []
    for (name, latitude, longitude), result in zip(
        MAP_POINTS, results, strict=True
    ):
        daily = result["daily"]
        expected_dates = [f"{year}-11-{day:02d}" for day in EVENT_DAYS]
        if daily["time"] != expected_dates:
            raise ValueError(f"Incomplete archive dates for {year}, {name}")
        temperatures = daily["temperature_2m_mean"]
        precipitation = daily["precipitation_sum"]
        if len(temperatures) != 3 or len(precipitation) != 3:
            raise ValueError(f"Incomplete archive values for {year}, {name}")
        for day, temperature, rainfall in zip(
            EVENT_DAYS, temperatures, precipitation, strict=True
        ):
            if temperature is None or rainfall is None:
                raise ValueError(f"Missing archive values for {year}, {name}")
            samples.append(
                {
                    "year": year,
                    "day": day,
                    "location": name,
                    "lat": latitude,
                    "lon": longitude,
                    "temperature_f": float(temperature),
                    "precipitation_mm": float(rainfall),
                }
            )
    return samples


def summarize_projection(samples: list[dict], years: tuple[int, ...]) -> list[dict]:
    """Average each date and map point, retaining the historical range."""
    if not years:
        raise ValueError("At least one historical year is required")

    by_point = {}
    for sample in samples:
        key = (sample["day"], sample["location"])
        by_point.setdefault(key, []).append(sample)

    projections = []
    for day in EVENT_DAYS:
        for name, latitude, longitude in MAP_POINTS:
            readings = by_point.get((day, name), [])
            if sorted(row["year"] for row in readings) != sorted(years):
                raise ValueError(
                    "Incomplete historical coverage for "
                    f"November {day}, {name}"
                )
            temperatures = [row["temperature_f"] for row in readings]
            rainfall = [row["precipitation_mm"] for row in readings]
            projections.append(
                {
                    "day": day,
                    "location": name,
                    "lat": latitude,
                    "lon": longitude,
                    "temperature_f": round(mean(temperatures), 1),
                    "temperature_min_f": round(min(temperatures), 1),
                    "temperature_max_f": round(max(temperatures), 1),
                    "precipitation_mm": round(mean(rainfall), 1),
                    "precipitation_min_mm": round(min(rainfall), 1),
                    "precipitation_max_mm": round(max(rainfall), 1),
                    "history_years": len(years),
                }
            )
    return projections


def load_convention_projection() -> list[dict]:
    """Fetch 2021–2026 matching dates and compute a November 2027 baseline."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        per_year = list(pool.map(_archive_year, HISTORY_YEARS))
    samples = [sample for year_rows in per_year for sample in year_rows]
    return summarize_projection(samples, HISTORY_YEARS)
