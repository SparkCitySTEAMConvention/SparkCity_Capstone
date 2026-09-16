"""Read-only Environment dashboard for air quality and weather."""

from __future__ import annotations

import calendar
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from sparkcityx.database import connect_database
from sparkcityx.environment_data import load_monthly_environment


ROOT = Path(__file__).resolve().parents[1]


@st.cache_data(ttl=300, show_spinner="Loading Environment data from S2...")
def get_monthly_environment(year: int) -> pd.DataFrame:
    """Fetch monthly aggregates without changing the shared database."""
    load_dotenv(ROOT / "secrets" / ".env", override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

        return load_monthly_environment(connection, year)


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

    air_tab, weather_tab = st.tabs(["Air Quality", "Weather"])

    with air_tab:
        air = monthly.dropna(subset=["average_pm25"]).copy()

        if air.empty:
            st.info(f"No air quality readings are available for {year}.")
        else:
            st.subheader("Average PM2.5 by month")
            st.line_chart(
                air,
                x="month_name",
                y="average_pm25",
            )
            st.caption(
                f"{int(air['air_readings'].sum()):,} air quality "
                f"readings in {year}. PM2.5 units await team confirmation."
            )

            april = air.loc[air["month"] == 4, "average_pm25"]
            july = air.loc[air["month"] == 7, "average_pm25"]

            if not april.empty and not july.empty:
                left, right = st.columns(2)
                left.metric("April average PM2.5", f"{april.iloc[0]:.2f}")
                right.metric("July average PM2.5", f"{july.iloc[0]:.2f}")

            st.info(
                "The NORMAL/MONITOR indicator will be added when the "
                "air quality team confirms its classification rule."
            )

    with weather_tab:
        weather = monthly.dropna(
            subset=["average_temperature"]
        ).copy()

        if weather.empty:
            st.info(f"No weather readings are available for {year}.")
        else:
            st.subheader("Average weather temperature by month")
            st.bar_chart(
                weather,
                x="month_name",
                y="average_temperature",
            )
            st.caption(
                f"{int(weather['weather_readings'].sum()):,} weather "
                f"readings in {year}. Temperature units await "
                "team confirmation."
            )

            april = weather.loc[
                weather["month"] == 4, "average_temperature"
            ]
            july = weather.loc[
                weather["month"] == 7, "average_temperature"
            ]

            if not april.empty and not july.empty:
                left, right = st.columns(2)
                left.metric(
                    "April average temperature",
                    f"{april.iloc[0]:.2f}",
                )
                right.metric(
                    "July average temperature",
                    f"{july.iloc[0]:.2f}",
                )


    st.subheader("Key Insights")

    april = monthly.loc[monthly["month"] == 4]
    july = monthly.loc[monthly["month"] == 7]

    if april.empty or july.empty:
        st.info(
            "An April–July comparison is unavailable for this year. "
            "Select 2025 for the complete comparison."
        )
    else:
        april = april.iloc[0]
        july = july.iloc[0]

        if pd.notna(april["average_pm25"]) and pd.notna(
            july["average_pm25"]
        ):
            direction = (
                "lower"
                if july["average_pm25"] < april["average_pm25"]
                else "higher"
            )
            st.write(
                f"July average PM2.5 was **{direction}** than April: "
                f"{july['average_pm25']:.2f} versus "
                f"{april['average_pm25']:.2f}."
            )

        if pd.notna(april["average_temperature"]) and pd.notna(
            july["average_temperature"]
        ):
            direction = (
                "lower"
                if july["average_temperature"]
                < april["average_temperature"]
                else "higher"
            )
            st.write(
                f"July average weather temperature was **{direction}** "
                f"than April: {july['average_temperature']:.2f} "
                f"versus {april['average_temperature']:.2f}."
            )


if __name__ == "__main__":
    st.set_page_config(
        page_title="SparkCity Environment",
        page_icon="🌿",
        layout="wide",
    )
    render_environment_page()