"""Read-only Environment dashboard for air quality and weather."""

from __future__ import annotations

import calendar
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from sparkcityx.database import connect_database
from sparkcityx.environment_data import (
    load_air_monitoring_status,
    load_monthly_environment,
)


ROOT = Path(__file__).resolve().parents[1]


@st.cache_data(ttl=300, show_spinner="Loading Environment data from S2...")
def get_monthly_environment(year: int) -> pd.DataFrame:
    """Fetch monthly aggregates without changing the shared database."""
    load_dotenv(ROOT / "secrets" / ".env", override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

        return load_monthly_environment(connection, year)


@st.cache_data(ttl=300, show_spinner="Calculating air monitoring status...")
def get_air_monitoring_status(year: int) -> dict[str, int]:
    """Read the air team's monitoring counts for the selected year."""
    load_dotenv(ROOT / "secrets" / ".env", override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

        return load_air_monitoring_status(connection, year)


def render_environment_page() -> None:
    """Render the Environment section for the team dashboard."""
    st.title("Environment")
    st.caption("Air quality and weather observations from SparkCity S2")

    year = st.selectbox("Year", [2025, 2026], index=0)

    try:
        monthly = get_monthly_environment(year)
    except Exception:
        st.error(
            "Environment data could not be loaded from S2. "
            "Check the database connection and try again."
        )
        return

    if monthly.empty:
        st.info(f"No Environment readings are available for {year}.")
        return

    monthly["month_name"] = monthly["month"].map(
        lambda month: calendar.month_abbr[int(month)]
    )
    month_order = list(calendar.month_abbr)[1:]

    # Top row: air quality and weather charts
    air_column, weather_column = st.columns(2, gap="medium")

    with air_column:
        with st.container(border=True):
            air = monthly.dropna(subset=["average_pm25"]).copy()

            if air.empty:
                st.info(f"No air quality readings are available for {year}.")
            else:
                st.subheader("Average PM2.5 by month")
                air_chart = alt.Chart(air).encode(
                    x=alt.X("month_name:N", sort=month_order, title=None),
                    y=alt.Y("average_pm25:Q", title="Average PM2.5"),
                    tooltip=[
                        alt.Tooltip("month_name:N", title="Month"),
                        alt.Tooltip("average_pm25:Q", title="Average PM2.5", format=".2f"),
                    ],
                )
                if len(air) == 1:
                    air_chart = air_chart.mark_bar(color="#2563EB", size=32)
                else:
                    air_chart = air_chart.mark_line(color="#2563EB", point=True)
                st.altair_chart(air_chart, use_container_width=True)
                st.caption(
                    f"{int(air['air_readings'].sum()):,} air quality readings in {year}. "
                    "PM2.5 units await team confirmation."
                )
                april_air = air.loc[air["month"] == 4, "average_pm25"]
                july_air = air.loc[air["month"] == 7, "average_pm25"]
                if not april_air.empty and not july_air.empty:
                    left, right = st.columns(2)
                    left.metric("April average PM2.5", f"{april_air.iloc[0]:.2f}")
                    right.metric("July average PM2.5", f"{july_air.iloc[0]:.2f}")

    with weather_column:
        with st.container(border=True):
            weather = monthly.dropna(
                subset=["average_temperature"]
            ).copy()

            if weather.empty:
                st.info(f"No weather readings are available for {year}.")
            else:
                st.subheader("Average weather temperature by month")

                weather_chart = (
                    alt.Chart(weather)
                    .mark_bar(color="#F59E0B", size=32)
                    .encode(
                        x=alt.X(
                            "month_name:N",
                            sort=month_order,
                            title=None,
                        ),
                        y=alt.Y(
                            "average_temperature:Q",
                            title="Average temperature",
                        ),
                        tooltip=[
                            alt.Tooltip("month_name:N", title="Month"),
                            alt.Tooltip(
                                "average_temperature:Q",
                                title="Average temperature",
                                format=".2f",
                            ),
                        ],
                    )
                )
                st.altair_chart(
                    weather_chart,
                    use_container_width=True,
                )
                st.caption(
                    f"{int(weather['weather_readings'].sum()):,} weather "
                    f"readings in {year}. Temperature units await "
                    "team confirmation."
                )

                april_weather = weather.loc[
                    weather["month"] == 4, "average_temperature"
                ]
                july_weather = weather.loc[
                    weather["month"] == 7, "average_temperature"
                ]

                if not april_weather.empty and not july_weather.empty:
                    left, right = st.columns(2)
                    left.metric(
                        "April average temperature",
                        f"{april_weather.iloc[0]:.2f}",
                    )
                    right.metric(
                        "July average temperature",
                        f"{july_weather.iloc[0]:.2f}",
                    )

    # Bottom row: monitoring indicator and data-driven insights
    monitoring_column, insights_column = st.columns(
        2,
        gap="medium",
    )

    with monitoring_column:
        with st.container(border=True):
            st.subheader("Air Quality Monitoring Indicator")

            try:
                status = get_air_monitoring_status(year)
            except Exception:
                st.warning(
                    "Monitoring counts could not be loaded from S2."
                )
            else:
                total = status["total"]
                normal_percent = (
                    status["normal"] / total * 100
                    if total
                    else 0
                )
                monitor_percent = (
                    status["monitor"] / total * 100
                    if total
                    else 0
                )

                left, right = st.columns(2)


                indicator_data = pd.DataFrame(
                    [
                        {
                            "group": "Readings",
                            "status": "NORMAL",
                            "count": status["normal"],
                        },
                        {
                            "group": "Readings",
                            "status": "MONITOR",
                            "count": status["monitor"],
                        },
                    ]
                )

                indicator_chart = (
                    alt.Chart(indicator_data)
                    .mark_bar()
                    .encode(
                        x=alt.X(
                            "count:Q",
                            stack="normalize",
                            axis=None,
                        ),
                        y=alt.Y("group:N", axis=None),
                        color=alt.Color(
                            "status:N",
                            scale=alt.Scale(
                                domain=["NORMAL", "MONITOR"],
                                range=["#26A269", "#F59E0B"],
                            ),
                            legend=None,
                        ),
                        tooltip=[
                            alt.Tooltip("status:N", title="Status"),
                            alt.Tooltip("count:Q", title="Readings"),
                        ],
                    )
                    .properties(height=36)
                )
                st.altair_chart(
                    indicator_chart,
                    use_container_width=True,
                )


                st.caption(
                    "MONITOR means at least one pollutant met or "
                    "exceeded its historical 90th-percentile threshold "
                    "across all S2 air quality readings. This is a "
                    "statistical monitoring indicator, not a "
                    "public-health classification."
                )

    with insights_column:
        with st.container(border=True):
            st.subheader("Key Insights")

            april = monthly.loc[monthly["month"] == 4]
            july = monthly.loc[monthly["month"] == 7]

            if april.empty or july.empty:
                st.info(
                    "An April–July comparison is unavailable for "
                    "this year. Select 2025 for the complete "
                    "comparison."
                )
            else:
                april = april.iloc[0]
                july = july.iloc[0]

                if pd.notna(april["average_pm25"]) and pd.notna(
                    july["average_pm25"]
                ):
                    direction = (
                        "lower"
                        if july["average_pm25"]
                        < april["average_pm25"]
                        else "higher"
                    )
                    st.write(
                        f"July average PM2.5 was **{direction}** "
                        f"than April: {july['average_pm25']:.2f} "
                        f"versus {april['average_pm25']:.2f}."
                    )
                else:
                    st.caption(
                        "The April–July PM2.5 comparison is "
                        f"unavailable for {year}."
                    )

                if pd.notna(
                    april["average_temperature"]
                ) and pd.notna(
                    july["average_temperature"]
                ):
                    direction = (
                        "lower"
                        if july["average_temperature"]
                        < april["average_temperature"]
                        else "higher"
                    )
                    st.write(
                        "July average weather temperature was "
                        f"**{direction}** than April: "
                        f"{july['average_temperature']:.2f} versus "
                        f"{april['average_temperature']:.2f}."
                    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="SparkCity Environment",
        page_icon="🌿",
        layout="wide",
    )
    render_environment_page()