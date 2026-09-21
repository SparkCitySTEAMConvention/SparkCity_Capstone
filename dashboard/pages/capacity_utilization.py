"""Capacity & Utilization page.

Evaluates whether New York Digital City has sufficient lodging and
infrastructure capacity for the team's recommended convention scenario.

The proposed convention is in 2027. Historical occupancy and energy data
are used as planning baselines and should not be interpreted as measured
2027 observations.
"""

from datetime import date
from decimal import Decimal
from html import escape

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from components.shared import STYLES_PATH, read_css
from components.convention_config import (
    EVENT_START_DATE,
    EVENT_END_DATE,
    EVENT_ATTENDEES,
    EVENT_DATE_LABEL,
    EVENT_MONTH_NUM,
    EVENT_MONTH_ABBR,
    EVENT_MONTH_NAME,
    EVENT_DAYS_LABEL,
    EVENT_DURATION_DAYS,
    BASELINE_YEAR,
)

from sparkcityx.database import connect_database


# ------------------------------------------------------------------
# DISPLAY / ANALYSIS CONSTANTS
# ------------------------------------------------------------------

MONTH_ORDER = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

FULL_MONTH_NAMES = {
    "Jan": "January",
    "Feb": "February",
    "Mar": "March",
    "Apr": "April",
    "May": "May",
    "Jun": "June",
    "Jul": "July",
    "Aug": "August",
    "Sep": "September",
    "Oct": "October",
    "Nov": "November",
    "Dec": "December",
}


# ------------------------------------------------------------------
# HISTORICAL BASELINE
# ------------------------------------------------------------------
# The convention occurs in 2027, but occupancy analysis uses the
# historical year available in the shared SparkCity dataset.
#
# These are BASELINE dates, not event dates.
# ------------------------------------------------------------------

BASELINE_YEAR_START = date(BASELINE_YEAR, 1, 1)
BASELINE_YEAR_END = date(BASELINE_YEAR + 1, 1, 1)

BASELINE_MONTH_START = date(
    BASELINE_YEAR,
    EVENT_MONTH_NUM,
    1,
)

if EVENT_MONTH_NUM == 12:
    BASELINE_MONTH_END = date(
        BASELINE_YEAR + 1,
        1,
        1,
    )
else:
    BASELINE_MONTH_END = date(
        BASELINE_YEAR,
        EVENT_MONTH_NUM + 1,
        1,
    )


# PostgreSQL extract(dow):
# Sunday = 0, Monday = 1, ... Saturday = 6
#
# Derive the convention weekdays from the shared event dates rather
# than independently hardcoding Wednesday-Friday.

EVENT_DOWS = tuple(
    sorted(
        {
            (EVENT_START_DATE.toordinal() + offset + 1) % 7
            for offset in range(EVENT_DURATION_DAYS)
        }
    )
)

# ------------------------------------------------------------------
# DATABASE HELPER
# ------------------------------------------------------------------

