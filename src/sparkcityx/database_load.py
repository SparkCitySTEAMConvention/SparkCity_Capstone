"""Validated, idempotent loading from Spark DataFrames into PostgreSQL."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import islice
from typing import Any, Iterable, Iterator, Sequence

from psycopg import Connection, sql
from pyspark.sql import DataFrame

from .data_quality import normalize_dataset_type, validate_dataframe


_LOAD_CONFIGS: dict[str, dict[str, list[str] | str]] = {
    "traffic": {
        "table": "traffic_sensors",
        "columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "vehicle_count", "avg_speed", "congestion_level", "road_type",
        ],
        "key": ["sensor_id", "timestamp"],
    },
    "air_quality": {
        "table": "air_quality",
        "columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon", "pm25",
            "pm10", "no2", "co", "temperature", "humidity",
        ],
        "key": ["sensor_id", "timestamp"],
    },
    "weather": {
        "table": "weather_data",
        "columns": [
            "station_id", "timestamp", "location_lat", "location_lon",
            "temperature", "humidity", "wind_speed", "wind_direction",
            "precipitation", "pressure",
        ],
        "key": ["station_id", "timestamp"],
    },
    "energy": {
        "table": "energy_meters",
        "columns": [
            "meter_id", "timestamp", "building_type", "location_lat",
            "location_lon", "power_consumption", "voltage", "current",
            "power_factor",
        ],
        "key": ["meter_id", "timestamp"],
    },
    "city_zones": {
        "table": "city_zones",
        "columns": [
            "zone_id", "zone_name", "zone_type", "lat_min", "lat_max",
            "lon_min", "lon_max", "population",
        ],
        "key": ["zone_id"],
    },
    "occupancy": {
        "table": "occupancy_data",
        "columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "available_rooms", "occupied_rooms", "guests",
        ],
        "key": ["sensor_id", "timestamp"],
    },
    "fiscal": {
        "table": "fiscal_data",
        "columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "expense", "revenue",
        ],
        "key": ["sensor_id", "timestamp"],
    },
}


@dataclass(frozen=True)
class LoadResult:
    dataset_type: str
    table: str
    source_rows: int
    rows_before: int
    rows_after: int
    rows_inserted: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_load_config(dataset_type: str) -> dict[str, list[str] | str]:
    """Resolve loading metadata using the validator's canonical dataset name."""
    canonical = normalize_dataset_type(dataset_type)
    config = _LOAD_CONFIGS[canonical]
    return {
        "dataset_type": canonical,
        "table": config["table"],
        "columns": list(config["columns"]),
        "key": list(config["key"]),
    }


def _batches(rows: Iterable[Sequence[Any]], size: int) -> Iterator[list[Sequence[Any]]]:
    iterator = iter(rows)
    while batch := list(islice(iterator, size)):
        yield batch


def load_dataframe(
    connection: Connection,
    df: DataFrame,
    dataset_type: str,
    *,
    batch_size: int = 1_000,
) -> LoadResult:
    """Validate and insert new primary-key rows without replacing existing data."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    report = validate_dataframe(df, dataset_type)
    if not report["valid"]:
        raise ValueError(f"Dataset validation failed: {report}")

    config = get_load_config(dataset_type)
    table = str(config["table"])
    columns = list(config["columns"])
    key_columns = list(config["key"])
    count_query = sql.SQL("SELECT count(*) FROM {}.{}").format(
        sql.Identifier("sparkcity"), sql.Identifier(table)
    )
    with connection.cursor() as cursor:
        cursor.execute(count_query)
        rows_before = cursor.fetchone()[0]
        selected_rows = df.select(*columns).toLocalIterator()
        values = (tuple(row[column] for column in columns) for row in selected_rows)
        rows_inserted = 0
        for batch in _batches(values, batch_size):
            values_clause = sql.SQL(", ").join(
                sql.SQL("({})").format(sql.SQL(", ").join(sql.Placeholder() for _ in columns))
                for _ in batch
            )
            insert_query = sql.SQL(
                "INSERT INTO {}.{} ({}) VALUES {} ON CONFLICT ({}) DO NOTHING RETURNING 1"
            ).format(
                sql.Identifier("sparkcity"),
                sql.Identifier(table),
                sql.SQL(", ").join(map(sql.Identifier, columns)),
                values_clause,
                sql.SQL(", ").join(map(sql.Identifier, key_columns)),
            )
            parameters = [value for row in batch for value in row]
            cursor.execute(insert_query, parameters)
            rows_inserted += len(cursor.fetchall())
        cursor.execute(count_query)
        rows_after = cursor.fetchone()[0]

    return LoadResult(
        dataset_type=str(config["dataset_type"]),
        table=f"sparkcity.{table}",
        source_rows=report["record_count"],
        rows_before=rows_before,
        rows_after=rows_after,
        rows_inserted=rows_inserted,
    )
