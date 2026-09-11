from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sparkcityx.database_load import _batches, get_load_config, load_dataframe


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
    rowcounts = iter([1, 1])

    def record_rowcount(*_args, **_kwargs) -> None:
        cursor.rowcount = next(rowcounts)

    cursor.executemany.side_effect = record_rowcount

    result = load_dataframe(connection, df, "traffic", batch_size=1)

    assert result.rows_inserted == 2
    assert result.rows_before == 10
    assert result.rows_after == 12
    assert cursor.executemany.call_count == 2


@patch("sparkcityx.database_load.validate_dataframe")
def test_loader_reports_inserted_rows_independently_from_table_delta(validate: MagicMock) -> None:
    validate.return_value = {"valid": True, "record_count": 2}
    row = {
        "sensor_id": "S1",
        "timestamp": "2026-01-01",
        "location_lat": 40.0,
        "location_lon": -74.0,
        "vehicle_count": 2,
        "avg_speed": 20.0,
        "congestion_level": "low",
        "road_type": "street",
    }
    df = MagicMock()
    df.select.return_value.toLocalIterator.return_value = iter([row, {**row, "sensor_id": "S2"}])
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(10,), (12,)]
    rowcounts = iter([0, 0])

    def record_rowcount(*_args, **_kwargs) -> None:
        cursor.rowcount = next(rowcounts)

    cursor.executemany.side_effect = record_rowcount

    result = load_dataframe(connection, df, "traffic", batch_size=1)

    assert result.rows_inserted == 0
    assert result.rows_before == 10
    assert result.rows_after == 12
