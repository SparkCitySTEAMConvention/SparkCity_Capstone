"""Command-line interface for the SparkCity weather pipeline."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from pyspark.sql import SparkSession

from .database import connect_database
from .weather_pipeline import run_weather_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the weather pipeline command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate weather data and optionally load it into PostgreSQL."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/raw/weather_data.parquet"),
        help="Path to the weather Parquet dataset.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("secrets/.env"),
        help="Path to the database environment file.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1_000,
        help="Number of database rows inserted per batch.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Load validated data into PostgreSQL.",
    )
    return parser


def create_spark_session() -> SparkSession:
    """Create the local Spark session used by scheduled pipeline runs."""
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("sparkcity-weather-pipeline")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("WARN")
    return session


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run one weather pipeline job and return a process exit code."""
    args = build_parser().parse_args(argv)

    if args.batch_size <= 0:
        raise ValueError("batch-size must be greater than zero")

    spark = create_spark_session()

    try:
        if args.apply:
            if args.env_file.exists():
                load_dotenv(args.env_file, override=False)

            with connect_database() as connection:
                result = run_weather_pipeline(
                    spark,
                    args.source,
                    connection=connection,
                    apply=True,
                    batch_size=args.batch_size,
                )
        else:
            result = run_weather_pipeline(
                spark,
                args.source,
                apply=False,
                batch_size=args.batch_size,
            )
    finally:
        spark.stop()

    print("Weather pipeline completed successfully")
    print(f"Source: {result.source}")
    print(f"Validated rows: {result.record_count:,}")
    print(f"Database applied: {result.applied}")

    if result.load_result is not None:
        print(f"Rows inserted: {result.load_result.rows_inserted:,}")

    return 0


def main() -> None:
    """Run the command-line interface."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()