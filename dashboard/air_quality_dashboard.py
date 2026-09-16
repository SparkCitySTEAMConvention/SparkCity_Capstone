from pathlib import Path

import pandas as pd
import streamlit as st


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="SparkCity Air Quality Dashboard",
    page_icon="🏙️",
    layout="wide",
)


# ---------------------------------------------------------
# Locate project and load Air Quality data
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

AIR_QUALITY_PATH = (
    PROJECT_ROOT
    / "data"
    / "features"
    / "air_quality_features.parquet"
)


@st.cache_data
def load_air_quality_data():
    df = pd.read_parquet(AIR_QUALITY_PATH)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["hour"] = df["timestamp"].dt.hour

    return df


df = load_air_quality_data()


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("🏙️ SPARKCITY")
st.header("Air Quality Dashboard")
st.caption("Environmental Conditions & Trends")

min_date = df["timestamp"].min().date()
max_date = df["timestamp"].max().date()

st.caption(
    f"Data period: {min_date:%b %d, %Y} – "
    f"{max_date:%b %d, %Y}"
)


# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------

st.subheader("Dashboard Filters")

filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    selected_dates = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

with filter_col2:
    pollutant = st.selectbox(
        "Pollutant",
        ["All Pollutants", "PM2.5", "PM10", "NO2", "CO"],
    )

with filter_col3:
    sensor_options = ["All Sensors"] + sorted(
        df["sensor_id"].dropna().unique().tolist()
    )

    selected_sensor = st.selectbox(
        "Sensor",
        sensor_options,
    )


# ---------------------------------------------------------
# Apply filters
# ---------------------------------------------------------

filtered_df = df.copy()

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates

    filtered_df = filtered_df[
        (filtered_df["date"] >= start_date)
        & (filtered_df["date"] <= end_date)
    ]

if selected_sensor != "All Sensors":
    filtered_df = filtered_df[
        filtered_df["sensor_id"] == selected_sensor
    ]


# ---------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------

st.divider()

metric1, metric2, metric3, metric4, metric5, metric6 = st.columns(6)

metric1.metric(
    "Avg PM2.5",
    f"{filtered_df['pm25'].mean():.2f}",
)

metric2.metric(
    "Avg PM10",
    f"{filtered_df['pm10'].mean():.2f}",
)

metric3.metric(
    "Avg NO2",
    f"{filtered_df['no2'].mean():.2f}",
)

metric4.metric(
    "Avg CO",
    f"{filtered_df['co'].mean():.2f}",
)

metric5.metric(
    "Observations",
    f"{len(filtered_df):,}",
)

metric6.metric(
    "Sensors",
    f"{filtered_df['sensor_id'].nunique():,}",
)


# ---------------------------------------------------------
# Daily PM2.5 / PM10 trends
# ---------------------------------------------------------

st.divider()

left_chart, right_chart = st.columns([2, 1])

with left_chart:

    st.subheader("Daily PM2.5 and PM10 Trends")

    daily = (
        filtered_df
        .groupby("date", as_index=False)
        .agg(
            pm25=("pm25", "mean"),
            pm10=("pm10", "mean"),
        )
    )

    daily_chart = (
        daily
        .set_index("date")[["pm25", "pm10"]]
    )

    st.line_chart(daily_chart)


# ---------------------------------------------------------
# Monitoring status
# ---------------------------------------------------------

with right_chart:

    st.subheader("Air Quality Monitoring Status")

    pm25_threshold = df["pm25"].quantile(0.90)
    pm10_threshold = df["pm10"].quantile(0.90)
    no2_threshold = df["no2"].quantile(0.90)
    co_threshold = df["co"].quantile(0.90)

    monitor_mask = (
        (filtered_df["pm25"] >= pm25_threshold)
        | (filtered_df["pm10"] >= pm10_threshold)
        | (filtered_df["no2"] >= no2_threshold)
        | (filtered_df["co"] >= co_threshold)
    )

    monitor_count = int(monitor_mask.sum())
    normal_count = int(len(filtered_df) - monitor_count)

    total = len(filtered_df)

    if total:
        normal_pct = normal_count / total * 100
        monitor_pct = monitor_count / total * 100
    else:
        normal_pct = 0
        monitor_pct = 0

    st.metric(
        "NORMAL",
        f"{normal_count:,}",
        f"{normal_pct:.1f}% of observations",
    )

    st.metric(
        "MONITOR",
        f"{monitor_count:,}",
        f"{monitor_pct:.1f}% of observations",
    )

    st.caption(
        "MONITOR indicates that at least one pollutant "
        "met or exceeded its historical 90th-percentile "
        "threshold. This is a statistical monitoring "
        "indicator, not an EPA or public-health classification."
    )


# ---------------------------------------------------------
# Monthly and hourly trends
# ---------------------------------------------------------

st.divider()

monthly_col, hourly_col = st.columns(2)


with monthly_col:

    st.subheader("Monthly Air Quality Trends")

    monthly = (
        filtered_df
        .groupby("month", as_index=False)
        .agg(
            pm25=("pm25", "mean"),
            pm10=("pm10", "mean"),
            no2=("no2", "mean"),
            co=("co", "mean"),
        )
    )

    monthly_chart = (
        monthly
        .set_index("month")[
            ["pm25", "pm10", "no2", "co"]
        ]
    )

    st.line_chart(monthly_chart)


with hourly_col:

    st.subheader("Hourly Pollutant Patterns")

    hourly = (
        filtered_df
        .groupby("hour", as_index=False)
        .agg(
            pm25=("pm25", "mean"),
            pm10=("pm10", "mean"),
            no2=("no2", "mean"),
            co=("co", "mean"),
        )
    )

    hourly_chart = (
        hourly
        .set_index("hour")[
            ["pm25", "pm10", "no2", "co"]
        ]
    )

    st.line_chart(hourly_chart)


# ---------------------------------------------------------
# Data coverage
# ---------------------------------------------------------

st.divider()

coverage_col, takeaway_col = st.columns([1, 2])

with coverage_col:

    st.subheader("Data Coverage")

    st.metric(
        "Total Observations",
        f"{len(filtered_df):,}",
    )

    st.metric(
        "Total Sensors",
        f"{filtered_df['sensor_id'].nunique():,}",
    )

    if not filtered_df.empty:
        st.write(
            "**Selected Period:** "
            f"{filtered_df['timestamp'].min().date()} "
            "to "
            f"{filtered_df['timestamp'].max().date()}"
        )


# ---------------------------------------------------------
# Key takeaways
# ---------------------------------------------------------

with takeaway_col:

    st.subheader("Key Takeaways")

    st.markdown(
        """
        - Air Quality conditions are relatively stable across
          the available monthly data.
        - Monitoring indicators identify observations that are
          elevated relative to the historical SparkCity dataset.
        - Daily and hourly views allow planners to examine
          environmental patterns at different time scales.
        - Observation and sensor counts provide context for
          interpreting each selected period.
        - Air Quality should be considered alongside traffic,
          weather, energy, occupancy, fiscal, and city-zone
          information for convention planning.
        """
    )


# ---------------------------------------------------------
# Purpose
# ---------------------------------------------------------

st.divider()

st.subheader("Purpose")

st.write(
    "Support data-driven city planning by providing clear, "
    "consistent Air Quality trends and monitoring information "
    "for integration with the broader SparkCity dashboard."
)