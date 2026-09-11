from __future__ import annotations

import pytest

from sparkcityx.data_quality import get_validation_config, validate_dataframe
from sparkcityx.loaders import load_dataset


@pytest.mark.parametrize("alias", ["fiscal", "financial", "financial_data", "fiscal_data"])
def test_financial_aliases_share_rules(alias: str) -> None:
    assert get_validation_config(alias) == get_validation_config("fiscal")


def test_config_is_a_defensive_copy() -> None:
    config = get_validation_config("traffic")
    config["required_columns"].clear()
    assert get_validation_config("traffic")["required_columns"]


def test_unknown_dataset_has_useful_error() -> None:
    with pytest.raises(ValueError, match="Unknown dataset type"):
        get_validation_config("parking")


def test_validation_reports_quality_failures(spark) -> None:
    columns = get_validation_config("traffic")["required_columns"]
    row = ("S1", "2026-01-01", 95.0, -74.0, -1, 20.0, "impossible", "street")
    df = spark.createDataFrame([row, row], columns)

    report = validate_dataframe(df, "traffic")

    assert report["valid"] is False
    assert report["record_count"] == 2
    assert report["duplicate_count"] == 1
    assert report["range_violations"] == {"location_lat": 2, "vehicle_count": 2}
    assert report["value_violations"] == {"congestion_level": 2}


def test_empty_dataframe_is_invalid(spark) -> None:
    df = spark.createDataFrame([], "sensor_id string, timestamp string")
    report = validate_dataframe(df, "traffic")
    assert report["valid"] is False
    assert report["record_count"] == 0


def test_validation_reports_missing_null_and_incompatible_columns(spark) -> None:
    df = spark.createDataFrame(
        [(None, "2026-01-01", "not-a-number")],
        "sensor_id string, timestamp string, vehicle_count string",
    )

    report = validate_dataframe(df, "traffic")

    assert "avg_speed" in report["missing_columns"]
    assert report["null_counts"] == {"sensor_id": 1}
    assert report["non_numeric_columns"] == ["vehicle_count"]
    assert report["valid"] is False


def test_duplicate_check_requires_full_key(spark) -> None:
    df = spark.createDataFrame(
        [("S1", 10.0), ("S1", 12.0)],
        "sensor_id string, avg_speed double",
    )
    report = validate_dataframe(df, "traffic")
    assert report["duplicate_count"] == 0
    assert "timestamp" in report["missing_columns"]


def test_validation_reports_cross_field_schema_failures(spark) -> None:
    zone_df = spark.createDataFrame(
        [("Z1", "Zone 1", "residential", 41.0, 40.0, -74.0, -73.0, 100)],
        (
            "zone_id string, zone_name string, zone_type string, lat_min double, "
            "lat_max double, lon_min double, lon_max double, population int"
        ),
    )
    occupancy_df = spark.createDataFrame(
        [("S1", "2026-01-01", 40.0, -74.0, 10, 11, 20)],
        (
            "sensor_id string, timestamp string, location_lat double, "
            "location_lon double, available_rooms int, occupied_rooms int, guests int"
        ),
    )

    zone_report = validate_dataframe(zone_df, "city_zones")
    occupancy_report = validate_dataframe(occupancy_df, "occupancy")

    assert zone_report["cross_field_violations"] == {"lat_bounds": 1}
    assert zone_report["valid"] is False
    assert occupancy_report["cross_field_violations"] == {"occupied_vs_available_rooms": 1}
    assert occupancy_report["valid"] is False


def test_validation_reports_invalid_timestamps(spark) -> None:
    columns = get_validation_config("traffic")["required_columns"]
    df = spark.createDataFrame(
        [("S1", "not-a-timestamp", 40.0, -74.0, 2, 20.0, "low", "street")],
        columns,
    )

    report = validate_dataframe(df, "traffic")

    assert report["timestamp_violations"] == {"timestamp": 1}
    assert report["valid"] is False


def test_json_directory_load_avoids_local_file_probe(spark, tmp_path) -> None:
    dataset_dir = tmp_path / "json-data"
    dataset_dir.mkdir()
    (dataset_dir / "part-1.json").write_text('{"sensor_id":"S1","timestamp":"2026-01-01"}\n')
    (dataset_dir / "part-2.json").write_text('{"sensor_id":"S2","timestamp":"2026-01-01"}\n')

    df = load_dataset(spark, dataset_dir, file_format="json")
    assert df.count() == 2
