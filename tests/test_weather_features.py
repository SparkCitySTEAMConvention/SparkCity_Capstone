import pytest

from datetime import date, datetime
from pyspark.sql import DataFrame, Window
from sparkcityx.weather_features import add_weather_time_features
from sparkcityx.weather_features import (
    add_weather_interaction_features,
    add_weather_rolling_features,
    add_weather_time_features,
    aggregate_daily_weather,
    aggregate_hourly_weather,
    map_weather_to_zones,
    aggregate_zone_hourly_weather,
)


def test_add_weather_time_features(spark) -> None:
    df = spark.createDataFrame(
        [
            (
                "WTH-001",
                datetime(2026, 1, 5, 14, 30),
            )
        ],
        "station_id string, timestamp timestamp",
    )

    result = add_weather_time_features(df)
    row = result.first()

    assert row.reading_date == date(2026, 1, 5)
    assert row.year == 2026
    assert row.month == 1
    assert row.week_of_year == 2
    assert row.day_of_week == 2
    assert row.hour == 14
    assert row.hour_timestamp == datetime(2026, 1, 5, 14, 0)

def make_weather_dataframe(spark):
    return spark.createDataFrame(
        [
            ("WTH-001", datetime(2026, 1, 1, 0, 0), 40.0, 50.0, 5.0, 0.0, 1010.0),
            ("WTH-002", datetime(2026, 1, 1, 0, 30), 60.0, 70.0, 15.0, 0.2, 1020.0),
            ("WTH-001", datetime(2026, 1, 1, 1, 0), 70.0, 60.0, 10.0, 0.1, 1015.0),
            ("WTH-001", datetime(2026, 1, 2, 0, 0), 80.0, 40.0, 20.0, 0.4, 1005.0),
        ],
        (
            "station_id string, timestamp timestamp, temperature double, "
            "humidity double, wind_speed double, precipitation double, "
            "pressure double"
        ),
    )

def test_aggregate_hourly_weather(spark) -> None:
    result = aggregate_hourly_weather(
        make_weather_dataframe(spark)
    )

    rows = result.orderBy("hour_timestamp").collect()

    assert len(rows) == 3
    assert rows[0].reading_count == 2
    assert rows[0].avg_temperature == pytest.approx(50.0)
    assert rows[0].avg_humidity == pytest.approx(60.0)
    assert rows[0].max_wind_speed == pytest.approx(15.0)
    assert rows[0].max_precipitation == pytest.approx(0.2)


def test_aggregate_daily_weather(spark) -> None:
    result = aggregate_daily_weather(
        make_weather_dataframe(spark)
    )

    rows = result.orderBy("reading_date").collect()

    assert len(rows) == 2
    assert rows[0].reading_count == 3
    assert rows[0].avg_temperature == pytest.approx(
        56.6666666667
    )
    assert rows[0].min_temperature == pytest.approx(40.0)
    assert rows[0].max_temperature == pytest.approx(70.0)


def test_add_weather_rolling_features_handles_initial_nulls(spark) -> None:
    hourly_df = aggregate_hourly_weather(
        make_weather_dataframe(spark)
    )

    rows = (
        add_weather_rolling_features(hourly_df)
        .orderBy("hour_timestamp")
        .collect()
    )

    assert rows[0].temperature_lag_1h is None
    assert rows[0].temperature_lag_24h is None
    assert rows[0].temperature_24h_stddev is None

    assert rows[1].temperature_lag_1h == pytest.approx(50.0)
    assert rows[1].temperature_change_1h == pytest.approx(20.0)
    assert rows[1].temperature_trend == "INSUFFICIENT_HISTORY"
    assert rows[1].temperature_24h_stddev is not None


def test_weather_interaction_features_are_bounded(spark) -> None:
    df = spark.createDataFrame(
        [
            (
                "WTH-001",
                datetime(2026, 1, 1, 0, 0),
                50.0,
                60.0,
                5.0,
                0.0,
                0.0,
            ),
            (
                "WTH-002",
                datetime(2026, 6, 1, 6, 0),
                70.0,
                80.0,
                20.0,
                360.0,
                0.5,
            ),
        ],
        (
            "station_id string, timestamp timestamp, temperature double, "
            "humidity double, wind_speed double, wind_direction double, "
            "precipitation double"
        ),
    )

    rows = (
        add_weather_interaction_features(
            df,
            high_wind_threshold=15.0,
            high_precipitation_threshold=0.2,
        )
        .orderBy("station_id")
        .collect()
    )

    cyclic_columns = [
        "wind_direction_sin",
        "wind_direction_cos",
        "hour_sin",
        "hour_cos",
        "month_sin",
        "month_cos",
    ]

    for row in rows:
        for column in cyclic_columns:
            assert -1.0 <= row[column] <= 1.0

    assert rows[0].weather_condition == "DRY"
    assert rows[1].weather_condition == "WET_AND_WINDY"


def test_map_weather_to_zones_is_deterministic_and_preserves_unmapped(
    spark,
) -> None:
    weather_df = spark.createDataFrame(
        [
            ("WTH-001", datetime(2026, 1, 1), 0.5, 0.5),
            ("WTH-002", datetime(2026, 1, 1), 5.0, 5.0),
        ],
        (
            "station_id string, timestamp timestamp, "
            "location_lat double, location_lon double"
        ),
    )

    zones_df = spark.createDataFrame(
        [
            ("ZONE_BIG", "Large Zone", "mixed", -1.0, 1.0, -1.0, 1.0),
            ("ZONE_SMALL", "Small Zone", "residential", 0.0, 0.75, 0.0, 0.75),
        ],
        (
            "zone_id string, zone_name string, zone_type string, "
            "lat_min double, lat_max double, lon_min double, lon_max double"
        ),
    )

    rows = (
        map_weather_to_zones(weather_df, zones_df)
        .orderBy("station_id")
        .collect()
    )

    assert len(rows) == 2
    assert rows[0].zone_id == "ZONE_SMALL"
    assert rows[1].zone_id is None



def test_aggregate_zone_hourly_weather(spark) -> None:
    df = spark.createDataFrame(
        [
            (
                "ZONE_001",
                "Downtown",
                "commercial",
                datetime(2026, 1, 1, 0, 0),
                40.0,
                50.0,
                5.0,
                0.0,
                1010.0,
            ),
            (
                "ZONE_001",
                "Downtown",
                "commercial",
                datetime(2026, 1, 1, 0, 30),
                60.0,
                70.0,
                15.0,
                0.2,
                1020.0,
            ),
            (
                "ZONE_001",
                "Downtown",
                "commercial",
                datetime(2026, 1, 1, 1, 0),
                70.0,
                60.0,
                10.0,
                0.1,
                1015.0,
            ),
            (
                None,
                None,
                None,
                datetime(2026, 1, 1, 0, 0),
                80.0,
                40.0,
                20.0,
                0.4,
                1005.0,
            ),
        ],
        (
            "zone_id string, zone_name string, zone_type string, "
            "timestamp timestamp, temperature double, humidity double, "
            "wind_speed double, precipitation double, pressure double"
        ),
    )

    rows = (
        aggregate_zone_hourly_weather(df)
        .orderBy("hour_timestamp")
        .collect()
    )

    assert len(rows) == 2
    assert rows[0].weather_readings == 2
    assert rows[0].avg_temperature == pytest.approx(50.0)
    assert rows[0].avg_humidity == pytest.approx(60.0)
    assert rows[0].max_wind_speed == pytest.approx(15.0)
    assert rows[0].max_precipitation == pytest.approx(0.2)