"""Read-only Environment dashboard for air quality and weather."""

from __future__ import annotations

import calendar
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

from sparkcityx.current_weather import load_current_weather_points
from sparkcityx.database import connect_database
from sparkcityx.environment_data import (
    load_air_monitoring_status,
    load_convention_air_history,
    load_convention_weather_history,
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


@st.cache_data(ttl=300, show_spinner="Loading convention history from S2...")
def get_convention_history() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch April 6–8 weather and air history without writing to S2."""
    load_dotenv(ROOT / "secrets" / ".env", override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

        weather = load_convention_weather_history(connection)
        air = load_convention_air_history(connection)

    return weather, air


@st.cache_data(ttl=900, show_spinner="Loading current weather...")
def get_current_weather_points() -> list[dict]:
    """Cache current modeled conditions for the SparkCity map."""
    return load_current_weather_points()


def render_environment_page() -> None:
    """Render the Environment section for the team dashboard."""
    st.markdown(
        """
        <style>
        .stApp [data-testid="stMetricLabel"],
        .stApp [data-testid="stMetricValue"] {
            color: #172b46 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Environment")
    st.caption("Air quality and weather observations from SparkCity S2")

    st.markdown(
        '<p style="color:#172B46;font-weight:600;">Year</p>',
        unsafe_allow_html=True,
    )
    year = st.selectbox(
        "Year",
        [2025, 2026],
        index=0,
        label_visibility="collapsed",
    )

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
                air_chart = (
                    air_chart
                    .configure(background="#FFFFFF")
                    .configure_view(stroke=None)
                    .configure_axis(
                        labelColor="#172B46",
                        titleColor="#172B46",
                        gridColor="#DCE5EF",
                    )
                )
                st.altair_chart(air_chart, use_container_width=True, theme=None)
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
                weather_chart = (
                    weather_chart
                    .configure(background="#FFFFFF")
                    .configure_view(stroke=None)
                    .configure_axis(
                        labelColor="#172B46",
                        titleColor="#172B46",
                        gridColor="#DCE5EF",
                    )
                )
                st.altair_chart(
                    weather_chart,
                    use_container_width=True,
                    theme=None,
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
                left.metric("NORMAL", f"{status['normal']:,}")
                right.metric("MONITOR", f"{status['monitor']:,}")

                st.caption(
                    f"NORMAL {normal_percent:.1f}% · "
                    f"MONITOR {monitor_percent:.1f}% of {year} readings"
                )

                st.markdown(
                    '<div style="display:flex;height:20px;'
                    'border-radius:5px;overflow:hidden;background:#E5E7EB;" '
                    f'role="img" aria-label="{normal_percent:.1f}% normal, '
                    f'{monitor_percent:.1f}% monitor">'
                    f'<div style="width:{normal_percent:.1f}%;'
                    'background:#26A269;"></div>'
                    f'<div style="width:{monitor_percent:.1f}%;'
                    'background:#F59E0B;"></div>'
                    '</div>',
                    unsafe_allow_html=True,
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


    st.subheader("Current modeled weather map")
    st.caption(
        "Current model estimates across five SparkCity locations. "
        "These are not live S2 station readings or an April 2027 forecast."
    )

    try:
        map_points = get_current_weather_points()
    except Exception:
        st.warning("Current weather is temporarily unavailable.")
    else:
        with st.container(border=True):
            location_colors = {
                "Center": [220, 38, 38, 220],
                "North": [147, 51, 234, 220],
                "South": [22, 163, 74, 220],
                "West": [234, 88, 12, 220],
                "East": [37, 99, 235, 220],
            }
            map_points = [
                {**point, "marker_color": location_colors[point["location"]]}
                for point in map_points
            ]
            center = map_points[0]
            condition_column, temperature_column, rain_column = st.columns(3)
            condition_column.metric(
                "Current conditions",
                f"{center['icon']} {center['description']}",
            )
            temperature_column.metric(
                "Center temperature",
                f"{center['temperature_f']:.1f} °F",
            )
            rain_column.metric(
                "Recent precipitation",
                f"{center['precipitation_mm']:.1f} mm",
            )

            map_layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_points,
                get_position="[lon, lat]",
                get_fill_color="marker_color",
                get_radius=1800,
                pickable=True,
                stroked=True,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=2,
            )
            map_view = pdk.ViewState(
                latitude=40.76,
                longitude=-73.97,
                zoom=10.5,
                pitch=0,
            )
            st.pydeck_chart(
                pdk.Deck(
                    layers=[map_layer],
                    initial_view_state=map_view,
                    map_style="light",
                    tooltip={
                        "html": (
                            "<b>{icon} {location}</b><br/>"
                            "{description}<br/>"
                            "{temperature_f} °F · "
                            "Precipitation: {precipitation_mm} mm"
                        ),
                        "style": {"color": "white"},
                    },
                ),
                use_container_width=True,
            )
            st.markdown(
                "**Map locations:** 🔴 Center · 🟣 North · "
                "🟢 South · 🟠 West · 🔵 East"
            )
            st.caption(
                f"Reported {map_points[0]['reported_at']} "
                "America/New_York. Data: Open-Meteo current weather model. "
                "Hover over a marker for conditions."
            )

    st.subheader("April 6–8, 2027 convention planning outlook")
    st.caption(
        "Historical planning context, not a forecast for April 2027. "
        "Measurement units await team confirmation."
    )

    try:
        weather_history, air_history = get_convention_history()
    except Exception:
        st.warning("Convention history could not be loaded from S2.")
    else:
        weather_plan_column, air_plan_column = st.columns(2, gap="medium")

        with weather_plan_column:
            with st.container(border=True):
                st.subheader("Weather planning")
                if weather_history.empty:
                    st.info("No matching historical weather readings are available.")
                else:
                    weather_history = weather_history.copy()
                    weather_history["average_temperature"] = pd.to_numeric(
                        weather_history["average_temperature"]
                    )
                    daily_weather = (
                        weather_history.groupby("day", as_index=False)
                        ["average_temperature"].mean()
                    )

                    day_columns = st.columns(3)
                    for column, row in zip(
                        day_columns, daily_weather.itertuples(), strict=False
                    ):
                        column.metric(
                            f"April {row.day}",
                            f"{row.average_temperature:.1f}",
                        )

                    st.caption(
                        f"Based on {len(weather_history)} matching days "
                        f"from {weather_history['year'].nunique()} historical years."
                    )
                    st.markdown(
                        "- **Bring a layer:** Historical daily averages vary "
                        "across the three dates.\n"
                        "- **Keep umbrellas and covered routes available:** "
                        "Precipitation appeared in the historical readings.\n"
                        "- **Offer shade and water:** Prepare comfortable "
                        "outdoor waiting areas if conditions are sunny."
                    )
                    st.caption(
                        "Historical precipitation readings do not give the "
                        "probability of rain in 2027. Check a current forecast "
                        "closer to the event."
                    )


        with air_plan_column:
            with st.container(border=True):
                st.subheader("Air quality planning")
                if air_history.empty:
                    st.info("No matching historical air readings are available.")
                else:
                    air_history = air_history.copy()
                    air_history["average_pm25"] = pd.to_numeric(
                        air_history["average_pm25"]
                    )

                    day_columns = st.columns(3)
                    for column, row in zip(
                        day_columns, air_history.itertuples(), strict=False
                    ):
                        column.metric(
                            f"April {row.day} PM2.5",
                            f"{row.average_pm25:.2f}",
                        )

                    years = ", ".join(
                        str(year) for year in sorted(air_history["year"].unique())
                    )
                    st.caption(
                        f"Based on {int(air_history['readings'].sum()):,} "
                        f"readings from {years}. No April 6–8, 2026 air "
                        "readings are available; these are not 2027 predictions."
                    )
                    st.markdown(
                        "- **Check current air readings** shortly before "
                        "and during each convention day.\n"
                        "- **Keep an indoor option** for outdoor activities "
                        "if current conditions warrant a change.\n"
                        "- **Share updates with attendees** if the outdoor "
                        "plan changes."
                    )
                    st.caption(
                        "The dashboard's NORMAL/MONITOR indicator is based "
                        "on historical data percentiles, not a public "
                        "health classification."
                    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="SparkCity Environment",
        page_icon="🌿",
        layout="wide",
    )
    render_environment_page()