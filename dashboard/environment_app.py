"""Read-only Environment dashboard for air quality and weather."""

from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

from sparkcityx.current_air_quality import load_current_air_quality
from components.shared import apply_accessible_palette, light_mode_enabled
from components.weather_scene import render_weather_scene
from sparkcityx.current_weather import load_current_weather_points
from sparkcityx.convention_projection import load_convention_projection
from sparkcityx.database import connect_database
from sparkcityx.lunar_data import NEW_YORK, load_lunar_details
from sparkcityx.environment_data import (
    load_air_monitoring_status,
    load_convention_air_history,
    load_convention_weather_history,
    load_monthly_environment,
)


ROOT = Path(__file__).resolve().parents[1]


def _themed_html(markup: str) -> None:
    """Render Environment HTML through the shared accessibility palette."""
    st.html(apply_accessible_palette(markup))


def _environment_chart_colors() -> dict[str, str]:
    """Keep Altair surfaces and labels synchronized with the selected theme."""
    if light_mode_enabled():
        return {
            "background": "#FFFFFF",
            "label": "#526A82",
            "title": "#172B46",
            "grid": "#D6E0EA",
        }
    return {
        "background": "#182430",
        "label": "#B8C4CF",
        "title": "#F3F6F9",
        "grid": "#34495A",
    }


@st.cache_data(ttl=300, show_spinner="Loading Environment data...")
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