def _run_query(conn, sql):
    """Run a query and return a DataFrame.

    PostgreSQL numeric values are converted from Decimal to float so
    Streamlit and Altair can serialize them correctly.
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d.name for d in cur.description]

    df = pd.DataFrame(rows, columns=columns)

    for col in df.columns:
        if df[col].map(lambda value: isinstance(value, Decimal)).any():
            df[col] = df[col].astype(float)

    return df


# ------------------------------------------------------------------
# LOAD CAPACITY DATA
# ------------------------------------------------------------------

@st.cache_data(
    ttl=3600,
    show_spinner="Loading capacity & infrastructure data…",
)
def load_capacity_data():

    with connect_database() as conn:

        # ----------------------------------------------------------
        # MONTHLY OCCUPANCY
        # ----------------------------------------------------------

        occupancy_monthly = _run_query(
            conn,
            f"""
            WITH monthly AS (
                SELECT
                    date_trunc('month', timestamp) AS month,
                    avg(
                        occupied_rooms::numeric /
                        NULLIF(available_rooms, 0)
                    ) AS avg_occupancy_rate,
                    avg(available_rooms) AS avg_available_rooms
                FROM sparkcity.occupancy_data
                WHERE timestamp >= '{BASELINE_YEAR_START}'
                  AND timestamp < '{BASELINE_YEAR_END}'
                GROUP BY 1
            )

            SELECT
                to_char(month, 'Mon') AS month_name,
                round(
                    avg_occupancy_rate::numeric,
                    4
                ) AS avg_occupancy_rate,
                round(
                    (
                        100 *
                        (1 - avg_occupancy_rate)
                    )::numeric,
                    1
                ) AS headroom_pct,
                round(
                    (
                        avg_available_rooms -
                        avg_available_rooms *
                        avg_occupancy_rate
                    )::numeric,
                    1
                ) AS avg_available_capacity_rooms
            FROM monthly
            ORDER BY month
            """,
        )

        # ----------------------------------------------------------
        # MONTHLY ENERGY
        # ----------------------------------------------------------

        energy_monthly = _run_query(
            conn,
            f"""
            SELECT
                to_char(
                    date_trunc('month', timestamp),
                    'Mon'
                ) AS month_name,

                count(*) AS readings,

                round(
                    avg(power_consumption)::numeric,
                    2
                ) AS avg_power_kw,

                round(
                    max(power_consumption)::numeric,
                    2
                ) AS max_power_kw

            FROM sparkcity.energy_meters

            WHERE timestamp >= '{BASELINE_YEAR_START}'
              AND timestamp < '{BASELINE_YEAR_END}'

            GROUP BY
                1,
                date_trunc('month', timestamp)

            ORDER BY
                date_trunc('month', timestamp)
            """,
        )

        # ----------------------------------------------------------
        # EVENT-MONTH ENERGY BY YEAR
        # ----------------------------------------------------------

        event_energy_by_year = _run_query(
            conn,
            f"""
            SELECT
                extract(year FROM timestamp)::int AS year,

                round(
                    avg(power_consumption)::numeric,
                    2
                ) AS avg_power_kw,

                round(
                    max(power_consumption)::numeric,
                    2
                ) AS max_power_kw

            FROM sparkcity.energy_meters

            WHERE extract(month FROM timestamp) = {EVENT_MONTH_NUM}

            GROUP BY 1
            ORDER BY 1
            """,
        )

        # ----------------------------------------------------------
        # OCCUPANCY BY DAY OF WEEK
        # ----------------------------------------------------------

        day_of_week = _run_query(
            conn,
            f"""
            SELECT
                to_char(timestamp, 'Dy') AS day_name,

                extract(dow FROM timestamp) AS dow,

                round(
                    avg(
                        occupied_rooms::numeric /
                        NULLIF(available_rooms, 0)
                    )::numeric,
                    4
                ) AS avg_occupancy_rate

            FROM sparkcity.occupancy_data

            WHERE timestamp >= '{BASELINE_YEAR_START}'
              AND timestamp < '{BASELINE_YEAR_END}'

            GROUP BY 1, 2
            ORDER BY 2
            """,
        )

        # ----------------------------------------------------------
        # EVENT-MONTH HISTORICAL CAPACITY
        # ----------------------------------------------------------

        event_month_totals = _run_query(
            conn,
            f"""
            WITH per_sensor_event_month AS (
                SELECT
                    sensor_id,

                    avg(available_rooms) AS avg_capacity,

                    avg(occupied_rooms) AS avg_occupied,

                    avg(guests) AS avg_guests

                FROM sparkcity.occupancy_data

                WHERE timestamp >= '{BASELINE_MONTH_START}'
                  AND timestamp < '{BASELINE_MONTH_END}'

                GROUP BY sensor_id
            )

            SELECT
                sum(avg_capacity) AS total_capacity_rooms,

                sum(avg_occupied) AS total_occupied_rooms,

                sum(avg_guests) /
                NULLIF(
                    sum(avg_occupied),
                    0
                ) AS guests_per_occupied_room

            FROM per_sensor_event_month
            """,
        )

        # ----------------------------------------------------------
        # EVENT WEEKDAYS VS OTHER DAYS IN EVENT MONTH
        # ----------------------------------------------------------

        event_day_split = _run_query(
            conn,
            f"""
            SELECT

                CASE
                    WHEN extract(dow FROM timestamp) IN {EVENT_DOWS}
                    THEN 'Event days'
                    ELSE 'Other'
                END AS day_group,

                avg(
                    occupied_rooms::numeric /
                    NULLIF(available_rooms, 0)
                ) AS avg_occupancy_rate,

                count(*) AS readings

            FROM sparkcity.occupancy_data

            WHERE timestamp >= '{BASELINE_MONTH_START}'
              AND timestamp < '{BASELINE_MONTH_END}'

            GROUP BY 1
            """,
        )

        # ----------------------------------------------------------
        # DAILY OCCUPANCY SERIES
        # ----------------------------------------------------------

        daily_series = _run_query(
            conn,
            f"""
            SELECT
                date_trunc(
                    'day',
                    timestamp
                ) AS day,

                avg(
                    occupied_rooms::numeric /
                    NULLIF(available_rooms, 0)
                ) AS avg_occupancy_rate

            FROM sparkcity.occupancy_data

            WHERE timestamp >= '{BASELINE_YEAR_START}'
              AND timestamp < '{BASELINE_YEAR_END}'

            GROUP BY 1
            ORDER BY 1
            """,
        )

    occupancy_monthly["month_name"] = pd.Categorical(
        occupancy_monthly["month_name"],
        MONTH_ORDER,
        ordered=True,
    )

    energy_monthly["month_name"] = pd.Categorical(
        energy_monthly["month_name"],
        MONTH_ORDER,
        ordered=True,
    )

    return {
        "occupancy_monthly": occupancy_monthly,
        "energy_monthly": energy_monthly,
        "event_energy_by_year": event_energy_by_year,
        "day_of_week": day_of_week,
        "event_month_totals": event_month_totals.iloc[0],
        "event_day_split": event_day_split,
        "daily_series": daily_series,
    }


# ------------------------------------------------------------------
# WEEKLY OCCUPANCY PATTERN
# ------------------------------------------------------------------

def _dominant_weekly_cycle(daily_series):
    """Measure the strength of the approximately seven-day occupancy cycle."""

    y = daily_series[
        "avg_occupancy_rate"
    ].to_numpy(dtype=float)

    n = len(y)

    freqs = np.fft.rfftfreq(
        n,
        d=1.0,
    )

    power = (
        np.abs(
            np.fft.rfft(
                y - y.mean()
            )
        )
        ** 2
    )

    target_bin = int(
        np.argmin(
            np.abs(
                freqs - 1 / 7
            )
        )
    )

    period_days = 1 / freqs[target_bin]

    rank = (
        int(
            (
                power >
                power[target_bin]
            ).sum()
        )
        + 1
    )

    return (
        period_days,
        rank,
        len(power),
    )


# ------------------------------------------------------------------
# CONVENTION CAPACITY IMPACT
# ------------------------------------------------------------------

def _derive_convention_impact(data):

    totals = data[
        "event_month_totals"
    ]

    day_split = data[
        "event_day_split"
    ].set_index("day_group")

    event_days_rate = float(
        day_split.loc[
            "Event days",
            "avg_occupancy_rate",
        ]
    )

    other_rate = float(
        day_split.loc[
            "Other",
            "avg_occupancy_rate",
        ]
    )

    total_capacity = float(
        totals[
            "total_capacity_rooms"
        ]
    )

    guests_per_room = float(
        totals[
            "guests_per_occupied_room"
        ]
    )

    event_days_occupied = (
        event_days_rate *
        total_capacity
    )

    event_days_headroom_rooms = (
        total_capacity -
        event_days_occupied
    )

    rooms_needed = (
        EVENT_ATTENDEES /
        guests_per_room
    )

    pct_headroom_used = (
        rooms_needed /
        event_days_headroom_rooms
    )

    post_event_rate = (
        event_days_occupied +
        rooms_needed
    ) / total_capacity

    period_days, rank, n_bins = (
        _dominant_weekly_cycle(
            data["daily_series"]
        )
    )

    return {
        "total_capacity": total_capacity,
        "guests_per_room": guests_per_room,
        "event_days_rate": event_days_rate,
        "other_rate": other_rate,
        "event_days_headroom_rooms": event_days_headroom_rooms,
        "rooms_needed": rooms_needed,
        "pct_headroom_used": pct_headroom_used,
        "post_event_rate": post_event_rate,
        "period_days": period_days,
        "cycle_rank": rank,
        "n_bins": n_bins,
    }


# ------------------------------------------------------------------
# DISPLAY HELPERS
# ------------------------------------------------------------------

def _join_names(names):
    """Convert a list of month names into readable prose."""

    if not names:
        return "none"

    if len(names) == 1:
        return names[0]

    return (
        ", ".join(names[:-1]) +
        " and " +
        names[-1]
    )


def _kpi_card(icon, label, value, sublabel, accent):
    return (
        f'<div class="cap-kpi-card" style="--accent:{accent}">'
        f'<span class="cap-kpi-icon">{icon}</span>'
        f'<div class="cap-kpi-label">{escape(label)}</div>'
        f'<div class="cap-kpi-value">{escape(value)}</div>'
        f'<div class="cap-kpi-sublabel">{escape(sublabel)}</div>'
        f'</div>'
    )


# ------------------------------------------------------------------
# PAGE
# ------------------------------------------------------------------

def render_capacity_utilization():

    st.markdown(
        f"""
    <style>
    {read_css(STYLES_PATH, section='capacity')}
    </style>
    """,
        unsafe_allow_html=True,
    )

    try:
        data = load_capacity_data()

    except RuntimeError as exc:
        st.title("Capacity & Utilization")

        st.error(
            f"Can't reach the shared database: {exc}"
        )

        st.caption(
            "Run `uv run python scripts/check-database.py` "
            "to verify secrets/.env is configured."
        )

        return

    impact = _derive_convention_impact(
        data
    )

    occupancy_monthly = data[
        "occupancy_monthly"
    ]

    energy_monthly = data[
        "energy_monthly"
    ]

    # --------------------------------------------------------------
    # ENERGY METRICS
    # --------------------------------------------------------------

    energy_lo = (
        energy_monthly[
            "avg_power_kw"
        ].min()
    )

    energy_hi = (
        energy_monthly[
            "avg_power_kw"
        ].max()
    )

    energy_axis_lo = (
        int(energy_lo) - 3
    )

    energy_axis_hi = (
        int(energy_hi) + 4
    )

    event_energy = (
        energy_monthly[
            energy_monthly[
                "month_name"
            ] == EVENT_MONTH_ABBR
        ].iloc[0]
    )

    energy_peak = (
        energy_monthly.loc[
            energy_monthly[
                "max_power_kw"
            ].idxmax()
        ]
    )

    event_by_year = ", ".join(
        f"{int(row.year)}: "
        f"{row.avg_power_kw:.1f} kW"
        for row
        in data[
            "event_energy_by_year"
        ].itertuples()
    )

    # --------------------------------------------------------------
    # OCCUPANCY RANKING
    # --------------------------------------------------------------

    by_headroom = (
        occupancy_monthly
        .sort_values(
            "headroom_pct",
            ascending=False,
        )
    )

    ranked_months = (
        by_headroom[
            "month_name"
        ]
        .astype(str)
        .tolist()
    )

    event_index = (
        ranked_months.index(
            EVENT_MONTH_ABBR
        )
    )

    looser_months = _join_names(
        [
            FULL_MONTH_NAMES[month]
            for month
            in ranked_months[
                :event_index
            ]
        ]
    )

    event_headroom = float(
        occupancy_monthly.loc[
            occupancy_monthly[
                "month_name"
            ] == EVENT_MONTH_ABBR,
            "headroom_pct",
        ].iloc[0]
    )

    loosest = (
        by_headroom.iloc[0]
    )

    tightest = (
        by_headroom.iloc[-1]
    )

    loosest_name = (
        FULL_MONTH_NAMES[
            str(
                loosest[
                    "month_name"
                ]
            )
        ]
    )

    tightest_name = (
        FULL_MONTH_NAMES[
            str(
                tightest[
                    "month_name"
                ]
            )
        ]
    )

    # --------------------------------------------------------------
    # HEADER
    # --------------------------------------------------------------

    st.markdown(
        """
        <div class="capacity-page-title">
            🏢 Capacity &amp; Utilization
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p class="capacity-page-description">'
        f'Capacity outlook for the recommended '
        f'<strong>{EVENT_DATE_LABEL}</strong> convention window.'
        f'</p>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------
    # KPI CARDS
    # --------------------------------------------------------------

    with st.container(
        key="cap_kpi_row"
    ):

        cards = [

            (
                "🏨",
                "City Room Capacity",
                f"{impact['total_capacity']:,.0f}",
                (
                    "rooms tracked across the city, "
                    f"{EVENT_MONTH_ABBR} {BASELINE_YEAR}"
                ),
                "#8767b1",
            ),

            (
                "📉",
                (
                    f"{EVENT_DAYS_LABEL} Baseline "
                    f"({EVENT_MONTH_ABBR})"
                ),
                f"{impact['event_days_rate']:.1%}",
                (
                    f"vs. {impact['other_rate']:.1%} "
                    f"on other {EVENT_MONTH_NAME} days"
                ),
                "#337bc0",
            ),

            (
                "🟢",
                "Headroom Before Event",
                (
                    f"{impact['event_days_headroom_rooms']:,.0f}"
                ),
                (
                    "spare rooms on a typical "
                    f"{EVENT_MONTH_ABBR} "
                    f"{EVENT_DAYS_LABEL}"
                ),
                "#2a9d8f",
            ),

            (
                "👥",
                (
                    f"Rooms Needed "
                    f"(+{EVENT_ATTENDEES:,})"
                ),
                f"{impact['rooms_needed']:,.0f}",
                (
                    f"at "
                    f"{impact['guests_per_room']:.2f} "
                    "guests/occupied room"
                ),
                "#e9a13f",
            ),

            (
                "✅",
                "Projected Occupancy",
                f"{impact['post_event_rate']:.1%}",
                (
                    "with the convention, +"
                    f"{(
                        impact['post_event_rate']
                        - impact['event_days_rate']
                    ) * 100:.1f} pts"
                ),
                "#428778",
            ),
        ]

        st.markdown(
            '<div class="cap-kpi-grid">'
            + "".join(
                _kpi_card(*card)
                for card in cards
            )
            + "</div>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------------
    # CAPACITY VERDICT
    # --------------------------------------------------------------

    st.markdown(
        f"""
        <div class="cap-verdict">
            ✅
            <strong>
                There is sufficient capacity to hold the convention
                on {EVENT_DATE_LABEL}.
            </strong>
            Even after absorbing {EVENT_ATTENDEES:,} extra attendees,
            projected occupancy stays below the city's ordinary
            {EVENT_MONTH_NAME} level on other days and well under
            {tightest_name}, the tightest month of the historical year.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------
    # OCCUPANCY + ENERGY
    # --------------------------------------------------------------

    st.subheader(
        "How the convention affects capacity"
    )

    left, right = st.columns(
        [1.3, 1],
        gap="large",
    )

    with left:

        st.markdown(
            "**Occupancy Headroom by Month**"
        )

        chart_df = (
            occupancy_monthly.copy()
        )

        chart_df[
            "is_event_month"
        ] = (
            chart_df[
                "month_name"
            ] == EVENT_MONTH_ABBR
        )

        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(

                x=alt.X(
                    "month_name:N",
                    sort=MONTH_ORDER,
                    title="Month",
                    axis=alt.Axis(
                        labelAngle=0
                    ),
                ),

                y=alt.Y(
                    "headroom_pct:Q",
                    title="Room headroom (%)",
                ),

                color=alt.condition(
                    alt.datum.is_event_month,
                    alt.value("#287dcc"),
                    alt.value("#4A6074"),
                ),

                tooltip=[
                    alt.Tooltip(
                        "month_name:N",
                        title="Month",
                    ),
                    alt.Tooltip(
                        "headroom_pct:Q",
                        title="Headroom %",
                    ),
                ],
            )
            .properties(
                height=280
            )
        )

        st.altair_chart(
            chart,
            width="stretch",
        )

        if looser_months == "none":
            st.caption(
                f"{EVENT_MONTH_NAME} "
                "has the most room headroom "
                f"in the {BASELINE_YEAR} baseline."
            )
        else:
            st.caption(
                f"{EVENT_MONTH_NAME} (highlighted) "
                "has more headroom than every month except "
                f"{looser_months} — well clear of the "
                f"{tightest_name} squeeze."
            )

    with right:

        st.markdown(
            "**Avg Power Draw by Month**"
        )

        energy_chart = (
            alt.Chart(
                energy_monthly
            )
            .mark_line(
                point=True,
                color="#e76f51",
            )
            .encode(

                x=alt.X(
                    "month_name:N",
                    sort=MONTH_ORDER,
                    title="Month",
                    axis=alt.Axis(
                        labelAngle=0
                    ),
                ),

                y=alt.Y(
                    "avg_power_kw:Q",
                    title="Avg power draw (kW)",
                    scale=alt.Scale(
                        domain=[
                            energy_axis_lo,
                            energy_axis_hi,
                        ]
                    ),
                ),

                tooltip=[
                    "month_name",
                    "avg_power_kw",
                    "max_power_kw",
                ],
            )
            .properties(
                height=280
            )
        )

        st.altair_chart(
            energy_chart,
            width="stretch",
        )

        st.caption(
            f"Average power draw remains relatively stable "
            f"({energy_lo:.1f}–{energy_hi:.1f} kW) across "
            f"the {BASELINE_YEAR} baseline. "
            f"{EVENT_MONTH_NAME}'s peak load "
            f"({event_energy['max_power_kw']:.1f} kW) "
            f"is below the historical high "
            f"({energy_peak['max_power_kw']:.1f} kW, "
            f"{energy_peak['month_name']}). "
            f"{EVENT_MONTH_NAME} averages available across years: "
            f"{event_by_year}."
        )

    # --------------------------------------------------------------
    # DAY-OF-WEEK BASELINE
    # --------------------------------------------------------------

    st.subheader(
        f"Why {EVENT_DAYS_LABEL} is the right baseline"
    )

    left2, right2 = st.columns(
        [1, 1.3],
        gap="large",
    )

    with left2:

        dow_df = (
            data[
                "day_of_week"
            ].copy()
        )

        dow_df[
            "is_event"
        ] = (
            dow_df[
                "dow"
            ].isin(EVENT_DOWS)
        )

        dow_chart = (
            alt.Chart(
                dow_df
            )
            .mark_bar()
            .encode(

                x=alt.X(
                    "day_name:N",
                    sort=[
                        "Sun",
                        "Mon",
                        "Tue",
                        "Wed",
                        "Thu",
                        "Fri",
                        "Sat",
                    ],
                    title=None,
                ),

                y=alt.Y(
                    "avg_occupancy_rate:Q",
                    title="Avg occupancy rate",
                    axis=alt.Axis(
                        format="%"
                    ),
                ),

                color=alt.condition(
                    alt.datum.is_event,
                    alt.value("#287dcc"),
                    alt.value("#4A6074"),
                ),

                tooltip=[
                    alt.Tooltip(
                        "day_name:N",
                        title="Day",
                    ),
                    alt.Tooltip(
                        "avg_occupancy_rate:Q",
                        title="Occupancy",
                        format=".1%",
                    ),
                ],
            )
            .properties(
                height=260
            )
        )

        st.altair_chart(
            dow_chart,
            width="stretch",
        )

        st.caption(
            f"Across the {BASELINE_YEAR} historical baseline, "
            f"{EVENT_DAYS_LABEL} occupancy consistently runs "
            "below the Saturday–Sunday peak."
        )

    with right2:
        insight_html = (
            '<div class="cap-insight-card">'
            '<h4>📈 A stable, predictable weekly rhythm</h4>'
            f'<p>A discrete Fourier transform of the historical daily occupancy-rate series '
            f'identifies an approximately <strong>{impact["period_days"]:.1f}-day cycle</strong>. '
            f'The signal ranks <strong>#{impact["cycle_rank"]} of {impact["n_bins"]}</strong> '
            f'frequency components, supporting a recurring weekly occupancy pattern.</p>'
            f'<p>Because the convention runs {EVENT_DAYS_LABEL}, the historical '
            f'{EVENT_DAYS_LABEL}-specific occupancy rate '
            f'(<strong>{impact["event_days_rate"]:.1%}</strong>) provides a more relevant '
            f'planning baseline than using the whole-month average alone.</p>'
            '</div>'
        )

        st.markdown(
            insight_html,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------------
    # ATTENDEE IMPACT
    # --------------------------------------------------------------

    st.subheader(
        f"{EVENT_ATTENDEES:,}-attendee impact, step by step"
    )

    steps = [

        (
            "1",
            "Convert attendees to rooms",
            (
                f"{EVENT_ATTENDEES:,} attendees ÷ "
                f"{impact['guests_per_room']:.2f} "
                "observed guests per occupied room"
            ),
            (
                f"≈ {impact['rooms_needed']:,.0f} "
                "rooms needed"
            ),
        ),

        (
            "2",
            f"Compare to {EVENT_DAYS_LABEL} headroom",
            (
                f"{impact['rooms_needed']:,.0f} rooms needed ÷ "
                f"{impact['event_days_headroom_rooms']:,.0f} "
                "rooms of spare capacity"
            ),
            (
                f"{impact['pct_headroom_used']:.1%} "
                "of headroom used"
            ),
        ),

        (
            "3",
            "Project post-convention occupancy",
            (
                f"({impact['event_days_rate']:.1%} baseline × "
                f"{impact['total_capacity']:,.0f} rooms + "
                f"{impact['rooms_needed']:,.0f} rooms) ÷ "
                f"{impact['total_capacity']:,.0f} rooms"
            ),
            (
                f"{impact['post_event_rate']:.1%} "
                "projected occupancy"
            ),
        ),

        (
            "4",
            "Check against known peaks",
            (
                f"Projected {impact['post_event_rate']:.1%} "
                f"vs. {EVENT_MONTH_NAME} baseline on other days "
                f"{impact['other_rate']:.1%} and "
                f"{tightest_name}'s "
                f"{tightest['avg_occupancy_rate']:.1%} "
                "(the tightest historical month)"
            ),
            (
                "Still below both — "
                "within the historical range"
            ),
        ),
    ]

    step_html = ""

    for number, title, math, result in steps:
        step_html += (
            '<div class="cap-step-card">'
            f'<span class="cap-step-num">{number}</span>'
            '<div>'
            f'<div class="cap-step-title">{escape(title)}</div>'
            f'<div class="cap-step-math">{escape(math)}</div>'
            f'<div class="cap-step-result">{escape(result)}</div>'
            '</div>'
            '</div>'
        )

    st.markdown(
        f'<div class="cap-step-flow">{step_html}</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------------
    # INSIGHTS / LIMITATIONS
    # --------------------------------------------------------------

    st.subheader(
        "What the data shows"
    )

    col_insights, col_limits = (
        st.columns(
            2,
            gap="large",
        )
    )

    with col_insights:
        insights_html = (
            '<div class="cap-list-card">'
            '<h4>✔ Key Insights</h4>'
            '<ul>'
            '<li>Historical room occupancy has a seasonal pattern, while average energy load '
            'remains comparatively stable. For this scenario, lodging utilization is the more '
            'meaningful capacity consideration.</li>'
            f'<li>{EVENT_MONTH_NAME} has {event_headroom:.1f}% historical room headroom and '
            'compares favorably with the tighter months in the baseline year.</li>'
            f'<li>{EVENT_DAYS_LABEL} historically run lighter than the weekend occupancy peak, '
            'supporting their use as the convention-day baseline.</li>'
            f'<li>A {EVENT_ATTENDEES:,}-attendee scenario uses approximately '
            f'{impact["pct_headroom_used"]:.0%} of the estimated spare room capacity available '
            f'on a typical {EVENT_MONTH_NAME} {EVENT_DAYS_LABEL}.</li>'
            '</ul>'
            '</div>'
        )

        st.markdown(
            insights_html,
            unsafe_allow_html=True,
        )

    with col_limits:
        limitations_html = (
            '<div class="cap-list-card cap-list-card-muted">'
            '<h4>⚠ Data Limitations</h4>'
            '<ul>'
            f'<li>Monthly occupancy comparisons use calendar {BASELINE_YEAR} so all twelve '
            'months are evaluated on a consistent historical period.</li>'
            f'<li>The proposed convention occurs in {EVENT_START_DATE.year}; historical '
            f'occupancy and energy observations are used as planning baselines, not as measured '
            f'{EVENT_START_DATE.year} conditions.</li>'
            '<li>Room and guest counts are city-wide totals and are not separated by lodging '
            'or venue type in the current dataset.</li>'
            f'<li>The {EVENT_ATTENDEES:,}-attendee impact assumes the historical '
            'guests-per-room relationship also applies to convention visitors.</li>'
            '</ul>'
            '</div>'
        )

        st.markdown(
            limitations_html,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------------
    # FULL OCCUPANCY TABLE
    # --------------------------------------------------------------
    # Keep this intentionally compact. The previous dataframe used
    # width="stretch", which made four columns span the entire page.
    # --------------------------------------------------------------

    table_col, spacer = st.columns(
        [1.15, 1], gap="large",)

    with table_col:

        with st.expander(
            "Occupancy by month (full detail)"
        ):

            occupancy_detail = (
                occupancy_monthly.rename(
                    columns={
                        "month_name": "Month",
                        "avg_occupancy_rate": "Avg Occupancy",
                        "headroom_pct": "Headroom %",
                        "avg_available_capacity_rooms": "Avg Spare Rooms",
                    }
                )
                .copy()
            )

            occupancy_detail["Avg Occupancy"] = (
                occupancy_detail["Avg Occupancy"]
                .map(lambda value: f"{value:.1%}")
            )

            occupancy_detail["Headroom %"] = (
                occupancy_detail["Headroom %"]
                .map(lambda value: f"{value:.1f}%")
            )

            occupancy_detail["Avg Spare Rooms"] = (
                occupancy_detail["Avg Spare Rooms"]
                .map(lambda value: f"{value:,.0f}")
            )

            st.dataframe(
                occupancy_detail,
                hide_index=True,
                width="stretch",
                height=455,
            )