from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from sparkcityx.weather_pipeline import run_weather_pipeline


def test_weather_pipeline_preview_validates_without_writing(
    spark,
    tmp_path,
) -> None:
    source = tmp_path / "weather.parquet"

    df = spark.createDataFrame(
        [
            (
                "WTH-001",
                datetime(2026, 1, 1, 0, 0),
                40.71,
                -74.00,
                55.0,
                60.0,
                10.0,
                180.0,
                0.1,
                1012.0,
            )
        ],
        (
            "station_id string, timestamp timestamp, "
            "location_lat double, location_lon double, "
            "temperature double, humidity double, "
            "wind_speed double, wind_direction double, "
            "precipitation double, pressure double"
        ),
    )

    df.write.mode("overwrite").parquet(str(source))

    result = run_weather_pipeline(
        spark,
        source,
        apply=False,
    )

    assert result.valid is True
    assert result.record_count == 1
    assert result.applied is False
    assert result.load_result is None


    with pytest.raises(
        ValueError,
        match="database connection is required",
    ):
        run_weather_pipeline(
        spark,
            source,
            apply=True,
        )


@patch("sparkcityx.weather_pipeline.load_dataframe")
@patch("sparkcityx.weather_pipeline.validate_dataframe")
@patch("sparkcityx.weather_pipeline.load_dataset")
def test_weather_pipeline_apply_delegates_to_database_loader(
    load_dataset_mock,
    validate_dataframe_mock,
    load_dataframe_mock,
    tmp_path,
) -> None:
    source = tmp_path / "weather.parquet"
    source.touch()

    spark = MagicMock()
    connection = MagicMock()
    weather_df = MagicMock()
    expected_load_result = MagicMock()

    load_dataset_mock.return_value = weather_df
    validate_dataframe_mock.return_value = {
        "valid": True,
        "record_count": 10,
    }
    load_dataframe_mock.return_value = expected_load_result

    result = run_weather_pipeline(
        spark,
        source,
        connection=connection,
        apply=True,
        batch_size=500,
    )

    assert result.valid is True
    assert result.record_count == 10
    assert result.applied is True
    assert result.load_result is expected_load_result

    load_dataset_mock.assert_called_once_with(spark, source)
    validate_dataframe_mock.assert_called_once_with(
        weather_df,
        "weather",
    )
    load_dataframe_mock.assert_called_once_with(
        connection,
        weather_df,
        "weather",
        batch_size=500,
    )


@patch("sparkcityx.weather_pipeline.load_dataframe")
@patch("sparkcityx.weather_pipeline.validate_dataframe")
@patch("sparkcityx.weather_pipeline.load_dataset")
def test_weather_pipeline_rejects_invalid_data_before_writing(
    load_dataset_mock,
    validate_dataframe_mock,
    load_dataframe_mock,
    tmp_path,
) -> None:
    source = tmp_path / "invalid-weather.parquet"
    source.touch()

    spark = MagicMock()
    connection = MagicMock()
    weather_df = MagicMock()

    load_dataset_mock.return_value = weather_df
    validate_dataframe_mock.return_value = {
        "valid": False,
        "record_count": 1,
        "range_violations": {"humidity": 1},
    }

    with pytest.raises(
        ValueError,
        match="Weather validation failed",
    ):
        run_weather_pipeline(
            spark,
            source,
            connection=connection,
            apply=True,
        )

    load_dataframe_mock.assert_not_called()