@st.cache_data(ttl=300, show_spinner="Loading convention history...")
def get_convention_history() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch November 3–5 weather and air history using read-only queries."""
    load_dotenv(ROOT / "secrets" / ".env", override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

        weather = load_convention_weather_history(connection)
        air = load_convention_air_history(connection)

    return weather, air


@st.cache_data(ttl=900, show_spinner="Loading current weather...")
def get_current_weather_points() -> list[dict]:
    """Cache current modeled conditions for the New York City Digital City map."""
    return load_current_weather_points()


@st.cache_data(ttl=900, show_spinner="Loading modeled air quality...")
def get_current_air_quality() -> dict:
    """Cache the current modeled US AQI for New York City Digital City."""
    return load_current_air_quality()


@st.cache_data(ttl=3600, show_spinner=False)
def get_lunar_details(local_date: str) -> dict[str, str]:
    """Cache lunar data; the date also refreshes it after midnight."""
    return load_lunar_details()


@st.cache_data(ttl=86400, show_spinner="Preparing convention projection...")
def get_convention_projection() -> list[dict]:
    """Cache historical reanalysis baselines for the 2027 event map."""
    return load_convention_projection()


def projection_marker_color(value: float, layer: str) -> list[int]:
    """Use fixed scales so colors stay comparable across all three days."""
    if layer == "Temperature":
        if value < 50:
            return [59, 130, 246, 180]
        if value < 60:
            return [56, 189, 248, 180]
        if value < 70:
            return [34, 197, 94, 180]
        if value < 80:
            return [250, 204, 21, 180]
        return [239, 111, 38, 180]
    if value < 0.1:
        return [169, 184, 196, 140]
    if value < 1:
        return [147, 197, 253, 180]
    if value < 5:
        return [59, 130, 246, 180]
    if value < 10:
        return [29, 78, 216, 190]
    return [88, 28, 135, 190]


def render_environment_page() -> None:
    """Render Environment inside its own styling boundary."""
    with st.container(key="environment-page"):
        _render_environment_content()


def _render_environment_content() -> None:
    """Render the Environment section for the team dashboard."""
    chart_colors = _environment_chart_colors()
    st.markdown(
        apply_accessible_palette("""
        <style>
        .st-key-environment-page [data-testid="stMetricLabel"],
        .st-key-environment-page [data-testid="stMetricValue"] {
            color: #F3F6F9 !important;
        }
        .st-key-environment-page [data-testid="stMetricLabel"] p,
        .st-key-environment-page [data-testid="stCaptionContainer"] p {
            font-size: 1.125rem !important;
            line-height: 1.45 !important;
        }
        .environment-page-title {
            color: #F3F6F9;
            font-size: 2.5313rem !important;
            font-weight: 700;
            line-height: 1.2;
            margin: 0 0 6px;
        }
        .environment-action-card {
            min-height: 188px;
            padding: 16px 18px;
            border: 1px solid #34495A;
            border-left-width: 5px;
            border-radius: 12px;
            color: #F3F6F9;
        }
        .environment-action-card.weather {
            border-left-color: #38BDF8;
            background: linear-gradient(135deg, #132B3A, #17283A);
        }
        .environment-action-card.air {
            border-left-color: #F59E0B;
            background: linear-gradient(135deg, #332815, #2C271B);
        }
        .environment-action-card .card-label {
            margin: 0 0 10px;
            font-size: 1.125rem !important;
            font-weight: 800;
            letter-spacing: 0.08em;
        }
        .environment-action-card.weather .card-label { color: #7DD3FC; }
        .environment-action-card.air .card-label { color: #FBBF24; }
        .environment-action-card .action-row {
            display: grid;
            grid-template-columns: 84px 1fr;
            gap: 10px;
            padding: 8px 0;
            border-top: 1px solid rgba(184, 196, 207, 0.18);
        }
        .environment-action-card .action-row:first-of-type {
            border-top: 0;
            padding-top: 0;
        }
        .environment-action-card .action-key {
            color: #B8C4CF;
            font-size: 1.125rem !important;
            font-weight: 800;
            letter-spacing: 0.05em;
        }
        .environment-action-card .action-copy {
            color: #F3F6F9;
            font-size: 1.125rem !important;
            line-height: 1.4;
        }
        </style>
        """),
        unsafe_allow_html=True,
    )
    st.markdown('<div class="environment-page-title">Environment</div>', unsafe_allow_html=True)
    st.caption(
        "Current modeled weather and historical environmental observations"
    )

    _themed_html(
        """
        <style>
          .environment-date-banner {
            padding: 20px 24px;
            border: 1px solid #34495A;
            border-left: 6px solid #37966b;
            border-radius: 14px;
            background: #1E332F;
            color: #F3F6F9;
          }
          .environment-date-banner .eyebrow {
            margin: 0 0 6px;
            color: #7FD1A8;
            font-size: 1.125rem !important;
            font-weight: 700;
            letter-spacing: 0.09em;
          }
          .environment-date-banner h2 {
            margin: 0 0 6px;
            color: #F3F6F9;
            font-size: 1.9125rem !important;
            line-height: 1.2;
          }
          .environment-date-banner .context {
            margin: 0;
            color: #B8C4CF;
            font-size: 1.125rem !important;
            line-height: 1.45;
          }
          .environment-date-banner .alternative {
            margin: 10px 0 0;
            padding-top: 10px;
            border-top: 1px solid #c9dfd2;
            color: #405c52;
            font-size: 1.125rem !important;
            line-height: 1.45;
          }
        </style>
        <section class="environment-date-banner"
                 aria-label="Confirmed convention dates">
          <p class="eyebrow">PRIMARY PLANNING WINDOW</p>
          <h2>November 3–5, 2027</h2>
          <p class="context">
            Environment planning outlook based on historical observations.
            This is not a November 2027 forecast.
            Measurement units await team confirmation.
          </p>
          <p class="alternative">
            <strong>Alternate window:</strong> October 19–21, 2027,
            if planners choose to avoid possible Election Day-related
            impacts around November 2.
          </p>
        </section>
        """
    )

    try:
        weather_history, air_history = get_convention_history()
    except Exception:
        st.warning("Convention history could not be loaded.")
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
                            f"November {row.day}",
                            f"{row.average_temperature:.1f}",
                        )

                    st.caption(
                        f"Based on {len(weather_history)} matching days "
                        f"from {weather_history['year'].nunique()} historical years."
                    )
                    _themed_html(
                        """
                        <section class="environment-action-card weather"
                                 aria-label="Weather readiness actions">
                          <p class="card-label">WEATHER READINESS</p>
                          <div class="action-row">
                            <span class="action-key">PLAN</span>
                            <span class="action-copy">Prepare layers for cooler
                            November mornings and evenings.</span>
                          </div>
                          <div class="action-row">
                            <span class="action-key">PREPARE</span>
                            <span class="action-copy">Keep umbrellas, covered
                            routes, and indoor staging available.</span>
                          </div>
                          <div class="action-row">
                            <span class="action-key">CHECK</span>
                            <span class="action-copy">Review the short-range
                            forecast 72 hours before the event and each
                            convention morning.</span>
                          </div>
                        </section>
                        """
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
                            f"November {row.day} PM2.5",
                            f"{row.average_pm25:.2f}",
                        )

                    years = ", ".join(
                        str(year) for year in sorted(air_history["year"].unique())
                    )
                    st.caption(
                        f"Based on {int(air_history['readings'].sum()):,} "
                        f"readings from {years}. No November 3–5, 2026 air "
                        "readings are available; these are not 2027 predictions."
                    )
                    _themed_html(
                        """
                        <section class="environment-action-card air"
                                 aria-label="Air quality readiness actions">
                          <p class="card-label">AIR QUALITY READINESS</p>
                          <div class="action-row">
                            <span class="action-key">CONTEXT</span>
                            <span class="action-copy">Treat the available 2025
                            history as limited planning context.</span>
                          </div>
                          <div class="action-row">
                            <span class="action-key">MONITOR</span>
                            <span class="action-copy">Check current AQI and
                            PM2.5 before opening and throughout each day.</span>
                          </div>
                          <div class="action-row">
                            <span class="action-key">RESPOND</span>
                            <span class="action-copy">Move outdoor activities
                            inside and notify attendees if current readings
                            become elevated.</span>
                          </div>
                        </section>
                        """
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
            "Historical November 3–5 weather readings included precipitation. "
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

    with st.expander("Interactive Weather Map — Internet Required", expanded=False):
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
            "conditions. This map is separate from historical observations and "
            "is not a November 2027 forecast."
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
            "Current model estimates, not local station observations."
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
            "America/New_York. Separate from the historical "
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
        '<p style="color:#F3F6F9;font-weight:600;">Year</p>',
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
            "Environment data could not be loaded. "
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
                    .configure(background=chart_colors["background"])
                    .configure_view(stroke=None)
                    .configure_axis(
                        labelColor=chart_colors["label"],
                        titleColor=chart_colors["title"],
                        gridColor=chart_colors["grid"],
                    )
                )
                st.altair_chart(air_chart, width="stretch", theme=None)
                st.caption(
                    f"{int(air['air_readings'].sum()):,} air quality readings in {year}. "
                    "PM2.5 units await team confirmation."
                )
                october_air = air.loc[air["month"] == 10, "average_pm25"]
                november_air = air.loc[air["month"] == 11, "average_pm25"]
                if not october_air.empty and not november_air.empty:
                    left, right = st.columns(2)
                    left.metric(
                        "October average PM2.5",
                        f"{october_air.iloc[0]:.2f}",
                    )
                    right.metric(
                        "November average PM2.5",
                        f"{november_air.iloc[0]:.2f}",
                    )

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
                    .configure(background=chart_colors["background"])
                    .configure_view(stroke=None)
                    .configure_axis(
                        labelColor=chart_colors["label"],
                        titleColor=chart_colors["title"],
                        gridColor=chart_colors["grid"],
                    )
                )
                st.altair_chart(
                    weather_chart,
                    width="stretch",
                    theme=None,
                )
                st.caption(
                    f"{int(weather['weather_readings'].sum()):,} weather "
                    f"readings in {year}. Temperature units await "
                    "team confirmation."
                )

                october_weather = weather.loc[
                    weather["month"] == 10, "average_temperature"
                ]
                november_weather = weather.loc[
                    weather["month"] == 11, "average_temperature"
                ]

                if not october_weather.empty and not november_weather.empty:
                    left, right = st.columns(2)
                    left.metric(
                        "October average temperature",
                        f"{october_weather.iloc[0]:.2f}",
                    )
                    right.metric(
                        "November average temperature",
                        f"{november_weather.iloc[0]:.2f}",
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
                    "Monitoring counts could not be loaded."
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
                    'border-radius:5px;overflow:hidden;background:#34495A;" '
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
                    "across all historical air quality readings. This is a "
                    "statistical monitoring indicator, not a "
                    "public-health classification."
                )

    with insights_column:
        october = monthly.loc[monthly["month"] == 10]
        november = monthly.loc[monthly["month"] == 11]
        insight_lines = []

        if october.empty or november.empty:
            insight_lines.append(
                "<p>An October–November comparison is unavailable for this "
                "year. Select 2025 for the complete comparison.</p>"
            )
        else:
            october = october.iloc[0]
            november = november.iloc[0]

            if pd.notna(october["average_pm25"]) and pd.notna(
                november["average_pm25"]
            ):
                direction = (
                    "lower"
                    if november["average_pm25"] < october["average_pm25"]
                    else "higher"
                )
                insight_lines.append(
                    f"<p>November average PM2.5 was "
                    f"<strong>{direction}</strong> than October: "
                    f"{november['average_pm25']:.2f} versus "
                    f"{october['average_pm25']:.2f}.</p>"
                )
            else:
                insight_lines.append(
                    "<p>The October–November PM2.5 comparison is "
                    f"unavailable for {year}.</p>"
                )

            if pd.notna(october["average_temperature"]) and pd.notna(
                november["average_temperature"]
            ):
                direction = (
                    "lower"
                    if november["average_temperature"]
                    < october["average_temperature"]
                    else "higher"
                )
                insight_lines.append(
                    "<p>November average weather temperature was "
                    f"<strong>{direction}</strong> than October: "
                    f"{november['average_temperature']:.2f} versus "
                    f"{october['average_temperature']:.2f}.</p>"
                )

        _themed_html(
            """
            <style>
              .environment-insights-card {
                position: relative;
                padding: 20px 24px;
                border: 1px solid #5A4A2C;
                border-left: 6px solid #e88c28;
                border-radius: 14px;
                background: #332E25;
                box-shadow: 0 4px 14px rgb(114 71 16 / 9%);
                color: #F3F6F9;
              }
              .environment-insights-card h3 {
                margin: 0 0 12px;
                color: #F0B573;
                font-size: 1.4625rem !important;
                line-height: 1.25;
              }
              .environment-insights-card p {
                margin: 0 0 10px;
                font-size: 1.125rem !important;
                line-height: 1.5;
              }
              .environment-insights-card p:last-child { margin-bottom: 0; }
            </style>
            <section class="environment-insights-card"
                     aria-label="Key insights">
              <h3>📌 Key Insights</h3>
            """
            + "".join(insight_lines)
            + "</section>"
        )


    st.subheader("Projected weather map · November 3–5, 2027")
    st.caption(
        "Planning projection from 2021–2026 matching dates, using Open-Meteo "
        "historical reanalysis across nine map locations. This is not a "
        "2027 weather forecast."
    )
    map_day_column, map_layer_column = st.columns(2, gap="small")
    with map_day_column:
        projection_day = st.selectbox(
            "Event day",
            [3, 4, 5],
            format_func=lambda day: f"November {day}",
            key="environment_projection_day",
        )
    with map_layer_column:
        projection_layer = st.selectbox(
            "Projected layer",
            ["Temperature", "Precipitation"],
            key="environment_projection_layer",
        )

    try:
        projection = get_convention_projection()
    except Exception:
        st.warning(
            "The projected weather map is temporarily unavailable. "
            "Historical database planning details above are still available."
        )
    else:
        map_data = []
        for point in projection:
            if point["day"] != projection_day:
                continue
            metric = (
                point["temperature_f"]
                if projection_layer == "Temperature"
                else point["precipitation_mm"]
            )
            map_data.append(
                {
                    **point,
                    "marker_color": projection_marker_color(
                        metric, projection_layer
                    ),
                }
            )
        if map_data:
            map_layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position="[lon, lat]",
                get_fill_color="marker_color",
                get_radius=3700,
                pickable=True,
                stroked=True,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=1,
            )
            st.pydeck_chart(
                pdk.Deck(
                    layers=[map_layer],
                    initial_view_state=pdk.ViewState(
                        latitude=40.76,
                        longitude=-73.97,
                        zoom=10.6,
                        pitch=0,
                    ),
                    map_style="dark",
                    tooltip={  # type: ignore[arg-type]
                        "html": (
                            "<b>{location} · November {day}, 2027 baseline</b><br/>"
                            "Mean temperature: {temperature_f} °F "
                            "(past range {temperature_min_f}-{temperature_max_f} °F)"
                            "<br/>Mean daily precipitation: {precipitation_mm} mm "
                            "(past range {precipitation_min_mm}-"
                            "{precipitation_max_mm} mm)"
                        ),
                        "style": {"color": "white"},
                    },
                width="stretch",
                height=300,
                 )
            )
            st.caption(
                "Colors show six-year historical averages for the selected "
                "calendar day. Temperature: blue → green → orange as values "
                "rise. Precipitation: gray → light blue → dark blue/purple as "
                "daily totals rise. Hover for the past range. Nearby circles "
                "may share a source model grid cell (roughly 9 km), so local "
                "detail is limited. Rainfall totals are not the chance of "
                "rain in 2027. [Source: Open-Meteo Historical Weather API]"
                "(https://open-meteo.com/en/docs/historical-weather-api)."
            )



if __name__ == "__main__":
    st.set_page_config(
        page_title="New York Digital City Environment",
        page_icon="🌿",
        layout="wide",
    )
    render_environment_page()
