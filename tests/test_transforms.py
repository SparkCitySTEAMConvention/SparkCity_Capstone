from __future__ import annotations

from pyspark.sql import functions as F

from sparkcityx.transforms import add_occupancy_rate, add_traffic_anomaly_flags


def test_add_occupancy_rate_computes_ratio(spark) -> None:
    df = spark.createDataFrame(
        [("S1", 50, 100), ("S2", 30, 120)],
        "sensor_id string, occupied_rooms int, available_rooms int",
    )

    result = add_occupancy_rate(df).orderBy("sensor_id").collect()

    assert result[0]["occupancy_rate"] == 0.5
    assert result[1]["occupancy_rate"] == 0.25


def test_add_occupancy_rate_handles_zero_available_rooms(spark) -> None:
    df = spark.createDataFrame(
        [("S1", 0, 0)],
        "sensor_id string, occupied_rooms int, available_rooms int",
    )

    result = add_occupancy_rate(df).collect()

    assert result[0]["occupancy_rate"] is None


def test_add_occupancy_rate_preserves_existing_columns(spark) -> None:
    df = spark.createDataFrame(
        [("S1", "2026-01-01", 40.0, -74.0, 100, 50, 80)],
        (
            "sensor_id string, timestamp string, location_lat double, "
            "location_lon double, available_rooms int, occupied_rooms int, guests int"
        ),
    )

    result = add_occupancy_rate(df)

    assert set(df.columns) <= set(result.columns)
    assert result.count() == df.count()


def test_add_traffic_anomaly_flags_flags_impossible_readings(spark) -> None:
    df = spark.createDataFrame(
        [
            ("S1", 50, 60.0),   # normal
            ("S2", -5, 40.0),   # impossible negative vehicle count
            ("S3", 20, 150.0),  # impossible speed (>120 km/h)
            ("S4", 15, -10.0),  # impossible speed (negative)
        ],
        "sensor_id string, vehicle_count int, avg_speed double",
    )

    result = add_traffic_anomaly_flags(df).orderBy("sensor_id").collect()

    assert result[0]["vehicle_count_outlier_domain"] is False
    assert result[0]["speed_outlier_domain"] is False

    assert result[1]["vehicle_count_outlier_domain"] is True
    assert result[2]["speed_outlier_domain"] is True
    assert result[3]["speed_outlier_domain"] is True


def test_add_traffic_anomaly_flags_counts_are_queryable(spark) -> None:
    df = spark.createDataFrame(
        [("S1", 50, 60.0), ("S2", -5, 40.0), ("S3", 20, 150.0)],
        "sensor_id string, vehicle_count int, avg_speed double",
    )

    flagged = add_traffic_anomaly_flags(df)
    anomaly_count = flagged.filter(
        F.col("speed_outlier_domain") | F.col("vehicle_count_outlier_domain")
    ).count()

    assert anomaly_count == 2
