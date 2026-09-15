"""Production orchestration for SparkCity weather ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from psycopg import Connection
from pyspark.sql import SparkSession

from .database_load import LoadResult, load_dataframe
from .data_quality import validate_dataframe
from .loaders import load_dataset


@dataclass(frozen=True)
class WeatherPipelineResult:
    """Summary of one weather ingestion pipeline run."""

    source: str
    valid: bool
    record_count: int
    applied: bool
    validation_report: dict[str, Any]
    load_result: LoadResult | None


def run_weather_pipeline(
    spark: SparkSession,
    source: str | Path,
    *,
    connection: Connection | None = None,
    apply: bool = False,
    batch_size: int = 1_000,
) -> WeatherPipelineResult:
    """Validate weather data and optionally load it into PostgreSQL."""
    source_path = Path(source)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Weather source not found: {source_path}"
        )

    weather_df = load_dataset(spark, source_path)
    report = validate_dataframe(weather_df, "weather")

    if not report["valid"]:
        raise ValueError(
            f"Weather validation failed: {report}"
        )

    load_result = None

    if apply:
        if connection is None:
            raise ValueError(
                "A database connection is required when apply=True"
            )

        load_result = load_dataframe(
            connection,
            weather_df,
            "weather",
            batch_size=batch_size,
        )

    return WeatherPipelineResult(
        source=str(source_path),
        valid=True,
        record_count=report["record_count"],
        applied=apply,
        validation_report=report,
        load_result=load_result,
    )