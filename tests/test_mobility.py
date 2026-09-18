from __future__ import annotations

from unittest.mock import MagicMock, patch

from sparkcityx.mobility import (
    get_congestion_breakdown,
    get_hourly_traffic,
    get_mobility_summary,
    get_road_type_summary,
    get_sensor_summary,
)

@patch("sparkcityx.mobility.connect_database")
def test_get_mobility_summary_returns_expected_metrics(
    connect_database: MagicMock,
) -> None:
    cursor = (
        connect_database.return_value
        .__enter__.return_value
        .cursor.return_value
        .__enter__.return_value
    )

    cursor.fetchone.side_effect = [
        (76.40, 18.93, 35.53),
        (17, 107.60),
    ]

    result = get_mobility_summary()

    assert result == {
        "average_vehicle_count": 76.4,
        "average_speed_kmh": 18.93,
        "high_congestion_percent": 35.53,
        "peak_hour": 17,
        "peak_hour_average_vehicle_count": 107.6,
    }

@patch("sparkcityx.mobility.connect_database")
def test_get_hourly_traffic_returns_hourly_metrics(
    connect_database: MagicMock,
) -> None:
    cursor = (
        connect_database.return_value
        .__enter__.return_value
        .cursor.return_value
        .__enter__.return_value
    )

    cursor.fetchall.return_value = [
        (0, 69.52, 19.73),
        (7, 104.25, 16.30),
        (17, 107.60, 15.76),
    ]

    result = get_hourly_traffic()

    assert result == [
        {
            "hour": 0,
            "average_vehicle_count": 69.52,
            "average_speed_kmh": 19.73,
        },
        {
            "hour": 7,
            "average_vehicle_count": 104.25,
            "average_speed_kmh": 16.30,
        },
        {
            "hour": 17,
            "average_vehicle_count": 107.60,
            "average_speed_kmh": 15.76,
        },
    ]

@patch("sparkcityx.mobility.connect_database")
def test_get_congestion_breakdown_returns_expected_percentages(
    connect_database: MagicMock,
) -> None:
    cursor = (
        connect_database.return_value
        .__enter__.return_value
        .cursor.return_value
        .__enter__.return_value
    )

    cursor.fetchall.return_value = [
        ("high", 12789, 35.53),
        ("medium", 13852, 38.48),
        ("low", 9359, 26.00),
    ]

    result = get_congestion_breakdown()

    assert result == [
        {
            "congestion_level": "high",
            "record_count": 12789,
            "percentage": 35.53,
        },
        {
            "congestion_level": "medium",
            "record_count": 13852,
            "percentage": 38.48,
        },
        {
            "congestion_level": "low",
            "record_count": 9359,
            "percentage": 26.00,
        },
    ]

@patch("sparkcityx.mobility.connect_database")
def test_get_road_type_summary_returns_expected_metrics(
    connect_database: MagicMock,
) -> None:
    cursor = (
        connect_database.return_value
        .__enter__.return_value
        .cursor.return_value
        .__enter__.return_value
    )

    cursor.fetchall.return_value = [
        ("school_zone", 7121, 76.82, 8.52, 34.66),
        ("highway", 7201, 76.40, 36.12, 36.09),
        ("arterial", 7164, 76.17, 25.00, 36.59),
    ]

    result = get_road_type_summary()

    assert result == [
        {
            "road_type": "school_zone",
            "record_count": 7121,
            "average_vehicle_count": 76.82,
            "average_speed_kmh": 8.52,
            "high_congestion_percent": 34.66,
        },
        {
            "road_type": "highway",
            "record_count": 7201,
            "average_vehicle_count": 76.40,
            "average_speed_kmh": 36.12,
            "high_congestion_percent": 36.09,
        },
        {
            "road_type": "arterial",
            "record_count": 7164,
            "average_vehicle_count": 76.17,
            "average_speed_kmh": 25.00,
            "high_congestion_percent": 36.59,
        },
    ]

@patch("sparkcityx.mobility.connect_database")
def test_get_sensor_summary_returns_expected_metrics(
    connect_database: MagicMock,
) -> None:
    cursor = (
        connect_database.return_value
        .__enter__.return_value
        .cursor.return_value
        .__enter__.return_value
    )

    cursor.fetchall.return_value = [
        (
            "TRF-1269",
            12,
            40.758738,
            -73.961754,
            99.58,
            16.57,
            83.33,
        ),
        (
            "TRF-2039",
            12,
            40.762103,
            -73.967051,
            87.58,
            19.97,
            75.00,
        ),
    ]

    result = get_sensor_summary()

    assert result == [
        {
            "sensor_id": "TRF-1269",
            "observation_count": 12,
            "latitude": 40.758738,
            "longitude": -73.961754,
            "average_vehicle_count": 99.58,
            "average_speed_kmh": 16.57,
            "high_congestion_percent": 83.33,
        },
        {
            "sensor_id": "TRF-2039",
            "observation_count": 12,
            "latitude": 40.762103,
            "longitude": -73.967051,
            "average_vehicle_count": 87.58,
            "average_speed_kmh": 19.97,
            "high_congestion_percent": 75.00,
        },
    ]