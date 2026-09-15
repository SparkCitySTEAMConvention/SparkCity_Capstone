"""Reusable data preparation for the SparkCity weather dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd


_REQUIRED_COLUMNS = {
    "station_id",
    "timestamp",
    "temperature",
    "humidity",
    "wind_speed",
    "precipitation",
    "pressure",
}


def prepare_weather_dashboard_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Validate and prepare weather rows for dashboard rendering."""
    missing_columns = sorted(_REQUIRED_COLUMNS - set(df.columns))

    if missing_columns:
        raise ValueError(
            "Weather dashboard data is missing columns: "
            + ", ".join(missing_columns)
        )

    result = df.copy()
    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        errors="raise",
    )
    result["reading_date"] = result["timestamp"].dt.date
    result["hour_timestamp"] = result["timestamp"].dt.floor("h")

    return result.sort_values(
        ["timestamp", "station_id"]
    ).reset_index(drop=True)


def summarize_weather_dashboard(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Calculate headline weather dashboard metrics."""
    return {
        "record_count": int(len(df)),
        "station_count": int(df["station_id"].nunique()),
        "average_temperature": float(df["temperature"].mean()),
        "average_humidity": float(df["humidity"].mean()),
        "maximum_wind_speed": float(df["wind_speed"].max()),
        "total_precipitation": float(
            df["precipitation"].sum()
        ),
        "average_pressure": float(df["pressure"].mean()),
        "first_timestamp": df["timestamp"].min(),
        "last_timestamp": df["timestamp"].max(),
    }