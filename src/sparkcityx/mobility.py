"""Mobility and traffic dashboard data queries."""

from __future__ import annotations
from typing import Any
from sparkcityx.database import connect_database

def has_month_data(month: int) -> bool:
    """Return True when traffic sensor observations exist for a month."""
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM sparkcity.traffic_sensors
            WHERE EXTRACT(MONTH FROM timestamp) = %s
        );
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (month,))
            row = cursor.fetchone()

    return bool(row and row[0])

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


def get_convention_mobility_outlook() -> dict[str, Any]:
    """
    Return historical mobility conditions for convention planning.

    The recommended convention is April 6-8, 2027, which falls
    Tuesday through Thursday. This query uses observed April
    Tuesday-Thursday traffic as the historical planning baseline.
    """

    summary_query = """
        SELECT
            ROUND(AVG(vehicle_count)::numeric, 2),
            ROUND(AVG(avg_speed)::numeric, 2),
            ROUND(
                COUNT(*) FILTER (WHERE congestion_level = 'high')::numeric
                * 100 / NULLIF(COUNT(*), 0),
                2
            )
        FROM sparkcity.traffic_sensors
        WHERE EXTRACT(MONTH FROM timestamp) = 4
          AND EXTRACT(ISODOW FROM timestamp) BETWEEN 2 AND 4;
    """

    peak_query = """
        SELECT
            EXTRACT(HOUR FROM timestamp)::integer AS hour,
            ROUND(AVG(vehicle_count)::numeric, 2) AS average_vehicle_count
        FROM sparkcity.traffic_sensors
        WHERE EXTRACT(MONTH FROM timestamp) = 4
          AND EXTRACT(ISODOW FROM timestamp) BETWEEN 2 AND 4
        GROUP BY EXTRACT(HOUR FROM timestamp)
        ORDER BY average_vehicle_count DESC
        LIMIT 1;
    """

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(summary_query)
            summary_row = cursor.fetchone()

            cursor.execute(peak_query)
            peak_row = cursor.fetchone()

    if (
        summary_row is None
        or summary_row[0] is None
        or peak_row is None
    ):
        return {}

    high_congestion_percent = float(summary_row[2])

    if high_congestion_percent < 30:
        outlook = "Lower"
    elif high_congestion_percent < 40:
        outlook = "Moderate"
    else:
        outlook = "Elevated"

    return {
        "convention_dates": "April 6–8, 2027",
        "average_vehicle_count": float(summary_row[0]),
        "average_speed_kmh": float(summary_row[1]),
        "high_congestion_percent": high_congestion_percent,
        "peak_hour": int(peak_row[0]),
        "peak_hour_average_vehicle_count": float(peak_row[1]),
        "mobility_outlook": outlook,
        "basis": "Historical April Tuesday–Thursday traffic patterns",
    }