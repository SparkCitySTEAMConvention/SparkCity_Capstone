"""Mobility & Traffic dashboard page."""

from typing import Any, cast

import altair as alt
import pandas as pd
import streamlit as st

from sparkcityx.mobility import (
    get_congestion_breakdown,
    get_convention_mobility_outlook,
    get_hourly_traffic,
    get_mobility_summary,
    get_road_type_summary,
    get_sensor_summary,
    has_month_data,
)


def render_mobility_traffic():
    """Render the Mobility & Traffic dashboard page."""

    # Keep pydeck local to this page.
    # Importing it globally was affecting styling on the Overview page.
    import pydeck as pdk

    # ---------------------------------------------------------
    # Page Header
    # ---------------------------------------------------------

    st.title("Mobility & Traffic")

    st.write(
        "Explore traffic volume, average speeds, congestion patterns, "
        "road conditions, and transportation considerations for "
        "SparkCity convention planning."
    )

    # ---------------------------------------------------------
    # Convention Mobility Forecast
    # ---------------------------------------------------------

    # Scenario assumptions:
    # - 15,000 anticipated attendees across the three-day convention
    # - attendance distributed evenly across the three convention days
    # - 2 attendees per convention-generated vehicle
    #
    # This estimates added vehicle demand without pretending that every
    # convention vehicle passes every traffic sensor.
    convention_outlook = get_convention_mobility_outlook()

    if convention_outlook:
        anticipated_attendees = 15_000
        convention_days = 3
        attendees_per_vehicle = 2.0

        estimated_attendees_per_day = anticipated_attendees / convention_days
        estimated_added_vehicles_per_day = (
            estimated_attendees_per_day / attendees_per_vehicle
        )

        convention_peak_hour = convention_outlook["peak_hour"]
        convention_peak_display = (
            f"{convention_peak_hour % 12 or 12} "
            f"{'AM' if convention_peak_hour < 12 else 'PM'}"
        )

        st.markdown(
            f"""
<div class="convention-forecast-panel">
<div class="convention-forecast-eyebrow">CONVENTION MOBILITY FORECAST</div>
<div class="convention-forecast-title">April 6–8, 2027</div>
<div class="convention-forecast-subtitle">Scenario forecast for 15,000 anticipated attendees</div>
<div class="convention-forecast-metrics">
<div class="convention-forecast-metric">
<span class="convention-forecast-value">{estimated_attendees_per_day:,.0f}</span>
<span class="convention-forecast-label">Estimated Attendees / Day</span>
</div>
<div class="convention-forecast-metric">
<span class="convention-forecast-value">+{estimated_added_vehicles_per_day:,.0f}</span>
<span class="convention-forecast-label">Estimated Added Vehicles / Day</span>
</div>
<div class="convention-forecast-metric">
<span class="convention-forecast-value">{convention_peak_display}</span>
<span class="convention-forecast-label">Historical Peak Travel Period</span>
</div>
<div class="convention-forecast-metric">
<span class="convention-forecast-value">{convention_outlook['high_congestion_percent']:.1f}%</span>
<span class="convention-forecast-label">Historical High Congestion</span>
</div>
</div>
<div class="convention-forecast-takeaway">
<strong>Forecast:</strong> Convention travel is expected to add approximately
{estimated_added_vehicles_per_day:,.0f} vehicle trips per day to normal city traffic,
with the greatest mobility risk around the historical {convention_peak_display} peak.
Staggered arrivals/departures, shuttle service, rideshare coordination, and transit
options can reduce pressure during peak periods.
</div>
<div class="convention-forecast-note">
<strong>Scenario assumptions:</strong> 15,000 total attendees distributed evenly across
three days and 2 attendees per convention-generated vehicle. Historical April
Tuesday–Thursday sensor patterns provide the traffic baseline. This is a planning
scenario, not a measured 2027 traffic observation.
</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="mobility-analysis-heading">Historical Traffic Analysis</div>',
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # Month Selection
    # ---------------------------------------------------------

    month_options = {
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

    month_col, _ = st.columns([1, 3])

    with month_col:
        selected_month = st.selectbox(
            "Select Month",
            options=list(month_options.keys()),
            index=3,
        )

    selected_month_number = month_options[selected_month]

    # Determine whether the selected month contains actual sensor data.
    has_observed_data = has_month_data(selected_month_number)

    # If no observations exist for the selected month, use the complete
    # observed dataset as a planning baseline rather than returning
    # an empty dashboard.
    query_month = (
        selected_month_number
        if has_observed_data
        else None
    )

    # ---------------------------------------------------------
    # Retrieve Dashboard Data
    # ---------------------------------------------------------

    summary = get_mobility_summary(query_month)
    hourly_data = get_hourly_traffic(query_month)
    congestion_data = get_congestion_breakdown(query_month)
    road_type_data = get_road_type_summary(query_month)

    # The hotspot map represents the complete sensor network.
    sensor_data = get_sensor_summary()

    if not summary:
        st.warning("Traffic data is currently unavailable.")
        return

    # ---------------------------------------------------------
    # Estimated Data Notice
    # ---------------------------------------------------------

    if not has_observed_data:
        st.info(
            f"Estimated Traffic Pattern — No sensor observations are "
            f"available for {selected_month}. Values shown use the "
            "available 2025 traffic patterns as a planning baseline "
            "and are not measured observations for this month."
        )

    # ---------------------------------------------------------
    # Summary KPI Cards
    # ---------------------------------------------------------

    peak_hour = summary["peak_hour"]

    peak_hour_display = (
        f"{peak_hour % 12 or 12} "
        f"{'AM' if peak_hour < 12 else 'PM'}"
    )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.markdown(
            f"""
<div class="mobility-kpi-card">
    <div class="mobility-kpi-label">Average Traffic Volume</div>
    <div class="mobility-kpi-value">
        {summary['average_vehicle_count']:.1f}
    </div>
    <div class="mobility-kpi-detail">vehicles</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with kpi2:
        st.markdown(
            f"""
<div class="mobility-kpi-card">
    <div class="mobility-kpi-label">Average Speed</div>
    <div class="mobility-kpi-value">
        {summary['average_speed_kmh']:.2f}
    </div>
    <div class="mobility-kpi-detail">km/h</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with kpi3:
        st.markdown(
            f"""
<div class="mobility-kpi-card">
    <div class="mobility-kpi-label">High Congestion</div>
    <div class="mobility-kpi-value">
        {summary['high_congestion_percent']:.2f}%
    </div>
    <div class="mobility-kpi-detail">of observations</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with kpi4:
        st.markdown(
            f"""
<div class="mobility-kpi-card">
    <div class="mobility-kpi-label">Peak Traffic Hour</div>
    <div class="mobility-kpi-value">
        {peak_hour_display}
    </div>
    <div class="mobility-kpi-detail">
        {summary['peak_hour_average_vehicle_count']:.1f} avg. vehicles
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------------
    # Prepare Hourly Data
    # ---------------------------------------------------------

    hourly_df = pd.DataFrame(hourly_data)

    if not hourly_df.empty:
        hourly_df["time"] = hourly_df["hour"].apply(
            lambda hour: (
                f"{hour % 12 or 12} "
                f"{'AM' if hour < 12 else 'PM'}"
            )
        )

    # ---------------------------------------------------------
    # Traffic Volume & Average Speed
    # ---------------------------------------------------------

    top_left, top_right = st.columns(2)

    with top_left:
        st.subheader("Traffic Volume by Hour")
        st.write(
            "Average traffic volume throughout the day."
        )

        if not hourly_df.empty:
            traffic_volume_chart = (
                alt.Chart(hourly_df)
                .mark_area(
                    line=True,
                    point=True,
                    opacity=0.35,
                    color="#A63D40",
                )
                .encode(
                    x=alt.X(
                        "hour:Q",
                        title="Time of Day",
                        axis=alt.Axis(
                            values=[
                                0,
                                3,
                                6,
                                9,
                                12,
                                15,
                                18,
                                21,
                            ],
                            labelExpr=(
                                "datum.value == 0 ? '12 AM' : "
                                "datum.value < 12 ? "
                                "datum.value + ' AM' : "
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
                        alt.Tooltip(
                            "time:N",
                            title="Time",
                        ),
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
                width=700,
            )

    with top_right:
        st.subheader("Average Speed by Hour")
        st.write(
            "Average vehicle speed throughout the day."
        )

        if not hourly_df.empty:
            average_speed_chart = (
                alt.Chart(hourly_df)
                .mark_line(
                    point=True,
                    strokeWidth=3,
                    color="#F2994A",
                )
                .encode(
                    x=alt.X(
                        "hour:Q",
                        title="Time of Day",
                        axis=alt.Axis(
                            values=[
                                0,
                                3,
                                6,
                                9,
                                12,
                                15,
                                18,
                                21,
                            ],
                            labelExpr=(
                                "datum.value == 0 ? '12 AM' : "
                                "datum.value < 12 ? "
                                "datum.value + ' AM' : "
                                "datum.value == 12 ? '12 PM' : "
                                "(datum.value - 12) + ' PM'"
                            ),
                        ),
                    ),
                    y=alt.Y(
                        "average_speed_kmh:Q",
                        title="Average Speed (km/h)",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "time:N",
                            title="Time",
                        ),
                        alt.Tooltip(
                            "average_speed_kmh:Q",
                            title="Average Speed",
                            format=".2f",
                        ),
                    ],
                )
            )

            st.altair_chart(
                average_speed_chart,
                width=700,
            )

    # ---------------------------------------------------------
    # Congestion & Road Type
    # ---------------------------------------------------------

    congestion_df = pd.DataFrame(congestion_data)
    road_type_df = pd.DataFrame(road_type_data)

    if not road_type_df.empty:
        road_type_df["road_type_display"] = (
            road_type_df["road_type"]
            .str.replace("_", " ")
            .str.title()
        )

    bottom_left, bottom_right = st.columns(2)

    with bottom_left:
        st.subheader("Congestion Breakdown")
        st.write(
            "Distribution of traffic observations by congestion level."
        )

        if not congestion_df.empty:
            congestion_chart = (
                alt.Chart(congestion_df)
                .mark_arc(
                    innerRadius=55,
                    outerRadius=105,
                )
                .encode(
                    theta=alt.Theta(
                        "percentage:Q",
                        title="Percentage",
                    ),
                    color=alt.Color(
                        "congestion_level:N",
                        title="Congestion Level",
                        scale=alt.Scale(
                            domain=[
                                "high",
                                "medium",
                                "low",
                            ],
                            range=[
                                "#E05252",
                                "#F2C94C",
                                "#58B96B",
                            ],
                        ),
                        sort=[
                            "high",
                            "medium",
                            "low",
                        ],
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "congestion_level:N",
                            title="Congestion",
                        ),
                        alt.Tooltip(
                            "record_count:Q",
                            title="Observations",
                        ),
                        alt.Tooltip(
                            "percentage:Q",
                            title="Percentage",
                            format=".2f",
                        ),
                    ],
                )
                .properties(
                    height=260,
                    padding={
                        "left": 20,
                        "right": 20,
                        "top": 15,
                        "bottom": 15,
                    },
                )
            )

            st.altair_chart(
                congestion_chart,
                width=700,
            )

    with bottom_right:
        st.subheader("Average Speed by Road Type")
        st.write(
            "Average vehicle speed across SparkCity road categories."
        )

        if not road_type_df.empty:
            road_speed_chart = (
                alt.Chart(road_type_df)
                .mark_bar(
                    cornerRadiusEnd=5,
                    size=24,
                )
                .encode(
                    y=alt.Y(
                        "road_type_display:N",
                        sort="-x",
                        title=None,
                        axis=alt.Axis(
                            labelFontSize=12,
                            labelPadding=8,
                        ),
                    ),
                    x=alt.X(
                        "average_speed_kmh:Q",
                        title="Average Speed (km/h)",
                        scale=alt.Scale(
                            domain=[0, 42],
                            nice=False,
                        ),
                        axis=alt.Axis(
                            grid=True,
                            gridOpacity=0.15,
                            tickCount=6,
                            labelPadding=8,
                            titlePadding=14,
                        ),
                    ),
                    color=alt.Color(
                        "road_type_display:N",
                        scale=alt.Scale(
                            domain=[
                                "Highway",
                                "Arterial",
                                "Residential",
                                "Downtown",
                                "School Zone",
                            ],
                            range=[
                                "#4DA3D9",
                                "#F2A23A",
                                "#58B96B",
                                "#E05252",
                                "#8E63CE",
                            ],
                        ),
                        legend=None,
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "road_type_display:N",
                            title="Road Type",
                        ),
                        alt.Tooltip(
                            "average_speed_kmh:Q",
                            title="Average Speed",
                            format=".2f",
                        ),
                    ],
                )
                .properties(
                    height=260,
                    padding={
                        "left": 20,
                        "right": 30,
                        "top": 15,
                        "bottom": 15,
                    },
                )
            )

            st.altair_chart(
                road_speed_chart,
                width=700,
            )

    # ---------------------------------------------------------
    # Convention Transportation Risk Areas
    # ---------------------------------------------------------

    st.divider()

    st.subheader("Convention Transportation Risk Areas")

    st.write(
        "Identifies historically congested sensor locations that may require "
        "additional transportation planning during the April 6–8, 2027 "
        "convention. These locations already experience recurring congestion "
        "and could face additional pressure from convention-generated traffic."
    )

    sensor_df = pd.DataFrame(sensor_data)

    if not sensor_df.empty:
        risk_df = sensor_df.copy()

        # Rank existing mobility vulnerabilities using three historical
        # indicators: recurring high congestion, heavier traffic volume,
        # and lower average speed. Percentile ranks keep unlike units
        # comparable without inventing a traffic-engineering standard.
        risk_df["congestion_risk"] = risk_df[
            "high_congestion_percent"
        ].rank(pct=True)

        risk_df["volume_risk"] = risk_df[
            "average_vehicle_count"
        ].rank(pct=True)

        risk_df["speed_risk"] = (
            -risk_df["average_speed_kmh"]
        ).rank(pct=True)

        risk_df["convention_risk_score"] = (
            risk_df["congestion_risk"] * 0.50
            + risk_df["volume_risk"] * 0.30
            + risk_df["speed_risk"] * 0.20
        ) * 100

        # Display the highest-risk historical locations rather than every
        # sensor on the network so the map remains useful for planning.
        risk_df = (
            risk_df
            .sort_values("convention_risk_score", ascending=False)
            .head(25)
            .copy()
        )

        risk_df["risk_rank"] = range(1, len(risk_df) + 1)
        risk_df["convention_risk_score"] = (
            risk_df["convention_risk_score"].round(1)
        )

        view_state = pdk.ViewState(
            latitude=sensor_df["latitude"].mean(),
            longitude=sensor_df["longitude"].mean(),
            zoom=10,
            pitch=0,
        )

        risk_layer = pdk.Layer(
            "ScatterplotLayer",
            data=risk_df,
            get_position="[longitude, latitude]",
            get_radius=150,
            get_fill_color="[224, 82, 82, 190]",
            pickable=True,
        )

        deck = pdk.Deck(
            layers=[risk_layer],
            initial_view_state=view_state,
            tooltip=cast(
                Any,
                {
                    "html": (
                        "<b>Convention Risk Rank:</b> #{risk_rank}<br/>"
                        "<b>Sensor:</b> {sensor_id}<br/>"
                        "<b>Risk Score:</b> {convention_risk_score}<br/>"
                        "<b>Average Traffic:</b> {average_vehicle_count}<br/>"
                        "<b>Average Speed:</b> {average_speed_kmh} km/h<br/>"
                        "<b>High Congestion:</b> {high_congestion_percent}%"
                    )
                },
            ),
        )

        st.pydeck_chart(deck)

        st.caption(
            "The map shows the 25 highest-risk sensor locations based on a "
            "planning score that weights historical high congestion (50%), "
            "traffic volume (30%), and lower average speed (20%). The score "
            "ranks existing transportation vulnerabilities; it is not an "
            "official traffic standard and does not claim that the convention "
            "caused the historical conditions."
        )

    # ---------------------------------------------------------
    # Key Insights & Recommendations
    # ---------------------------------------------------------

    st.divider()

    _, insights_col, recommendations_col, _ = st.columns([0.5, 2, 2, 0.5])

    peak_hour_label = (
        f"{peak_hour % 12 or 12} "
        f"{'AM' if peak_hour < 12 else 'PM'}"
    )

    with insights_col:
        st.markdown(
            f"""
<div class="mobility-insight-card">
<div class="mobility-card-title">💡 Key Insights</div>
<p><strong>Highest traffic volume:</strong> {peak_hour_label}</p>
<p><strong>Average traffic volume:</strong> {summary['average_vehicle_count']:.2f} vehicles</p>
<p><strong>Average speed:</strong> {summary['average_speed_kmh']:.2f} km/h</p>
<p><strong>High congestion:</strong> {summary['high_congestion_percent']:.2f}% of traffic observations</p>
</div>
""",
            unsafe_allow_html=True,
        )

    with recommendations_col:
        st.markdown(
            """
<div class="mobility-recommendation-card">
<div class="mobility-card-title">📌 Recommendations</div>
<p>• Schedule major arrivals and departures outside peak traffic periods</p>
<p>• Account for reduced travel speeds during morning and evening rush periods</p>
<p>• Use high-congestion sensor locations when planning transportation routes</p>
<p>• Monitor traffic conditions during the event and adjust transportation plans as needed</p>
</div>
""",
            unsafe_allow_html=True,
        )