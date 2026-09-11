from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sparkcityx.database_load import _batches, get_load_config, load_dataframe


EXPECTED_MAPPINGS = {
    "traffic": ("traffic_sensors", ["sensor_id", "timestamp"]),
    "air_quality": ("air_quality", ["sensor_id", "timestamp"]),
    "weather": ("weather_data", ["station_id", "timestamp"]),
    "energy": ("energy_meters", ["meter_id", "timestamp"]),
    "city_zones": ("city_zones", ["zone_id"]),
    "occupancy": ("occupancy_data", ["sensor_id", "timestamp"]),
    "fiscal": ("fiscal_data", ["sensor_id", "timestamp"]),
}


@pytest.mark.parametrize(
    ("dataset_type", "expected"), EXPECTED_MAPPINGS.items()
)
def test_all_dataset_mappings(dataset_type: str, expected: tuple[str, list[str]]) -> None:
    config = get_load_config(dataset_type)
    assert (config["table"], config["key"]) == expected


def test_load_config_uses_fiscal_aliases() -> None:
    assert get_load_config("financial_data")["table"] == "fiscal_data"


def test_batches_do_not_drop_rows() -> None:
    assert list(_batches(iter([(1,), (2,), (3,)]), 2)) == [[(1,), (2,)], [(3,)]]


def test_batch_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        load_dataframe(MagicMock(), MagicMock(), "traffic", batch_size=0)


@patch("sparkcityx.database_load.validate_dataframe")
def test_invalid_dataframe_is_never_written(validate: MagicMock) -> None:
    validate.return_value = {"valid": False, "missing_columns": ["sensor_id"]}
    connection = MagicMock()

    with pytest.raises(ValueError, match="validation failed"):
        load_dataframe(connection, MagicMock(), "traffic")

    connection.cursor.assert_not_called()


@patch("sparkcityx.database_load.validate_dataframe")
def test_loader_inserts_only_new_rows(validate: MagicMock) -> None:
    validate.return_value = {"valid": True, "record_count": 2}
    row_one = {
        "sensor_id": "S1",
        "timestamp": "2026-01-01",
        "location_lat": 40.0,
        "location_lon": -74.0,
        "vehicle_count": 2,
        "avg_speed": 20.0,
        "congestion_level": "low",
        "road_type": "street",
    }
    row_two = {**row_one, "sensor_id": "S2"}
    df = MagicMock()
    df.select.return_value.toLocalIterator.return_value = iter([row_one, row_two])
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(10,), (12,)]
    cursor.rowcount = 1

    result = load_dataframe(connection, df, "traffic", batch_size=1)

    assert result.rows_inserted == 2
    assert result.rows_before == 10
    assert result.rows_after == 12
    assert cursor.executemany.call_count == 2


@patch("sparkcityx.database_load.validate_dataframe")
def test_inserted_count_does_not_use_concurrent_table_growth(validate: MagicMock) -> None:
    validate.return_value = {"valid": True, "record_count": 1}
    row = {
        "zone_id": "Z1", "zone_name": "One", "zone_type": "park",
        "lat_min": 40.0, "lat_max": 41.0, "lon_min": -74.0,
        "lon_max": -73.0, "population": 10,
    }
    df = MagicMock()
    df.select.return_value.toLocalIterator.return_value = iter([row])
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(0,), (50,)]
    cursor.rowcount = 0

    result = load_dataframe(connection, df, "city_zones")

    assert result.rows_after == 50
    assert result.rows_inserted == 0
