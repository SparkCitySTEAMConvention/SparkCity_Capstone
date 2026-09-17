"""Mobility and traffic dashboard data queries."""

from __future__ import annotations

from typing import Any

from sparkcityx.database import connect_database


def get_mobility_summary(month: int | None = None) -> dict[str, Any]:
    """Return summary metrics for the Mobility & Traffic dashboard."""

    month_filter = ""
    params = ()

    if month is not None:
        month_filter = """
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        """
        params = (month,)

    query = f"""
        SELECT
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count,
            ROUND(AVG(avg_speed)::numeric, 2) AS average_speed_kmh,
            ROUND(
                (
                    COUNT(*) FILTER (WHERE congestion_level = 'high')::numeric
                    / NULLIF(COUNT(*), 0)
                ) * 100,
                2
            ) AS high_congestion_percent
        FROM sparkcity.traffic_sensors
        {month_filter};
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()

    peak_hour_query = f"""
        SELECT
            EXTRACT(HOUR FROM timestamp)::integer AS hour,
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count
        FROM sparkcity.traffic_sensors
        {month_filter}
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY average_vehicle_count DESC
        LIMIT 1;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(peak_hour_query, params)
            peak_row = cursor.fetchone()

    if (
        row is None
        or row[0] is None
        or peak_row is None
    ):
        return {}

    return {
        "average_vehicle_count": float(row[0]),
        "average_speed_kmh": float(row[1]),
        "high_congestion_percent": float(row[2]),
        "peak_hour": int(peak_row[0]),
        "peak_hour_average_vehicle_count": float(peak_row[1]),
    }

def get_hourly_traffic(
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Return average traffic volume and speed for each hour of the day."""

    month_filter = ""
    params = ()

    if month is not None:
        month_filter = """
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        """
        params = (month,)

    query = f"""
        SELECT
            EXTRACT(HOUR FROM timestamp)::integer AS hour,
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count,
            ROUND(AVG(avg_speed)::numeric, 2) AS average_speed_kmh
        FROM sparkcity.traffic_sensors
        {month_filter}
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY hour;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "hour": int(row[0]),
            "average_vehicle_count": float(row[1]),
            "average_speed_kmh": float(row[2]),
        }
        for row in rows
    ]

def get_congestion_breakdown(
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Return traffic record counts and percentages by congestion level."""

    month_filter = ""
    params = ()

    if month is not None:
        month_filter = """
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        """
        params = (month,)

    query = f"""
        SELECT
            congestion_level,
            COUNT(*) AS record_count,
            ROUND(
                COUNT(*)::numeric * 100 / SUM(COUNT(*)) OVER (),
                2
            ) AS percentage
        FROM sparkcity.traffic_sensors
        {month_filter}
        GROUP BY congestion_level
        ORDER BY
            CASE congestion_level
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "congestion_level": row[0],
            "record_count": int(row[1]),
            "percentage": float(row[2]),
        }
        for row in rows
    ]

def get_road_type_summary(
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Return traffic and congestion metrics grouped by road type."""

    month_filter = ""
    params = ()

    if month is not None:
        month_filter = """
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        """
        params = (month,)

    query = f"""
        SELECT
            road_type,
            COUNT(*) AS record_count,
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count,
            ROUND(AVG(avg_speed)::numeric, 2) AS average_speed_kmh,
            ROUND(
                COUNT(*) FILTER (WHERE congestion_level = 'high')::numeric
                * 100 / COUNT(*),
                2
            ) AS high_congestion_percent
        FROM sparkcity.traffic_sensors
        {month_filter}
        GROUP BY road_type
        ORDER BY average_vehicle_count DESC;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "road_type": row[0],
            "record_count": int(row[1]),
            "average_vehicle_count": float(row[2]),
            "average_speed_kmh": float(row[3]),
            "high_congestion_percent": float(row[4]),
        }
        for row in rows
    ]

def get_sensor_summary(
    month: int | None = None,
) -> list[dict[str, Any]]:
    """Return summarized traffic conditions for each sensor location."""

    month_filter = ""
    params = ()

    if month is not None:
        month_filter = """
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        """
        params = (month,)

    query = f"""
        SELECT
            sensor_id,
            COUNT(*) AS observation_count,
            ROUND(AVG(location_lat)::numeric, 6) AS latitude,
            ROUND(AVG(location_lon)::numeric, 6) AS longitude,
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count,
            ROUND(AVG(avg_speed)::numeric, 2) AS average_speed_kmh,
            ROUND(
                COUNT(*) FILTER (WHERE congestion_level = 'high')::numeric
                * 100 / COUNT(*),
                2
            ) AS high_congestion_percent
        FROM sparkcity.traffic_sensors
        {month_filter}
        GROUP BY sensor_id
        ORDER BY high_congestion_percent DESC;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

    return [
        {
            "sensor_id": row[0],
            "observation_count": int(row[1]),
            "latitude": float(row[2]),
            "longitude": float(row[3]),
            "average_vehicle_count": float(row[4]),
            "average_speed_kmh": float(row[5]),
            "high_congestion_percent": float(row[6]),
        }
        for row in rows
    ]