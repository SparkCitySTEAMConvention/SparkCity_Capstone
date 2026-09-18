from datetime import datetime
from unittest.mock import MagicMock

import pytest

from sparkcityx.environment_data import load_monthly_environment


def test_monthly_environment_combines_air_and_weather() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [
        [(4, 21.12, 2880), (7, 20.84, 2976)],
        [(4, 50.93, 1440), (7, 50.34, 1488)],
    ]

    result = load_monthly_environment(connection, 2025)

    assert result["month"].tolist() == [4, 7]
    assert result["average_pm25"].tolist() == pytest.approx(
        [21.12, 20.84]
    )
    assert result["average_temperature"].tolist() == pytest.approx(
        [50.93, 50.34]
    )
    assert result["air_readings"].tolist() == [2880, 2976]
    assert result["weather_readings"].tolist() == [1440, 1488]

    assert cursor.execute.call_count == 2
    for call in cursor.execute.call_args_list:
        assert call.args[1] == (
            datetime(2025, 1, 1),
            datetime(2026, 1, 1),
        )


def test_monthly_environment_rejects_invalid_year() -> None:
    connection = MagicMock()

    with pytest.raises(ValueError, match="year"):
        load_monthly_environment(connection, 1800)

    connection.cursor.assert_not_called()


from sparkcityx.environment_data import (
    load_air_monitoring_status,
    load_monthly_environment,
)


def test_air_monitoring_status_uses_full_history_thresholds() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (35_040, 10_494)

    result = load_air_monitoring_status(connection, 2025)

    assert result == {
        "total": 35_040,
        "normal": 24_546,
        "monitor": 10_494,
    }

    query, dates = cursor.execute.call_args.args
    assert "percentile_cont(0.9)" in query
    assert "FROM sparkcity.air_quality" in query
    assert dates == (
        datetime(2025, 1, 1),
        datetime(2026, 1, 1),
    )