#!/usr/bin/env python3
"""Validate and safely load one generated dataset into shared PostgreSQL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pyspark.sql import SparkSession

from sparkcityx.database import connect_database
from sparkcityx.database_load import get_load_config, load_dataframe
from sparkcityx.loaders import load_dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = {
    "traffic": "traffic_sensors.csv",
    "air_quality": "air_quality.json",
    "weather": "weather_data.parquet",
    "energy": "energy_meters.csv",
    "city_zones": "city_zones.csv",
    "occupancy": "occupancy_data.csv",
    "fiscal": "fiscal_data.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=sorted(DEFAULT_FILES))
    parser.add_argument("--path", type=Path, help="Source file; defaults to data/raw")
    parser.add_argument("--env-file", type=Path, default=ROOT / "secrets" / ".env")
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument(
        "--apply", action="store_true", help="Insert new rows after validation"
    )
    args = parser.parse_args()

    source = args.path or ROOT / "data" / "raw" / DEFAULT_FILES[args.dataset]
    config = get_load_config(args.dataset)
    print(f"Dataset: {args.dataset}")
    print(f"Source: {source}")
    print(f"Target: sparkcity.{config['table']}")
    print("Conflict policy: keep existing primary-key rows")
    if not source.exists():
        raise SystemExit(f"Source file not found: {source}")
    if not args.apply:
        print("Preview only; rerun with --apply to validate and insert.")
        return

    if args.env_file.exists():
        load_dotenv(args.env_file, override=False)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    spark = (
        SparkSession.builder.master("local[1]")
        .appName(f"sparkcity-load-{args.dataset}")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    try:
        df = load_dataset(spark, source)
        with connect_database() as connection:
            result = load_dataframe(
                connection, df, args.dataset, batch_size=args.batch_size
            )
    finally:
        spark.stop()

    print("Load completed successfully")
    print(f"Source rows: {result.source_rows}")
    print(f"Rows before: {result.rows_before}")
    print(f"Rows inserted: {result.rows_inserted}")
    print(f"Rows after: {result.rows_after}")


if __name__ == "__main__":
    main()
