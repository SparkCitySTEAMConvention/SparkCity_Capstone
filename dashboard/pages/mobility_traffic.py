"""Mobility & Traffic dashboard page."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
import pydeck as pdk

from sparkcityx.mobility import (
    get_congestion_breakdown,
    get_hourly_traffic,
    get_mobility_summary,
    get_road_type_summary,
    get_sensor_summary, 
)

st.set_page_config(
    page_title="Mobility & Traffic | SparkCity",
    page_icon="🚦",
    layout="wide",
)

# ---------------------------------------------------------
# Page Header
# ---------------------------------------------------------
header_left, header_right = st.columns([3, 1])

with header_left:
    st.title("Mobility & Traffic")

    st.write(
        "Explore traffic patterns, congestion levels, and mobility conditions "
        "across SparkCity."
    )

with header_right:
    selected_month = st.selectbox(
        "Select a Month",
        [
            "All Available Data",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",  
        ],
    )
month_numbers = {
"January": 1,
"February": 2,
"March": 3,
"April": 4,
"May": 5,
"June": 6,
"July": 7,
"August": 8,
"September": 9,
"October": 10,
"November": 11,
"December": 12,
}

selected_month_number = month_numbers.get(selected_month)

# ---------------------------------------------------------
# Mobility Summary
# ---------------------------------------------------------

summary = get_mobility_summary(selected_month_number)

has_month_data = bool(summary)

if not has_month_data:
    st.info(
        f"No traffic data is available for {selected_month}. "
        "Select another month to view monthly traffic metrics."
    )  
    st.stop()
    

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Average Traffic Volume",
        value=f"{summary['average_vehicle_count']:.1f}",
    )

with col2:
    st.metric(
        label="Average Speed",
        value=f"{summary['average_speed_kmh']:.2f} km/h",
    )

with col3:
    st.metric(
        label="High Congestion",
        value=f"{summary['high_congestion_percent']:.2f}%",
    )

with col4:
    peak_hour = summary["peak_hour"]

    peak_hour_display = (
        f"{peak_hour % 12 or 12} "
        f"{'AM' if peak_hour < 12 else 'PM'}"
    )

    st.metric(
        label="Peak Traffic Hour",
        value=peak_hour_display,
        help=(
            "Average traffic volume during this hour: "
            f"{summary['peak_hour_average_vehicle_count']:.1f} vehicles"
        ),
    )

# ---------------------------------------------------------
# Hourly Traffic Patterns
# ---------------------------------------------------------

# traffic patterns by hour
st.divider()
hourly_data = get_hourly_traffic(selected_month_number)
hourly_df = pd.DataFrame(hourly_data)
hourly_df["time"] = hourly_df["hour"].apply(
    lambda hour: f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"
)
top_left, top_right = st.columns(2)
with top_left:
    st.subheader("Traffic Volume by Hour")
    st.write("Average traffic volume throughout the day.")
    

    traffic_volume_chart = (
        alt.Chart(hourly_df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "hour:Q",
                title="Time of Day",
                axis=alt.Axis(
                    values=[0, 3, 6, 9, 12, 15, 18, 21],
                    labelExpr=(
                        "datum.value == 0 ? '12 AM' : "
                        "datum.value < 12 ? datum.value + ' AM' : "
                        "datum.value == 12 ? '12 PM' : "
                        "(datum.value - 12) + ' PM'"
                    ),
                ),
            ),
            y=alt.Y(
                "average_vehicle_count:Q",
                title="Average Traffic Volume",
            ),
            tooltip=[
                alt.Tooltip("time:N", title="Time"),
                alt.Tooltip(
                    "average_vehicle_count:Q",
                    title="Average Traffic Volume",
                    format=".1f",
                ),
            ],
        )
    )

    st.altair_chart(
        traffic_volume_chart,
        width="stretch",
    )

# average speed by hour

with top_right:
    st.subheader("Average Speed by Hour")
    st.write("Average vehicle speed throughout the day.")
    st.line_chart(
        hourly_df,
        x="hour",
        y="average_speed_kmh",
        x_label="Hour of Day",
        y_label="Average Speed (km/h)",
    )

bottom_left, bottom_right = st.columns(2)
# ---------------------------------------------------------
# Congestion Breakdown
# ---------------------------------------------------------

congestion_data = get_congestion_breakdown(selected_month_number)
congestion_df = pd.DataFrame(congestion_data)

with bottom_left:
    st.subheader("Congestion Breakdown")

    st.write(
        "Distribution of traffic observations by congestion level."
    )

    congestion_chart = (
        alt.Chart(congestion_df)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta("percentage:Q"),
            color=alt.Color(
                "congestion_level:N",
                title="Congestion Level",
            ),
            tooltip=[
                alt.Tooltip(
                    "congestion_level:N",
                    title="Congestion Level",
                ),
                alt.Tooltip(
                    "percentage:Q",
                    title="Percentage",
                    format=".1f",
                ),
                alt.Tooltip(
                    "record_count:Q",
                    title="Observations",
                    format=",",
                ),
            ],
        )
    )

    st.altair_chart(
        congestion_chart,
        width="stretch",
    )

# ---------------------------------------------------------
# Average Speed by Road Type
# ---------------------------------------------------------

road_type_data = get_road_type_summary(selected_month_number)
road_type_df = pd.DataFrame(road_type_data)

with bottom_right:
    st.subheader("Average Speed by Road Type")

    st.write(
        "Comparison of average vehicle speeds across different road types."
    )

    st.bar_chart(
        road_type_df,
        x="road_type",
        y="average_speed_kmh",
        x_label="Road Type",
        y_label="Average Speed (km/h)",
    )

# ---------------------------------------------------------
# Traffic Hotspots
# ---------------------------------------------------------

st.divider()
st.subheader("Traffic Hotspots")
st.caption(
    "Hotspots are based on all available traffic data to highlight recurring "
    "high-congestion locations. The month filter does not apply to this map."
)
st.write(
    "Explore traffic sensor locations and identify areas with "
    "higher levels of congestion."
)

sensor_data = get_sensor_summary()
sensor_df = pd.DataFrame(sensor_data)
high_congestion_sensors = sensor_df[
    sensor_df["high_congestion_percent"] >= 75
].copy()

hotspot_layer = pdk.Layer(
    "ScatterplotLayer",
    data=high_congestion_sensors,
    get_position=["longitude", "latitude"],
    get_radius=80,
    get_fill_color=[220, 60, 50, 180],
    pickable=True,
    auto_highlight=True,
)

map_view = pdk.ViewState(
    latitude=sensor_df["latitude"].mean(),
    longitude=sensor_df["longitude"].mean(),
    zoom=11,
    pitch=0,
)


hotspot_map = pdk.Deck(
    layers=[hotspot_layer],
    initial_view_state=map_view,
)

st.pydeck_chart(
    hotspot_map,
    width="stretch",
)

# ---------------------------------------------------------
# Key Insights & Recommendations
# ---------------------------------------------------------

st.divider()

insights_col, recommendations_col = st.columns(2)

peak_hour = summary["peak_hour"]
peak_hour_label = (
    f"{peak_hour % 12 or 12} "
    f"{'AM' if peak_hour < 12 else 'PM'}"
)

with insights_col:
    st.subheader("Key Insights")

    st.markdown(
        f"""
        - **Highest traffic volume:** {peak_hour_label}
        - **Average traffic volume:** {summary['average_vehicle_count']:.2f} vehicles
        - **Average speed:** {summary['average_speed_kmh']:.2f} km/h
        - **High congestion:** {summary['high_congestion_percent']:.2f}% of traffic observations
        """
    )

with recommendations_col:
    st.subheader("Recommendations")

    st.markdown(
        """
        - Consider scheduling major arrivals and departures outside peak traffic periods
        - Account for reduced travel speeds during morning and evening rush periods
        - Use high-congestion sensor locations when planning transportation routes
        - Monitor traffic conditions during the event and adjust transportation plans as needed
        """
    )