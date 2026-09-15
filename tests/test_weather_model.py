from datetime import datetime, timedelta

import pytest

from sparkcityx.weather_model import train_temperature_forecaster


def test_temperature_forecaster_returns_predictions_and_metrics(spark) -> None:
    start = datetime(2026, 1, 1)

    rows = [
        (
            start + timedelta(hours=index),
            50.0 + (index * 0.5),
            55.0 + (index % 5),
            8.0 + (index % 3),
            0.1 * (index % 2),
            1010.0 + (index % 4),
        )
        for index in range(100)
    ]

    hourly_df = spark.createDataFrame(
        rows,
        (
            "hour_timestamp timestamp, avg_temperature double, "
            "avg_humidity double, avg_wind_speed double, "
            "avg_precipitation double, avg_pressure double"
        ),
    )

    result = train_temperature_forecaster(
        hourly_df,
        train_ratio=0.8,
    )

    assert result.training_rows > 0
    assert result.test_rows > 0
    assert result.predictions.count() == result.test_rows
    assert "prediction" in result.predictions.columns
    assert result.metrics["rmse"] >= 0
    assert result.metrics["mae"] >= 0
    assert result.metrics["rmse"] < 1.0
    assert result.metrics["r2"] == pytest.approx(1.0, abs=0.05)