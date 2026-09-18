"""Read-only Environment dashboard for air quality and weather."""

from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from sparkcityx.current_air_quality import load_current_air_quality
from components.weather_scene import render_weather_scene
from sparkcityx.current_weather import load_current_weather_points
from sparkcityx.database import connect_database
from sparkcityx.lunar_data import NEW_YORK, load_lunar_details
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


@st.cache_data(ttl=900, show_spinner="Loading modeled air quality...")
def get_current_air_quality() -> dict:
    """Cache the current modeled US AQI for SparkCity Center."""
    return load_current_air_quality()


@st.cache_data(ttl=3600, show_spinner=False)
def get_lunar_details(local_date: str) -> dict[str, str]:
    """Cache lunar data; the date also refreshes it after midnight."""
    return load_lunar_details()


def render_environment_page() -> None:
    """Render Environment inside its own styling boundary."""
    with st.container(key="environment-page"):
        _render_environment_content()


def _render_environment_content() -> None:
    """Render the Environment section for the team dashboard."""
    st.markdown(
        """
        <style>
        .st-key-environment-page [data-testid="stMetricLabel"],
        .st-key-environment-page [data-testid="stMetricValue"] {
            color: #172b46 !important;
        }
        .st-key-environment-page [data-testid="stMetricLabel"] p,
        .st-key-environment-page [data-testid="stCaptionContainer"] p {
            font-size: 0.95rem !important;
            line-height: 1.45 !important;
        }
        .st-key-environment-insights [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid #f2d4a5 !important;
            border-left: 6px solid #e88c28 !important;
            border-radius: 14px !important;
            background: #fff9ef !important;
            box-shadow: 0 4px 14px rgb(114 71 16 / 9%);
        }
        .st-key-environment-insights h3 {
            color: #8a4a0b;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Environment")
    st.caption(
        "Current modeled weather and historical observations from SparkCity S2"
    )

    st.html(
        """
        <style>
          .environment-date-banner {
            padding: 20px 24px;
            border: 1px solid #c9dfd2;
            border-left: 6px solid #37966b;
            border-radius: 14px;
            background: #f0faf5;
            color: #172b46;
          }
          .environment-date-banner .eyebrow {
            margin: 0 0 6px;
            color: #287452;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.09em;
          }
          .environment-date-banner h2 {
            margin: 0 0 6px;
            color: #172b46;
            font-size: 1.7rem;
            line-height: 1.2;
          }
          .environment-date-banner .context {
            margin: 0;
            color: #405c52;
            font-size: 0.95rem;
            line-height: 1.45;
          }
        </style>
        <section class="environment-date-banner"
                 aria-label="Confirmed convention dates">
          <p class="eyebrow">CONFIRMED CONVENTION DATES</p>
          <h2>April 6–8, 2027</h2>
          <p class="context">
            Environment planning outlook based on historical observations.
            This is not an April 2027 forecast.
            Measurement units await team confirmation.
          </p>
        </section>
        """
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

    why_column, action_column = st.columns(2, gap="medium")

    with why_column:
        st.markdown("**Why it matters**")
        st.write(
            "Historical April 6–8 weather readings included precipitation. "
            "Matching air quality readings are available for 2025 only, "
            "so the air data gives limited planning context."
        )

    with action_column:
        st.markdown("**Planning action**")
        st.write(
            "Prepare covered routes and an indoor option. Check the current "
            "forecast and air readings closer to the convention before "
            "finalizing outdoor activities."
        )

    current_points = []
    try:
        current_points = get_current_weather_points()
    except Exception:
        st.info("Current modeled weather is temporarily unavailable.")
    else:
        center_now = current_points[0]
        st.subheader("Current modeled weather · Center")
        render_weather_scene(center_now["description"])
        readings = st.columns(7, gap="small")
        readings[0].metric(
            "Conditions",
            f"{center_now['temperature_f']:.1f} °F",
        )
        readings[1].metric(
            "Humidity",
            f"{center_now['humidity_percent']:.0f}%"
            if center_now["humidity_percent"] is not None else "N/A",
        )
        readings[2].metric(
            "Wind",
            f"{center_now['wind_speed_kmh']:.1f} km/h"
            if center_now["wind_speed_kmh"] is not None else "N/A",
        )
        readings[3].metric(
            "UV index",
            f"{center_now['uv_index']:.1f}"
            if center_now["uv_index"] is not None else "N/A",
        )
        readings[4].metric(
            "Sunset",
            (
                datetime.fromisoformat(center_now["sunset"])
                .strftime("%I:%M %p")
                .lstrip("0")
                if center_now["sunset"] else "N/A"
            ),
        )
        readings[5].metric(
            "Visibility",
            f"{center_now['visibility_m'] / 1000:.1f} km"
            if center_now["visibility_m"] is not None else "N/A",
        )
        readings[6].metric(
            "Pressure",
            f"{center_now['pressure_hpa']:.0f} hPa"
            if center_now["pressure_hpa"] is not None else "N/A",
        )
        st.caption(
            f"{center_now['description']} · Model time "
            f"{center_now['reported_at']} America/New_York. "
            "Current model estimates, not S2 station readings."
        )

    try:
        current_air = get_current_air_quality()
    except Exception:
        st.info("Current modeled air quality is temporarily unavailable.")
    else:
        aqi = current_air["us_aqi"]
        position = min(max(aqi, 0), 500) / 500 * 100
        st.markdown(
            f"**🌿 Current modeled US AQI · Center: {aqi} "
            f"({current_air['category']})**"
        )
        st.markdown(
            '<div style="position:relative;padding-top:9px;">'
            '<div style="height:14px;border-radius:7px;'
            'background:linear-gradient(to right,'
            '#22C55E 0% 10%,#EAB308 10% 20%,'
            '#F97316 20% 30%,#EF4444 30% 40%,'
            '#A855F7 40% 60%,#7F1D1D 60% 100%);"></div>'
            f'<div style="position:absolute;left:{position:.1f}%;top:3px;'
            'width:4px;height:26px;background:#172B46;'
            'border:1px solid white;border-radius:2px;"></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Open-Meteo air-quality model · {current_air['reported_at']} "
            "America/New_York. Separate from the historical S2 "
            "NORMAL/MONITOR indicator below."
        )

    with st.expander("Moon details"):
        try:
            lunar = get_lunar_details(
                datetime.now(NEW_YORK).date().isoformat()
            )
        except Exception:
            st.info("Moon details are temporarily unavailable.")
        else:
            phase_icons = {
                "New Moon": "🌑",
                "Waxing Crescent": "🌒",
                "First Quarter": "🌓",
                "Waxing Gibbous": "🌔",
                "Full Moon": "🌕",
                "Waning Gibbous": "🌖",
                "Last Quarter": "🌗",
                "Waning Crescent": "🌘",
            }
            moonrise = (
                current_points[0].get("moonrise")
                if current_points else None
            )
            moonrise_label = (
                datetime.fromisoformat(moonrise)
                .strftime("%I:%M %p")
                .lstrip("0")
                if moonrise else "N/A"
            )
            moon_columns = st.columns(4, gap="small")
            moon_columns[0].metric(
                "Phase",
                f"{phase_icons.get(lunar['phase'], '🌙')} {lunar['phase']}",
            )
            moon_columns[1].metric(
                "Illuminated", lunar["illumination"]
            )
            moon_columns[2].metric("Moonrise", moonrise_label)
            moon_columns[3].metric(
                "Next full moon", lunar["next_full_moon"]
            )
            st.caption(
                "Phase, noon illumination, and next full moon: "
                "U.S. Naval Observatory. Moonrise: Open-Meteo model. "
                f"Next full moon at {lunar['next_full_moon_time']} "
                "New York time."
            )

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

    # Headline metrics use reading-weighted averages of available months.
    air_observed = monthly.dropna(subset=["average_pm25"]).copy()
    weather_observed = monthly.dropna(
        subset=["average_temperature"]
    ).copy()

    air_count = int(air_observed["air_readings"].sum())
    weather_count = int(weather_observed["weather_readings"].sum())

    if air_count:
        air_average = (
            pd.to_numeric(air_observed["average_pm25"])
            * air_observed["air_readings"]
        ).sum() / air_count
    else:
        air_average = None

    if weather_count:
        weather_average = (
            pd.to_numeric(weather_observed["average_temperature"])
            * weather_observed["weather_readings"]
        ).sum() / weather_count
    else:
        weather_average = None

    st.subheader(f"{year} at a glance")
    metric_columns = st.columns(4, gap="small")
    metric_columns[0].metric(
        "Average PM2.5",
        f"{air_average:.2f}" if air_average is not None else "N/A",
    )
    metric_columns[1].metric(
        "Average temperature",
        f"{weather_average:.1f}" if weather_average is not None else "N/A",
    )
    metric_columns[2].metric("Air readings", f"{air_count:,}")
    metric_columns[3].metric("Weather readings", f"{weather_count:,}")
    st.caption(
        f"Summary of available {year} readings. "
        "Measurement units await team confirmation."
    )

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
                    air_chart = air_chart.mark_bar(color="#2563EB", size=20)
                else:
                    air_chart = air_chart.mark_line(color="#2563EB", point=True)
                air_chart = (
                    air_chart
                    .properties(height=190)
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
                    .mark_bar(color="#F59E0B", size=20)
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
                    .properties(height=190)
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
        with st.container(border=True, key="environment-insights"):
            st.subheader("📌 Key Insights")

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


    st.subheader("Interactive weather map")
    map_layers = {
        "🌡️ Temperature forecast": "temp",
        "🌧️ Rain radar": "radar",
        "💨 Wind forecast": "wind",
        "☁️ Clouds": "clouds",
    }
    selected_layer = st.selectbox(
        "Map layer",
        list(map_layers),
        key="environment_map_layer",
    )
    map_params = urlencode(
        {
            "lat": 40.76,
            "lon": -73.97,
            "zoom": 9,
            "level": "surface",
            "overlay": map_layers[selected_layer],
        }
    )
    st.iframe(
        f"https://embed.windy.com/embed2.html?{map_params}",
        height=420,
    )
    st.caption(
        "Interactive map and weather layers: Windy.com. "
        "Temperature and wind are forecasts; rain radar shows recent "
        "conditions. This map is separate from S2 historical data and "
        "is not an April 2027 forecast."
    )



if __name__ == "__main__":
    st.set_page_config(
        page_title="SparkCity Environment",
        page_icon="🌿",
        layout="wide",
    )
    render_environment_page()