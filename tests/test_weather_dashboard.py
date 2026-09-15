from datetime import datetime

import pandas as pd
import pytest

from sparkcityx.weather_dashboard import (
    prepare_weather_dashboard_data,
    summarize_weather_dashboard,
)


def make_dashboard_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "station_id": "WTH-002",
                "timestamp": datetime(2026, 1, 1, 1, 30),
                "temperature": 70.0,
                "humidity": 60.0,
                "wind_speed": 20.0,
                "precipitation": 0.2,
                "pressure": 1010.0,
            },
            {
                "station_id": "WTH-001",
                "timestamp": datetime(2026, 1, 1, 0, 30),
                "temperature": 50.0,
                "humidity": 40.0,
                "wind_speed": 10.0,
                "precipitation": 0.0,
                "pressure": 1014.0,
            },
        ]
    )


def test_prepare_weather_dashboard_data_adds_time_fields() -> None:
    result = prepare_weather_dashboard_data(
        make_dashboard_dataframe()
    )

    assert list(result["station_id"]) == [
        "WTH-001",
        "WTH-002",
    ]
    assert "reading_date" in result.columns
    assert "hour_timestamp" in result.columns
    assert result.iloc[0]["hour_timestamp"] == pd.Timestamp(
        "2026-01-01 00:00:00"
    )


def test_summarize_weather_dashboard_calculates_metrics() -> None:
    prepared = prepare_weather_dashboard_data(
        make_dashboard_dataframe()
    )

    summary = summarize_weather_dashboard(prepared)

    assert summary["record_count"] == 2
    assert summary["station_count"] == 2
    assert summary["average_temperature"] == pytest.approx(60.0)
    assert summary["average_humidity"] == pytest.approx(50.0)
    assert summary["maximum_wind_speed"] == pytest.approx(20.0)
    assert summary["total_precipitation"] == pytest.approx(0.2)