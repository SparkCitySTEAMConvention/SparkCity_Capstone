"""Weather anomaly scoring and alerting for SparkCity."""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dataclass(frozen=True)
class WeatherAlertThresholds:
    """Caller-supplied thresholds matching the dataset's confirmed units."""

    minimum_temperature: float
    maximum_temperature: float
    maximum_wind_speed: float
    maximum_precipitation: float
    minimum_pressure: float
    maximum_pressure: float


def add_threshold_alerts(
    df: DataFrame,
    thresholds: WeatherAlertThresholds,
) -> DataFrame:
    """Add deterministic weather alert flags and investigation severity."""
    result = (
        df
        .withColumn(
            "low_temperature_alert",
            F.col("temperature") < thresholds.minimum_temperature,
        )
        .withColumn(
            "high_temperature_alert",
            F.col("temperature") > thresholds.maximum_temperature,
        )
        .withColumn(
            "high_wind_alert",
            F.col("wind_speed") > thresholds.maximum_wind_speed,
        )
        .withColumn(
            "high_precipitation_alert",
            F.col("precipitation")
            > thresholds.maximum_precipitation,
        )
        .withColumn(
            "low_pressure_alert",
            F.col("pressure") < thresholds.minimum_pressure,
        )
        .withColumn(
            "high_pressure_alert",
            F.col("pressure") > thresholds.maximum_pressure,
        )
    )

    alert_columns = [
        "low_temperature_alert",
        "high_temperature_alert",
        "high_wind_alert",
        "high_precipitation_alert",
        "low_pressure_alert",
        "high_pressure_alert",
    ]

    alert_count = sum(
        F.when(F.col(column), 1).otherwise(0)
        for column in alert_columns
    )

    return (
        result
        .withColumn("alert_count", alert_count)
        .withColumn(
            "alert_severity",
            F.when(F.col("alert_count") >= 2, F.lit("CRITICAL"))
            .when(F.col("alert_count") == 1, F.lit("WARNING"))
            .otherwise(F.lit("NORMAL")),
        )
        .withColumn(
            "requires_investigation",
            F.col("alert_count") > 0,
        )
        .withColumn(
            "alert_reasons",
            F.concat_ws(
                ",",
                F.when(
                    F.col("low_temperature_alert"),
                    F.lit("LOW_TEMPERATURE"),
                ),
                F.when(
                    F.col("high_temperature_alert"),
                    F.lit("HIGH_TEMPERATURE"),
                ),
                F.when(
                    F.col("high_wind_alert"),
                    F.lit("HIGH_WIND"),
                ),
                F.when(
                    F.col("high_precipitation_alert"),
                    F.lit("HIGH_PRECIPITATION"),
                ),
                F.when(
                    F.col("low_pressure_alert"),
                    F.lit("LOW_PRESSURE"),
                ),
                F.when(
                    F.col("high_pressure_alert"),
                    F.lit("HIGH_PRESSURE"),
                ),
            ),
        )
        .withColumn(
            "investigation_status",
            F.when(
                F.col("requires_investigation"),
                F.lit("OPEN"),
            ).otherwise(F.lit("NOT_REQUIRED")),
        )
        .withColumn(
            "recommended_action",
            F.when(
                F.col("alert_severity") == "CRITICAL",
                F.lit("IMMEDIATE_REVIEW"),
            )
            .when(
                F.col("alert_severity") == "WARNING",
                F.lit("REVIEW_READING"),
            )
            .otherwise(F.lit("NO_ACTION")),
        )
    )



def add_multivariate_anomaly_scores(
    df: DataFrame,
    *,
    feature_columns: tuple[str, ...] = (
        "temperature",
        "humidity",
        "wind_speed",
        "precipitation",
        "pressure",
    ),
    score_threshold: float = 3.0,
) -> DataFrame:
    """Score multivariate anomalies using combined absolute z-scores."""
    statistics = df.agg(
        *[
            expression
            for column in feature_columns
            for expression in (
                F.avg(column).alias(f"{column}_mean"),
                F.stddev(column).alias(f"{column}_stddev"),
            )
        ]
    ).first()

    result = df
    zscore_columns = []

    for column in feature_columns:
        mean = statistics[f"{column}_mean"]
        stddev = statistics[f"{column}_stddev"]
        zscore_column = f"{column}_zscore"
        zscore_columns.append(zscore_column)

        if stddev in (None, 0):
            result = result.withColumn(
                zscore_column,
                F.lit(0.0),
            )
        else:
            result = result.withColumn(
                zscore_column,
                F.abs(
                    (F.col(column) - F.lit(mean))
                    / F.lit(stddev)
                ),
            )

    squared_score = sum(
        F.pow(F.coalesce(F.col(column), F.lit(0.0)), 2)
        for column in zscore_columns
    )

    return (
        result
        .withColumn(
            "multivariate_anomaly_score",
            F.sqrt(squared_score),
        )
        .withColumn(
            "is_multivariate_anomaly",
            F.col("multivariate_anomaly_score")
            > F.lit(score_threshold),
        )
    )