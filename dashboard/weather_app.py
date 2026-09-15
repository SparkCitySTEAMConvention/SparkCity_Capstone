"""Interactive SparkCity weather operations dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from sparkcityx.weather_dashboard import (
    prepare_weather_dashboard_data,
    summarize_weather_dashboard,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "raw" / "weather_data.parquet"


st.set_page_config(
    page_title="SparkCity Weather Operations",
    page_icon="🌤️",
    layout="wide",
)


@st.cache_data(show_spinner="Loading weather observations...")
def load_weather_data(source: str) -> pd.DataFrame:
    """Load and prepare the local weather Parquet dataset."""
    raw_df = pd.read_parquet(source)
    return prepare_weather_dashboard_data(raw_df)


st.title("🌤️ SparkCity Weather Operations")
st.caption(
    "Interactive monitoring of weather observations, temporal "
    "patterns, and readings requiring investigation."
)

source_path = st.sidebar.text_input(
    "Weather dataset",
    value=str(DEFAULT_SOURCE),
)

try:
    weather_df = load_weather_data(source_path)
except (FileNotFoundError, OSError, ValueError) as error:
    st.error(f"Unable to load weather data: {error}")
    st.stop()

minimum_date = weather_df["reading_date"].min()
maximum_date = weather_df["reading_date"].max()

selected_dates = st.sidebar.date_input(
    "Date range",
    value=(minimum_date, maximum_date),
    min_value=minimum_date,
    max_value=maximum_date,
)

station_options = sorted(
    weather_df["station_id"].dropna().unique().tolist()
)
selected_stations = st.sidebar.multiselect(
    "Stations",
    options=station_options,
    help="Leave empty to include every station.",
)

filtered_df = weather_df.copy()

if len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered_df = filtered_df[
        filtered_df["reading_date"].between(
            start_date,
            end_date,
        )
    ]

if selected_stations:
    filtered_df = filtered_df[
        filtered_df["station_id"].isin(selected_stations)
    ]

if filtered_df.empty:
    st.warning("No weather readings match the selected filters.")
    st.stop()

summary = summarize_weather_dashboard(filtered_df)

metric_columns = st.columns(5)
metric_columns[0].metric(
    "Readings",
    f"{summary['record_count']:,}",
)
metric_columns[1].metric(
    "Stations",
    f"{summary['station_count']:,}",
)
metric_columns[2].metric(
    "Average temperature",
    f"{summary['average_temperature']:.2f}",
)
metric_columns[3].metric(
    "Average humidity",
    f"{summary['average_humidity']:.2f}",
)
metric_columns[4].metric(
    "Maximum wind speed",
    f"{summary['maximum_wind_speed']:.2f}",
)

st.caption(
    f"Selected period: {summary['first_timestamp']} through "
    f"{summary['last_timestamp']}"
)

hourly_df = (
    filtered_df
    .groupby("hour_timestamp", as_index=False)
    .agg(
        average_temperature=("temperature", "mean"),
        average_humidity=("humidity", "mean"),
        average_wind_speed=("wind_speed", "mean"),
        total_precipitation=("precipitation", "sum"),
        average_pressure=("pressure", "mean"),
    )
    .sort_values("hour_timestamp")
)

overview_tab, precipitation_tab, investigation_tab, data_tab = (
    st.tabs(
        [
            "Weather overview",
            "Precipitation",
            "Investigation queue",
            "Filtered data",
        ]
    )
)

with overview_tab:
    st.subheader("Hourly temperature and humidity")

    temperature_column, humidity_column = st.columns(2)

    with temperature_column:
        st.line_chart(
            hourly_df,
            x="hour_timestamp",
            y="average_temperature",
        )

    with humidity_column:
        st.line_chart(
            hourly_df,
            x="hour_timestamp",
            y="average_humidity",
        )

    st.subheader("Wind speed and atmospheric pressure")

    wind_column, pressure_column = st.columns(2)

    with wind_column:
        st.line_chart(
            hourly_df,
            x="hour_timestamp",
            y="average_wind_speed",
        )

    with pressure_column:
        st.line_chart(
            hourly_df,
            x="hour_timestamp",
            y="average_pressure",
        )

with precipitation_tab:
    st.subheader("Hourly precipitation totals")
    st.bar_chart(
        hourly_df,
        x="hour_timestamp",
        y="total_precipitation",
    )

    st.metric(
        "Total precipitation in selection",
        f"{summary['total_precipitation']:.3f}",
    )

with investigation_tab:
    st.subheader("Readings requiring review")
    st.caption(
        "These are dataset-relative statistical observations, "
        "not official emergency thresholds."
    )

    high_temperature = filtered_df["temperature"].quantile(0.99)
    low_temperature = filtered_df["temperature"].quantile(0.01)
    high_wind = filtered_df["wind_speed"].quantile(0.99)
    high_precipitation = filtered_df["precipitation"].quantile(0.99)

    investigation_df = filtered_df[
        (filtered_df["temperature"] >= high_temperature)
        | (filtered_df["temperature"] <= low_temperature)
        | (filtered_df["wind_speed"] >= high_wind)
        | (
            filtered_df["precipitation"]
            >= high_precipitation
        )
    ].copy()

    investigation_df["investigation_reason"] = ""
    investigation_df.loc[
        investigation_df["temperature"] >= high_temperature,
        "investigation_reason",
    ] += "HIGH_TEMPERATURE "
    investigation_df.loc[
        investigation_df["temperature"] <= low_temperature,
        "investigation_reason",
    ] += "LOW_TEMPERATURE "
    investigation_df.loc[
        investigation_df["wind_speed"] >= high_wind,
        "investigation_reason",
    ] += "HIGH_WIND "
    investigation_df.loc[
        investigation_df["precipitation"] >= high_precipitation,
        "investigation_reason",
    ] += "HIGH_PRECIPITATION"

    investigation_df["investigation_reason"] = (
        investigation_df["investigation_reason"].str.strip()
    )

    st.dataframe(
        investigation_df[
            [
                "station_id",
                "timestamp",
                "investigation_reason",
                "temperature",
                "humidity",
                "wind_speed",
                "precipitation",
                "pressure",
            ]
        ].sort_values(
            ["timestamp", "station_id"],
            ascending=[False, True],
        ),
        use_container_width=True,
        hide_index=True,
    )

with data_tab:
    st.subheader("Filtered weather observations")
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )