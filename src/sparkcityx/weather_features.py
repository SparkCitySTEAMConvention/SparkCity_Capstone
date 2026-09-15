"""Reusable PySpark transformations for SparkCity weather analytics."""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


def add_weather_time_features(df: DataFrame) -> DataFrame:
    """Add calendar and hourly analysis columns from the weather timestamp."""
    return (
        df
        .withColumn("reading_date", F.to_date("timestamp"))
        .withColumn("year", F.year("timestamp"))
        .withColumn("month", F.month("timestamp"))
        .withColumn("week_of_year", F.weekofyear("timestamp"))
        .withColumn("day_of_week", F.dayofweek("timestamp"))
        .withColumn("hour", F.hour("timestamp"))
        .withColumn(
            "hour_timestamp",
            F.date_trunc("hour", "timestamp"),
        )
    )


def aggregate_hourly_weather(df: DataFrame) -> DataFrame:
    """Aggregate weather measurements into citywide hourly features."""
    time_df = (
        df
        if "hour_timestamp" in df.columns
        else add_weather_time_features(df)
    )

    return (
        time_df
        .groupBy("hour_timestamp")
        .agg(
            F.avg("temperature").alias("avg_temperature"),
            F.avg("humidity").alias("avg_humidity"),
            F.avg("wind_speed").alias("avg_wind_speed"),
            F.max("wind_speed").alias("max_wind_speed"),
            F.avg("precipitation").alias("avg_precipitation"),
            F.max("precipitation").alias("max_precipitation"),
            F.avg("pressure").alias("avg_pressure"),
            F.count("*").alias("reading_count"),
        )
        .orderBy("hour_timestamp")
    )


def aggregate_daily_weather(df: DataFrame) -> DataFrame:
    """Aggregate weather measurements into citywide daily features."""
    time_df = (
        df
        if "reading_date" in df.columns
        else add_weather_time_features(df)
    )

    return (
        time_df
        .groupBy("reading_date")
        .agg(
            F.avg("temperature").alias("avg_temperature"),
            F.min("temperature").alias("min_temperature"),
            F.max("temperature").alias("max_temperature"),
            F.avg("humidity").alias("avg_humidity"),
            F.avg("wind_speed").alias("avg_wind_speed"),
            F.max("wind_speed").alias("max_wind_speed"),
            F.avg("precipitation").alias("avg_precipitation"),
            F.max("precipitation").alias("max_precipitation"),
            F.avg("pressure").alias("avg_pressure"),
            F.count("*").alias("reading_count"),
        )
        .orderBy("reading_date")
    )

def add_weather_rolling_features(df: DataFrame) -> DataFrame:
    """Add 24-hour rolling statistics, lags, changes, and trend labels."""
    hour_window = Window.orderBy("hour_timestamp")
    rolling_window = hour_window.rowsBetween(-23, 0)

    return (
        df
        .withColumn(
            "temperature_24h_mean",
            F.avg("avg_temperature").over(rolling_window),
        )
        .withColumn(
            "temperature_24h_stddev",
            F.stddev("avg_temperature").over(rolling_window),
        )
        .withColumn(
            "humidity_24h_mean",
            F.avg("avg_humidity").over(rolling_window),
        )
        .withColumn(
            "wind_speed_24h_max",
            F.max("max_wind_speed").over(rolling_window),
        )
        .withColumn(
            "temperature_lag_1h",
            F.lag("avg_temperature", 1).over(hour_window),
        )
        .withColumn(
            "temperature_lag_24h",
            F.lag("avg_temperature", 24).over(hour_window),
        )
        .withColumn(
            "temperature_change_1h",
            F.col("avg_temperature") - F.col("temperature_lag_1h"),
        )
        .withColumn(
            "temperature_change_24h",
            F.col("avg_temperature") - F.col("temperature_lag_24h"),
        )
        .withColumn(
            "temperature_trend",
            F.when(
                F.col("temperature_lag_24h").isNull(),
                F.lit("INSUFFICIENT_HISTORY"),
            )
            .when(
                F.col("avg_temperature") > F.col("temperature_lag_24h"),
                F.lit("WARMING"),
            )
            .when(
                F.col("avg_temperature") < F.col("temperature_lag_24h"),
                F.lit("COOLING"),
            )
            .otherwise(F.lit("STABLE")),
        )
    )


