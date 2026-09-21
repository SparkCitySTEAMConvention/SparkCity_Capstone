"""Mobility & Traffic dashboard page."""

from typing import Any, cast

import altair as alt
import pandas as pd
import streamlit as st

from components.shared import load_css
from sparkcityx.mobility import (
    get_congestion_breakdown as _get_congestion_breakdown,
    get_convention_mobility_outlook,
    get_fourier_traffic_patterns as _get_fourier_traffic_patterns,
    get_mobility_summary as _get_mobility_summary,
    get_sensor_summary as _get_sensor_summary,
    has_month_data as _has_month_data,
)
from components.convention_config import (
    EVENT_DATE_LABEL,
    EVENT_ATTENDEES,
    EVENT_START_DATE,
    EVENT_END_DATE,
    EVENT_MONTH_NAME,
    EVENT_DAYS_LABEL,
    EVENT_DURATION_DAYS,
)


# Thin cached wrappers around sparkcityx.mobility's query functions (2026-09-18).
# The underlying module stays free of any Streamlit import; these wrappers just
# reuse the previous result within the TTL instead of re-querying the shared
# database on every navigation to this page. Same names, signatures, and
# return values as the functions they wrap, so every call site below is
# unchanged.
@st.cache_data(ttl=3600)
def has_month_data(month: int) -> bool:
    return _has_month_data(month)


@st.cache_data(ttl=3600)
def get_mobility_summary(month: int | None = None) -> dict[str, Any]:
    return _get_mobility_summary(month)


@st.cache_data(ttl=3600)
def get_congestion_breakdown(month: int | None = None) -> list[dict[str, Any]]:
    return _get_congestion_breakdown(month)


@st.cache_data(ttl=3600)
def get_fourier_traffic_patterns() -> list[dict[str, Any]]:
    return _get_fourier_traffic_patterns()


@st.cache_data(ttl=3600)
def get_sensor_summary(month: int | None = None) -> list[dict[str, Any]]:
    return _get_sensor_summary(month)


