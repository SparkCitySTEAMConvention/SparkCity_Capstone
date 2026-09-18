"""Reusable Spark DataFrame transformations shared across dataset owners.

Day 3 (issue #29): Occupancy gets a persisted ``occupancy_rate`` column so the
shared Day 3 aggregation code (``day3_stuff.txt``'s ``prepare_correlation_dataset``)
can compute ``F.avg("occupancy_rate")`` without crashing. Traffic gets a
rotation transformation (domain-specific anomaly flags) per the Day 3 rotation
requirement.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, functions as F


def add_occupancy_rate(df: DataFrame) -> DataFrame:
    """Add ``occupancy_rate`` = occupied_rooms / available_rooms.

    Rows where ``available_rooms`` is 0 get a null ``occupancy_rate`` rather
    than a division-by-zero error, since an empty property has no meaningful
    rate rather than an invalid one.
    """
    return df.withColumn(
        "occupancy_rate",
        F.when(
            F.col("available_rooms") > 0,
            F.col("occupied_rooms") / F.col("available_rooms"),
        ),
    )


def add_traffic_anomaly_flags(df: DataFrame) -> DataFrame:
    """Flag physically impossible Traffic readings.

    Mirrors the domain-specific outlier rules stubbed in ``day2_stuff.txt``'s
    ``detect_domain_outliers`` for the traffic dataset:

    - ``speed_outlier_domain``: ``avg_speed`` outside the plausible 0-120 km/h
      range for city driving.
    - ``vehicle_count_outlier_domain``: negative ``vehicle_count`` (impossible).
    """
    return df.withColumn(
        "speed_outlier_domain",
        (F.col("avg_speed") < 0) | (F.col("avg_speed") > 120),
    ).withColumn(
        "vehicle_count_outlier_domain",
        F.col("vehicle_count") < 0,
    )
