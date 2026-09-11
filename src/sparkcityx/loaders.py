"""Spark file loaders kept separate from dataframe validation rules."""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession


def load_dataset(
    spark: SparkSession,
    path: str | Path,
    *,
    file_format: str | None = None,
) -> DataFrame:
    """Load CSV, JSON array/JSON-lines, or Parquet into a Spark DataFrame."""
    source = str(path)
    source_path = Path(source)
    format_name = (file_format or source_path.suffix.lstrip(".")).lower()
    if format_name == "csv":
        return spark.read.option("header", True).option("inferSchema", True).csv(source)
    if format_name in {"json", "jsonl", "ndjson"}:
        multiline = (
            format_name == "json"
            and source_path.is_file()
            and _starts_with_json_array(source_path)
        )
        return spark.read.option("multiLine", multiline).json(source)
    if format_name in {"parquet", "pq"}:
        return spark.read.parquet(source)
    raise ValueError(f"Unsupported file format {format_name!r}; use csv, json, or parquet")


def _starts_with_json_array(path: Path) -> bool:
    """Identify local JSON arrays without parsing the complete dataset in Python."""
    with path.open("r", encoding="utf-8") as handle:
        while character := handle.read(1):
            if not character.isspace():
                return character == "["
    return False
