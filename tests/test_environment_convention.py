from unittest.mock import MagicMock

from sparkcityx.environment_data import (
    load_convention_air_history,
    load_convention_weather_history,
)


def test_convention_weather_history_uses_matching_dates() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (2025, 6, 48, 62.08, 10.28, 0.099, 60.4),
        (2026, 6, 48, 60.33, 16.53, 0.146, 72.9),
    ]

    result = load_convention_weather_history(connection)

    assert result["year"].tolist() == [2025, 2026]
    assert result["day"].tolist() == [6, 6]
    assert result["readings"].tolist() == [48, 48]
    query = cursor.execute.call_args.args[0]
    assert "sparkcity.weather_data" in query
    assert "2025-04-06" in query and "2025-04-09" in query
    assert "2026-04-06" in query and "2026-04-09" in query


def test_convention_air_history_uses_matching_dates() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        (2025, 6, 96, 22.66, 32.40, 26.55, 0.76),
    ]

    result = load_convention_air_history(connection)

    assert result["year"].tolist() == [2025]
    assert result["day"].tolist() == [6]
    assert result["readings"].tolist() == [96]
    query = cursor.execute.call_args.args[0]
    assert "sparkcity.air_quality" in query
    assert "2025-04-06" in query and "2025-04-09" in query
    assert "2026-04-06" in query and "2026-04-09" in query
