"""Reusable, file-format-independent validation for Spark DataFrames."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import NumericType


_COMMON_LOCATION_RANGES = {
    "location_lat": {"min": -90.0, "max": 90.0},
    "location_lon": {"min": -180.0, "max": 180.0},
}

_CONFIGS: dict[str, dict[str, Any]] = {
    "traffic": {
        "required_columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "vehicle_count", "avg_speed", "congestion_level", "road_type",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "vehicle_count": {"min": 0},
            "avg_speed": {"min": 0},
        },
        "allowed_values": {"congestion_level": ["low", "medium", "high"]},
        "duplicate_columns": ["sensor_id", "timestamp"],
    },
    "air_quality": {
        "required_columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon", "pm25",
            "pm10", "no2", "co", "temperature", "humidity",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "pm25": {"min": 0}, "pm10": {"min": 0}, "no2": {"min": 0},
            "co": {"min": 0}, "humidity": {"min": 0, "max": 100},
        },
        "duplicate_columns": ["sensor_id", "timestamp"],
    },
    "weather": {
        "required_columns": [
            "station_id", "timestamp", "location_lat", "location_lon",
            "temperature", "humidity", "wind_speed", "wind_direction",
            "precipitation", "pressure",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "humidity": {"min": 0, "max": 100},
            "wind_speed": {"min": 0},
            "wind_direction": {"min": 0, "max": 360},
            "precipitation": {"min": 0},
            "pressure": {"min": 0},
        },
        "duplicate_columns": ["station_id", "timestamp"],
    },
    "energy": {
        "required_columns": [
            "meter_id", "timestamp", "building_type", "location_lat",
            "location_lon", "power_consumption", "voltage", "current",
            "power_factor",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "power_consumption": {"min": 0}, "voltage": {"min": 0},
            "current": {"min": 0}, "power_factor": {"min": 0, "max": 1},
        },
        "duplicate_columns": ["meter_id", "timestamp"],
    },
    "city_zones": {
        "required_columns": [
            "zone_id", "zone_name", "zone_type", "lat_min", "lat_max",
            "lon_min", "lon_max", "population",
        ],
        "ranges": {
            "lat_min": {"min": -90, "max": 90},
            "lat_max": {"min": -90, "max": 90},
            "lon_min": {"min": -180, "max": 180},
            "lon_max": {"min": -180, "max": 180},
            "population": {"min": 0},
        },
        "cross_field_rules": [
            {"name": "lat_bounds", "left": "lat_min", "right": "lat_max"},
            {"name": "lon_bounds", "left": "lon_min", "right": "lon_max"},
        ],
        "duplicate_columns": ["zone_id"],
    },
    "occupancy": {
        "required_columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "available_rooms", "occupied_rooms", "guests",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "available_rooms": {"min": 0}, "occupied_rooms": {"min": 0},
            "guests": {"min": 0},
        },
        "cross_field_rules": [
            {
                "name": "occupied_vs_available_rooms",
                "left": "occupied_rooms",
                "right": "available_rooms",
            }
        ],
        "duplicate_columns": ["sensor_id", "timestamp"],
    },
    "fiscal": {
        "required_columns": [
            "sensor_id", "timestamp", "location_lat", "location_lon",
            "expense", "revenue",
        ],
        "ranges": {
            **_COMMON_LOCATION_RANGES,
            "expense": {"min": 0}, "revenue": {"min": 0},
        },
        "duplicate_columns": ["sensor_id", "timestamp"],
    },
}

_ALIASES = {
    "air": "air_quality", "air_quality_data": "air_quality",
    "traffic_sensors": "traffic", "weather_data": "weather",
    "energy_meters": "energy", "zones": "city_zones", "city_zone": "city_zones",
    "occupancy_data": "occupancy", "financial": "fiscal",
    "financial_data": "fiscal", "fiscal_data": "fiscal",
}


def normalize_dataset_type(dataset_type: str) -> str:
    """Return the canonical configured name for a dataset type or alias."""
    name = dataset_type.strip().lower().replace("-", "_").replace(" ", "_")
    name = _ALIASES.get(name, name)
    if name not in _CONFIGS:
        supported = ", ".join(sorted(_CONFIGS))
        raise ValueError(f"Unknown dataset type {dataset_type!r}. Supported types: {supported}")
    return name


def get_validation_config(dataset_type: str) -> dict[str, Any]:
    """Return an independent copy of the rules for ``dataset_type``."""
    return deepcopy(_CONFIGS[normalize_dataset_type(dataset_type)])


def validate_dataframe(df: DataFrame, dataset_type: str) -> dict[str, Any]:
    """Evaluate a Spark DataFrame and return a notebook-friendly validation report."""
    config = get_validation_config(dataset_type)
    dataset = normalize_dataset_type(dataset_type)
    columns = set(df.columns)
    missing_columns = [c for c in config["required_columns"] if c not in columns]
    present_required = [c for c in config["required_columns"] if c in columns]
    numeric_rule_columns = set(config.get("ranges", {}))
    non_numeric_columns = [
        field.name for field in df.schema.fields
        if field.name in numeric_rule_columns and not isinstance(field.dataType, NumericType)
    ]

    record_count = df.count()
    null_counts: dict[str, int] = {}
    if present_required:
        null_row = df.agg(*[
            F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).cast("long").alias(c)
            for c in present_required
        ]).first()
        null_counts = null_row.asDict() if null_row else {}

    duplicate_count = 0
    duplicate_columns = config["duplicate_columns"]
    if all(column in columns for column in duplicate_columns):
        duplicate_count = (
            df.groupBy(*duplicate_columns).count().filter(F.col("count") > 1)
            .agg(F.sum(F.col("count") - 1).alias("duplicates")).first()["duplicates"] or 0
        )

    range_violations: dict[str, int] = {}
    for column, limits in config.get("ranges", {}).items():
        if column not in columns or column in non_numeric_columns:
            continue
        invalid = F.lit(False)
        if "min" in limits:
            invalid = invalid | (F.col(column) < F.lit(limits["min"]))
        if "max" in limits:
            invalid = invalid | (F.col(column) > F.lit(limits["max"]))
        range_violations[column] = df.filter(invalid).count()

    value_violations: dict[str, int] = {}
    for column, allowed in config.get("allowed_values", {}).items():
        if column in columns:
            value_violations[column] = df.filter(
                F.col(column).isNotNull() & ~F.col(column).isin(allowed)
            ).count()

    cross_field_violations: dict[str, int] = {}
    for rule in config.get("cross_field_rules", []):
        left = rule["left"]
        right = rule["right"]
        if (
            left not in columns or right not in columns
            or left in non_numeric_columns or right in non_numeric_columns
        ):
            continue
        cross_field_violations[rule["name"]] = df.filter(F.col(left) > F.col(right)).count()

    numeric_columns = [
        field.name for field in df.schema.fields
        if isinstance(field.dataType, NumericType)
    ]
    numeric_summary = [
        row.asDict() for row in df.select(*numeric_columns).summary().collect()
    ] if numeric_columns and record_count else []

    issues = {
        "missing_columns": missing_columns,
        "non_numeric_columns": non_numeric_columns,
        "null_counts": {k: int(v) for k, v in null_counts.items() if v},
        "duplicate_count": int(duplicate_count),
        "range_violations": {k: v for k, v in range_violations.items() if v},
        "value_violations": {k: v for k, v in value_violations.items() if v},
        "cross_field_violations": {k: v for k, v in cross_field_violations.items() if v},
    }
    valid = record_count > 0 and not any([
        issues["missing_columns"], issues["non_numeric_columns"],
        issues["null_counts"], issues["duplicate_count"],
        issues["range_violations"], issues["value_violations"],
        issues["cross_field_violations"],
    ])
    return {
        "dataset_type": dataset,
        "valid": valid,
        "record_count": record_count,
        **issues,
        "numeric_summary": numeric_summary,
    }