def add_weather_interaction_features(
    df: DataFrame,
    *,
    high_wind_threshold: float,
    high_precipitation_threshold: float,
) -> DataFrame:
    """Add deterministic interaction, condition, and cyclical features."""
    time_df = (
        df
        if {"hour", "month"}.issubset(df.columns)
        else add_weather_time_features(df)
    )

    pi = 3.141592653589793

    return (
        time_df
        .withColumn(
            "is_precipitating",
            F.col("precipitation") > 0,
        )
        .withColumn(
            "is_high_precipitation",
            F.col("precipitation")
            >= high_precipitation_threshold,
        )
        .withColumn(
            "is_high_wind",
            F.col("wind_speed") >= high_wind_threshold,
        )
        .withColumn(
            "temperature_humidity_interaction",
            F.col("temperature") * F.col("humidity"),
        )
        .withColumn(
            "wind_direction_sin",
            F.sin(F.radians("wind_direction")),
        )
        .withColumn(
            "wind_direction_cos",
            F.cos(F.radians("wind_direction")),
        )
        .withColumn(
            "hour_sin",
            F.sin(2 * F.lit(pi) * F.col("hour") / 24),
        )
        .withColumn(
            "hour_cos",
            F.cos(2 * F.lit(pi) * F.col("hour") / 24),
        )
        .withColumn(
            "month_sin",
            F.sin(2 * F.lit(pi) * F.col("month") / 12),
        )
        .withColumn(
            "month_cos",
            F.cos(2 * F.lit(pi) * F.col("month") / 12),
        )
        .withColumn(
            "weather_condition",
            F.when(
                (F.col("precipitation") >= high_precipitation_threshold)
                & (F.col("wind_speed") >= high_wind_threshold),
                F.lit("WET_AND_WINDY"),
            )
            .when(
                F.col("precipitation")
                >= high_precipitation_threshold,
                F.lit("HIGH_PRECIPITATION"),
            )
            .when(
                F.col("wind_speed") >= high_wind_threshold,
                F.lit("HIGH_WIND"),
            )
            .when(
                F.col("precipitation") > 0,
                F.lit("LIGHT_PRECIPITATION"),
            )
            .otherwise(F.lit("DRY")),
        )
    )


def map_weather_to_zones(
    weather_df: DataFrame,
    zones_df: DataFrame,
) -> DataFrame:
    """Map each weather reading to the smallest matching geographic zone."""
    weather_alias = weather_df.alias("weather")
    zone_alias = F.broadcast(zones_df).alias("zone")

    zone_condition = (
        F.col("weather.location_lat").between(
            F.col("zone.lat_min"),
            F.col("zone.lat_max"),
        )
        & F.col("weather.location_lon").between(
            F.col("zone.lon_min"),
            F.col("zone.lon_max"),
        )
    )

    candidates_df = (
        weather_alias
        .join(zone_alias, zone_condition, "left")
        .select(
            "weather.*",
            F.col("zone.zone_id").alias("zone_id"),
            F.col("zone.zone_name").alias("zone_name"),
            F.col("zone.zone_type").alias("zone_type"),
            (
                (F.col("zone.lat_max") - F.col("zone.lat_min"))
                * (F.col("zone.lon_max") - F.col("zone.lon_min"))
            ).alias("_zone_area"),
        )
    )

    zone_rank_window = Window.partitionBy(
        "station_id",
        "timestamp",
    ).orderBy(
        F.col("_zone_area").asc_nulls_last(),
        F.col("zone_id").asc_nulls_last(),
    )

    return (
        candidates_df
        .withColumn(
            "_zone_rank",
            F.row_number().over(zone_rank_window),
        )
        .filter(F.col("_zone_rank") == 1)
        .drop("_zone_area", "_zone_rank")
    )


def aggregate_zone_hourly_weather(df: DataFrame) -> DataFrame:
    """Aggregate mapped weather readings by city zone and hour."""
    time_df = (
        df
        if "hour_timestamp" in df.columns
        else add_weather_time_features(df)
    )

    aggregations = [
        F.avg("temperature").alias("avg_temperature"),
        F.avg("humidity").alias("avg_humidity"),
        F.avg("wind_speed").alias("avg_wind_speed"),
        F.max("wind_speed").alias("max_wind_speed"),
        F.avg("precipitation").alias("avg_precipitation"),
        F.max("precipitation").alias("max_precipitation"),
        F.avg("pressure").alias("avg_pressure"),
        F.count("*").alias("weather_readings"),
    ]

    if "is_high_wind" in time_df.columns:
        aggregations.append(
            F.sum(
                F.when(F.col("is_high_wind"), 1).otherwise(0)
            ).alias("high_wind_readings")
        )

    if "is_high_precipitation" in time_df.columns:
        aggregations.append(
            F.sum(
                F.when(
                    F.col("is_high_precipitation"),
                    1,
                ).otherwise(0)
            ).alias("high_precipitation_readings")
        )

    return (
        time_df
        .filter(F.col("zone_id").isNotNull())
        .groupBy(
            "zone_id",
            "zone_name",
            "zone_type",
            "hour_timestamp",
        )
        .agg(*aggregations)
        .orderBy("zone_id", "hour_timestamp")
    )