def render_mobility_traffic():
    """Render the Mobility & Traffic dashboard page."""

    # Keep pydeck local to this page.
    # Importing it globally was affecting styling on the Overview page.
    import pydeck as pdk

    # ---------------------------------------------------------
    # Page Header
    # ---------------------------------------------------------

    load_css(section="mobility")

    st.markdown('<div class="mobility-page-title">Mobility &amp; Traffic</div>', unsafe_allow_html=True)

    st.markdown(
        '<p class="mobility-page-description">Explore traffic volume, average speeds, congestion patterns, '
        "road conditions, and transportation considerations for New York Digital City convention planning.</p>",
        unsafe_allow_html=True,
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

<div class="convention-forecast-title">{EVENT_DATE_LABEL}</div>

<div class="convention-forecast-subtitle">
Scenario forecast for {EVENT_ATTENDEES:,} anticipated attendees
</div>

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
<strong>Scenario assumptions:</strong> {EVENT_ATTENDEES:,} total attendees distributed evenly across
{EVENT_DURATION_DAYS} days and 2 attendees per convention-generated vehicle. Historical {EVENT_MONTH_NAME}
{EVENT_DAYS_LABEL} sensor patterns provide the traffic baseline. This is a planning
scenario, not a measured {EVENT_START_DATE.year} traffic observation.
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
            index=10,
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
    congestion_data = get_congestion_breakdown(query_month)
    fourier_data = get_fourier_traffic_patterns()

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
    # Recurring Traffic Patterns — Fourier Analysis
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Recurring Traffic Patterns — Full-Year 2025 Fourier Analysis")
    st.write(
        "Fourier analysis of the full 2025 traffic dataset identifies repeating "
        "traffic cycles throughout the year. These recurring patterns help "
        "convention planners anticipate predictable transportation demand when "
        "scheduling arrivals, departures, shuttles, and other transportation services."
    )

    fourier_df = pd.DataFrame(fourier_data)

    if not fourier_df.empty:
        cycle_order = ["12-hour", "8-hour", "24-hour"]
        fourier_df["cycle"] = pd.Categorical(
            fourier_df["cycle"],
            categories=cycle_order,
            ordered=True,
        )
        fourier_df = fourier_df.sort_values("cycle")

        fourier_chart = (
            alt.Chart(fourier_df)
            .mark_bar(
                cornerRadiusEnd=6,
                size=32,
                color="#9B0404",
            )
            .encode(
                y=alt.Y(
                    "cycle:N",
                    sort=cycle_order,
                    title="Recurring Cycle",
                    axis=alt.Axis(
                        labelFontSize=18,
                        titleFontSize=18,
                        labelPadding=12,
                        titlePadding=18,
                    ),
                ),
                x=alt.X(
                    "relative_strength:Q",
                    title="Pattern Strength (relative)",
                    scale=alt.Scale(domain=[0, 105]),
                    axis=alt.Axis(
                        labelFontSize=18,
                        titleFontSize=18,
                        labelPadding=8,
                        titlePadding=16,
                    ),
                ),
                tooltip=[
                    alt.Tooltip("cycle:N", title="Recurring Cycle"),
                    alt.Tooltip(
                        "period_hours:Q",
                        title="Cycle Length (hours)",
                        format=".1f",
                    ),
                    alt.Tooltip(
                        "relative_strength:Q",
                        title="Pattern Strength",
                        format=".1f",
                    ),
                ],
            )
            .properties(
                height=230,
                padding={
                    "left": 30,
                    "right": 25,
                    "top": 20,
                    "bottom": 25,
                },
            )
        )

        fourier_left, fourier_right = st.columns([1.35, 1])

        with fourier_left:
            st.altair_chart(fourier_chart, width="stretch")
            st.caption(
                "Higher values indicate stronger recurring patterns "
                "in historical traffic data."
            )

        strongest_cycle = fourier_df.sort_values(
            "relative_strength",
            ascending=False,
        ).iloc[0]

        with fourier_right:
            st.markdown(
                f"""
<div class="mobility-fourier-card">
<div class="mobility-card-title">What This Tells Planners</div>
<p>
The <strong>{strongest_cycle['cycle']} cycle</strong> is the strongest
recurring traffic pattern identified across the full 2025 traffic dataset.
</p>
<p>
Strong 8-hour and 24-hour cycles were also detected, showing that traffic
demand follows recurring within-day and daily rhythms rather than varying randomly.
</p>
<p>
For convention planning, these recurring patterns can help guide arrival,
departure, shuttle, rideshare, and transportation schedules around predictable
changes in traffic demand.
</p>
<p class="mobility-fourier-note">
Relative Fourier strength compares the displayed cycles with one another.
It is not a percentage of vehicles or a congestion probability.
</p>
</div>
""",
                unsafe_allow_html=True,
            )

    # ---------------------------------------------------------
    # Congestion Breakdown
    # ---------------------------------------------------------

    congestion_df = pd.DataFrame(congestion_data)

    st.subheader("Congestion Breakdown")
    st.write(
        "Historical distribution of traffic observations by congestion level."
    )

    if not congestion_df.empty:
        congestion_order = ["high", "medium", "low"]

        congestion_chart = (
            alt.Chart(congestion_df)
            .mark_bar(
                cornerRadiusEnd=6,
                size=32,
            )
            .encode(
                y=alt.Y(
                    "congestion_level:N",
                    sort=congestion_order,
                    title="Congestion Level",
                    axis=alt.Axis(
                        labelFontSize=18,
                        titleFontSize=18,
                        labelPadding=12,
                        titlePadding=18,
                        labelExpr="upper(datum.label)",
                    ),
                ),
                x=alt.X(
                    "percentage:Q",
                    title="Percentage of Traffic Observations",
                    scale=alt.Scale(domain=[0, 45]),
                    axis=alt.Axis(
                        labelFontSize=18,
                        titleFontSize=18,
                        labelPadding=8,
                        titlePadding=16,
                        format=".0f",
                    ),
                ),
                color=alt.Color(
                    "congestion_level:N",
                    legend=None,
                    scale=alt.Scale(
                        domain=["high", "medium", "low"],
                        range=["#710505", "#F2C94C", "#5E889D"],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("congestion_level:N", title="Congestion"),
                    alt.Tooltip(
                        "record_count:Q",
                        title="Observations",
                        format=",",
                    ),
                    alt.Tooltip(
                        "percentage:Q",
                        title="Percentage",
                        format=".1f",
                    ),
                ],
            )
            .properties(
                height=230,
                padding={
                    "left": 30,
                    "right": 25,
                    "top": 20,
                    "bottom": 25,
                },
            )
        )

        congestion_chart_col, congestion_text_col = st.columns([1.1, 1])

        with congestion_chart_col:
            st.altair_chart(congestion_chart, width="stretch")

        high_row = congestion_df[
            congestion_df["congestion_level"] == "high"
        ]

        high_congestion_display = (
            f"{float(high_row.iloc[0]['percentage']):.1f}%"
            if not high_row.empty
            else "N/A"
        )

        with congestion_text_col:
            st.markdown(
                f"""
<div class="mobility-congestion-card">
<div class="mobility-card-title">Why This Matters for the Convention</div>
<p>
<strong>{high_congestion_display}</strong> of the selected historical
observations are classified as high congestion.
</p>
<p>
That existing congestion baseline means convention-generated trips should
be managed around recurring peak periods rather than added to them without
coordination.
</p>
</div>
""",
                unsafe_allow_html=True,
            )

    # ---------------------------------------------------------
    # Convention Transportation Risk Areas
    # ---------------------------------------------------------

    st.divider()

    with st.expander(
        "🗺️ Full-Year 2025 Transportation Risk Areas",
        expanded=False,
    ):
        st.write(
            "Using the full 2025 traffic dataset, this analysis identifies historically "
            "congested sensor locations that may require additional transportation "
            "planning during the November 3–5, 2027 convention. These locations already "
            "experience recurring congestion and could face additional pressure from "
            "convention-generated traffic."
        )

        sensor_data = get_sensor_summary()
        sensor_df = pd.DataFrame(sensor_data)

        if not sensor_df.empty:
            risk_df = sensor_df.copy()

            # Rank existing mobility vulnerabilities using three historical
            # indicators: recurring high congestion, heavier traffic volume,
            # and lower average speed.
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

            # Display the highest-risk historical locations.
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
                latitude=risk_df["latitude"].mean(),
                longitude=risk_df["longitude"].mean(),
                zoom=10,
                pitch=0,
            )

            # Heatmap emphasizes areas where transportation risk clusters.
            heatmap_layer = pdk.Layer(
                "HeatmapLayer",
                data=risk_df,
                get_position="[longitude, latitude]",
                get_weight="convention_risk_score",
                radius_pixels=55,
                intensity=1,
                threshold=0.05,
                pickable=False,
            )

            # Point layer keeps individual high-risk sensor locations
            # available for hover details.
            sensor_layer = pdk.Layer(
                "ScatterplotLayer",
                data=risk_df,
                get_position="[longitude, latitude]",
                get_radius=75,
                get_fill_color=[37, 109, 180, 120],
                get_line_color=[20, 43, 74, 180],
                line_width_min_pixels=1,
                stroked=True,
                filled=True,
                pickable=True,
            )

            deck = pdk.Deck(
                layers=[
                    heatmap_layer,
                    sensor_layer,
                ],
                initial_view_state=view_state,
                map_style="dark",
                tooltip=True,
            )

            st.pydeck_chart(
                deck,
                width="stretch",
            )

            st.caption(
                "Heat intensity highlights clusters of higher transportation "
                "risk. Points identify the highest-risk sensor locations."
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
    <p><strong>November peak traffic:</strong> {peak_hour_label}</p>
    <p><strong>Average traffic volume:</strong> {summary['average_vehicle_count']:.2f} vehicles</p>
    <p><strong>Average speed:</strong> {summary['average_speed_kmh']:.2f} km/h</p>
    <p><strong>High congestion:</strong> {summary['high_congestion_percent']:.2f}% of November traffic observations</p>
    <p><strong>Convention impact:</strong> Approximately 2,500 additional vehicle trips per day could increase pressure during already-busy travel periods.</p>
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
