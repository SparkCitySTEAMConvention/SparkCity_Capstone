"""MLlib forecasting utilities for SparkCity weather analytics."""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F


@dataclass(frozen=True)
class WeatherForecastResult:
    """Trained forecasting model, test predictions, and metrics."""

    model: PipelineModel
    predictions: DataFrame
    metrics: dict[str, float]
    training_rows: int
    test_rows: int


def train_temperature_forecaster(
    hourly_df: DataFrame,
    *,
    train_ratio: float = 0.8,
) -> WeatherForecastResult:
    """Train a chronological MLlib model to predict next-hour temperature."""
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")

    time_window = Window.orderBy("hour_timestamp")

    prepared_df = (
        hourly_df
        .withColumn(
            "target_temperature",
            F.lead("avg_temperature", 1).over(time_window),
        )
        .withColumn("hour", F.hour("hour_timestamp"))
        .withColumn("month", F.month("hour_timestamp"))
        .withColumn(
            "hour_sin",
            F.sin(2 * F.lit(3.141592653589793) * F.col("hour") / 24),
        )
        .withColumn(
            "hour_cos",
            F.cos(2 * F.lit(3.141592653589793) * F.col("hour") / 24),
        )
        .withColumn(
            "month_sin",
            F.sin(2 * F.lit(3.141592653589793) * F.col("month") / 12),
        )
        .withColumn(
            "month_cos",
            F.cos(2 * F.lit(3.141592653589793) * F.col("month") / 12),
        )
        .dropna(
            subset=[
                "target_temperature",
                "avg_temperature",
                "avg_humidity",
                "avg_wind_speed",
                "avg_precipitation",
                "avg_pressure",
            ]
        )
        .withColumn(
            "_row_number",
            F.row_number().over(time_window),
        )
        .cache()
    )

    total_rows = prepared_df.count()

    if total_rows < 2:
        prepared_df.unpersist()
        raise ValueError("At least two complete hourly rows are required")

    training_rows = max(1, int(total_rows * train_ratio))

    if training_rows >= total_rows:
        training_rows = total_rows - 1

    training_df = prepared_df.filter(
        F.col("_row_number") <= training_rows
    )

    test_df = prepared_df.filter(
        F.col("_row_number") > training_rows
    )

    feature_columns = [
        "avg_temperature",
        "avg_humidity",
        "avg_wind_speed",
        "avg_precipitation",
        "avg_pressure",
        "hour_sin",
        "hour_cos",
        "month_sin",
        "month_cos",
    ]

    assembler = VectorAssembler(
        inputCols=feature_columns,
        outputCol="unscaled_features",
        handleInvalid="skip",
    )

    scaler = StandardScaler(
        inputCol="unscaled_features",
        outputCol="features",
        withMean=True,
        withStd=True,
    )

    regression = LinearRegression(
        featuresCol="features",
        labelCol="target_temperature",
        predictionCol="prediction",
        maxIter=100,
        regParam=0.01,
    )

    model = Pipeline(
        stages=[assembler, scaler, regression]
    ).fit(training_df)

    predictions = model.transform(test_df).cache()
    test_rows = predictions.count()

    metrics = {
        metric: float(
            RegressionEvaluator(
                labelCol="target_temperature",
                predictionCol="prediction",
                metricName=metric,
            ).evaluate(predictions)
        )
        for metric in ("rmse", "mae", "r2")
    }

    prepared_df.unpersist()

    return WeatherForecastResult(
        model=model,
        predictions=predictions,
        metrics=metrics,
        training_rows=training_rows,
        test_rows=test_rows,
    )