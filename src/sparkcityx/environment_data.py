"""Read-only data queries for the Environment dashboard."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from psycopg import Connection


def load_monthly_environment(
    connection: Connection,
    year: int,
) -> pd.DataFrame:
    """Return monthly PM2.5 and weather temperature for one year."""
    if not 1900 <= year <= 2100:
        raise ValueError("year must be between 1900 and 2100")

    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXTRACT(MONTH FROM timestamp)::int AS month,
                   AVG(pm25) AS average_pm25,
                   COUNT(*) AS air_readings
            FROM sparkcity.air_quality
            WHERE timestamp >= %s AND timestamp < %s
            GROUP BY 1
            ORDER BY 1
            """,
            (start, end),
        )
        air_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT EXTRACT(MONTH FROM timestamp)::int AS month,
                   AVG(temperature) AS average_temperature,
                   COUNT(*) AS weather_readings
            FROM sparkcity.weather_data
            WHERE timestamp >= %s AND timestamp < %s
            GROUP BY 1
            ORDER BY 1
            """,
            (start, end),
        )
        weather_rows = cursor.fetchall()

    air = pd.DataFrame(
        air_rows,
        columns=["month", "average_pm25", "air_readings"],
    )
    weather = pd.DataFrame(
        weather_rows,
        columns=["month", "average_temperature", "weather_readings"],
    )

    result = air.merge(weather, on="month", how="outer")
    return result.sort_values("month").reset_index(drop=True)


def load_air_monitoring_status(
    connection: Connection,
    year: int,
) -> dict[str, int]:
    """Count readings using the air team's historical 90th-percentile rule."""
    if not 1900 <= year <= 2100:
        raise ValueError("year must be between 1900 and 2100")

    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH thresholds AS (
                SELECT
                    percentile_cont(0.9) WITHIN GROUP
                        (ORDER BY pm25) AS pm25_limit,
                    percentile_cont(0.9) WITHIN GROUP
                        (ORDER BY pm10) AS pm10_limit,
                    percentile_cont(0.9) WITHIN GROUP
                        (ORDER BY no2) AS no2_limit,
                    percentile_cont(0.9) WITHIN GROUP
                        (ORDER BY co) AS co_limit
                FROM sparkcity.air_quality
            )
            SELECT
                COUNT(*)::int AS total,
                COUNT(*) FILTER (
                    WHERE air.pm25 >= thresholds.pm25_limit
                       OR air.pm10 >= thresholds.pm10_limit
                       OR air.no2 >= thresholds.no2_limit
                       OR air.co >= thresholds.co_limit
                )::int AS monitor
            FROM sparkcity.air_quality AS air
            CROSS JOIN thresholds
            WHERE air.timestamp >= %s
              AND air.timestamp < %s
            """,
            (start, end),
        )
        total, monitor = cursor.fetchone()

    return {
        "total": total,
        "normal": total - monitor,
        "monitor": monitor,
    }

def load_convention_weather_history(
    connection: Connection,
) -> pd.DataFrame:
    """Return April 6–8 weather observations from 2025 and 2026."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXTRACT(YEAR FROM timestamp)::int AS year,
                   EXTRACT(DAY FROM timestamp)::int AS day,
                   COUNT(*)::int AS readings,
                   AVG(temperature) AS average_temperature,
                   AVG(wind_speed) AS average_wind_speed,
                   AVG(precipitation) AS average_precipitation,
                   100.0 * AVG((precipitation > 0)::int)
                       AS percent_readings_with_precipitation
            FROM sparkcity.weather_data
            WHERE (timestamp >= DATE '2025-04-06'
                   AND timestamp < DATE '2025-04-09')
               OR (timestamp >= DATE '2026-04-06'
                   AND timestamp < DATE '2026-04-09')
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
        rows = cursor.fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "year",
            "day",
            "readings",
            "average_temperature",
            "average_wind_speed",
            "average_precipitation",
            "percent_readings_with_precipitation",
        ],
    )


def load_convention_weather_history(
    connection: Connection,
) -> pd.DataFrame:
    """Return April 6–8 weather observations from 2025 and 2026."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXTRACT(YEAR FROM timestamp)::int AS year,
                   EXTRACT(DAY FROM timestamp)::int AS day,
                   COUNT(*)::int AS readings,
                   AVG(temperature) AS average_temperature,
                   AVG(wind_speed) AS average_wind_speed,
                   AVG(precipitation) AS average_precipitation,
                   100.0 * AVG((precipitation > 0)::int)
                       AS percent_readings_with_precipitation
            FROM sparkcity.weather_data
            WHERE (timestamp >= DATE '2025-04-06'
                   AND timestamp < DATE '2025-04-09')
               OR (timestamp >= DATE '2026-04-06'
                   AND timestamp < DATE '2026-04-09')
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
        rows = cursor.fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "year",
            "day",
            "readings",
            "average_temperature",
            "average_wind_speed",
            "average_precipitation",
            "percent_readings_with_precipitation",
        ],
    )


def load_convention_air_history(
    connection: Connection,
) -> pd.DataFrame:
    """Return available April 6–8 air quality observations."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT EXTRACT(YEAR FROM timestamp)::int AS year,
                   EXTRACT(DAY FROM timestamp)::int AS day,
                   COUNT(*)::int AS readings,
                   AVG(pm25) AS average_pm25,
                   AVG(pm10) AS average_pm10,
                   AVG(no2) AS average_no2,
                   AVG(co) AS average_co
            FROM sparkcity.air_quality
            WHERE (timestamp >= DATE '2025-04-06'
                   AND timestamp < DATE '2025-04-09')
               OR (timestamp >= DATE '2026-04-06'
                   AND timestamp < DATE '2026-04-09')
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        )
        rows = cursor.fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "year",
            "day",
            "readings",
            "average_pm25",
            "average_pm10",
            "average_no2",
            "average_co",
        ],
    )
