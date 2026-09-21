import json
from io import BytesIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from sparkcityx.current_weather import (
    MAP_LOCATIONS,
    load_current_weather_points,
    weather_symbol,
)


def test_weather_symbols_match_condition_codes() -> None:
    assert weather_symbol(0)[0] == "Clear"
    assert weather_symbol(3)[0] == "Cloudy or partly cloudy"
    assert weather_symbol(61)[0] == "Rain or showers"
    assert weather_symbol(71)[0] == "Snow"
    assert weather_symbol(95)[0] == "Thunderstorm"


def test_current_weather_maps_each_api_result_to_its_location() -> None:
    response = [
        {
            "current": {
                "time": "2026-09-17T16:45",
                "temperature_2m": 80.0 + index,
                "precipitation": 0.0,
                "weather_code": 3,
            }
        }
        for index in range(len(MAP_LOCATIONS))
    ]

    with patch("sparkcityx.current_weather.urlopen") as open_url:
        open_url.return_value.__enter__.return_value = BytesIO(
            json.dumps(response).encode()
        )
        points = load_current_weather_points()

    assert len(points) == 5
    assert points[0]["location"] == "Center"
    assert points[0]["temperature_f"] == 80.0
    assert points[-1]["location"] == "East"
    assert points[-1]["temperature_f"] == 84.0

    url = open_url.call_args.args[0]
    params = parse_qs(urlparse(url).query)
    assert len(params["latitude"][0].split(",")) == 5
    assert params["temperature_unit"] == ["fahrenheit"]
