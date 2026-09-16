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