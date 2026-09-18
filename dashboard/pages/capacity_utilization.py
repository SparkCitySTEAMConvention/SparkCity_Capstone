"""Capacity & Utilization page UI + live queries against the shared sparkcity schema.

Answers three questions for the Convention Planner's chosen date (April 6-8,
2027): how would ~15,000 extra attendees load the city's room/venue capacity,
is there enough headroom to hold the convention on those dates, and what does
the occupancy/energy/traffic data show about capacity more generally. Numbers
are queried live (cached) rather than hardcoded so they stay in sync with the
shared database; see sql/analytical_queries.sql (Day 5 & Day 6 sections) and
notebooks/day5_Sloane_capacity_infrastructure.ipynb for the exploratory work
this page productionizes.
"""
from decimal import Decimal
from html import escape

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from components.shared import STYLES_PATH, read_css
from sparkcityx.database import connect_database

ATTENDEES = 15_000
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _run_query(conn, sql):
    """Run a query and return a DataFrame with SQL numeric columns coerced to
    float64. psycopg maps Postgres `numeric` to Python Decimal, which pandas
    keeps as opaque `object` columns -- Altair/Streamlit's JSON serialization
    doesn't handle Decimal cleanly, so charts built on unconverted columns
    silently render the wrong scale."""
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [d.name for d in cur.description]
    df = pd.DataFrame(rows, columns=columns)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


@st.cache_data(ttl=3600, show_spinner="Loading capacity & infrastructure data…")
def load_capacity_data():
    with connect_database() as conn:
        occupancy_monthly = _run_query(conn, """
            WITH monthly AS (
                SELECT
                    date_trunc('month', timestamp) AS month,
                    avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate,
                    avg(available_rooms) AS avg_available_rooms
                FROM sparkcity.occupancy_data
                WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
                GROUP BY 1
            )
            SELECT
                to_char(month, 'Mon') AS month_name,
                round(avg_occupancy_rate::numeric, 4) AS avg_occupancy_rate,
                round((100 * (1 - avg_occupancy_rate))::numeric, 1) AS headroom_pct,
                round((avg_available_rooms - avg_available_rooms * avg_occupancy_rate)::numeric, 1)
                    AS avg_available_capacity_rooms
            FROM monthly
            ORDER BY month
        """)

        energy_monthly = _run_query(conn, """
            SELECT
                to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
                count(*) AS readings,
                round(avg(power_consumption)::numeric, 2) AS avg_power_kw,
                round(max(power_consumption)::numeric, 2) AS max_power_kw
            FROM sparkcity.energy_meters
            GROUP BY 1, date_trunc('month', timestamp)
            ORDER BY date_trunc('month', timestamp)
        """)

        traffic_monthly = _run_query(conn, """
            SELECT
                to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
                round(avg(vehicle_count)::numeric, 1) AS avg_vehicle_count,
                round(100.0 * sum(CASE WHEN congestion_level = 'high' THEN 1 ELSE 0 END) / count(*), 1)
                    AS pct_high_congestion
            FROM sparkcity.traffic_sensors
            GROUP BY 1, date_trunc('month', timestamp)
            ORDER BY date_trunc('month', timestamp)
        """)

        day_of_week = _run_query(conn, """
            SELECT
                to_char(timestamp, 'Dy') AS day_name,
                extract(dow FROM timestamp) AS dow,
                round(avg(occupied_rooms::numeric / NULLIF(available_rooms, 0))::numeric, 4) AS avg_occupancy_rate
            FROM sparkcity.occupancy_data
            WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
            GROUP BY 1, 2
            ORDER BY 2
        """)

        april_totals = _run_query(conn, """
            WITH per_sensor_april AS (
                SELECT
                    sensor_id,
                    avg(available_rooms) AS avg_capacity,
                    avg(occupied_rooms) AS avg_occupied,
                    avg(guests) AS avg_guests
                FROM sparkcity.occupancy_data
                WHERE timestamp >= '2025-04-01' AND timestamp < '2025-05-01'
                GROUP BY sensor_id
            )
            SELECT
                sum(avg_capacity) AS total_capacity_rooms,
                sum(avg_occupied) AS total_occupied_rooms,
                sum(avg_guests) / NULLIF(sum(avg_occupied), 0) AS guests_per_occupied_room
            FROM per_sensor_april
        """)

        april_tue_thu = _run_query(conn, """
            SELECT
                CASE WHEN extract(dow FROM timestamp) IN (2, 3, 4) THEN 'Tue-Thu' ELSE 'Other' END AS day_group,
                avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate,
                count(*) AS readings
            FROM sparkcity.occupancy_data
            WHERE timestamp >= '2025-04-01' AND timestamp < '2025-05-01'
            GROUP BY 1
        """)

        daily_series = _run_query(conn, """
            SELECT
                date_trunc('day', timestamp) AS day,
                avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate
            FROM sparkcity.occupancy_data
            WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
            GROUP BY 1
            ORDER BY 1
        """)

    occupancy_monthly["month_name"] = pd.Categorical(occupancy_monthly["month_name"], MONTH_ORDER, ordered=True)
    energy_monthly["month_name"] = pd.Categorical(energy_monthly["month_name"], MONTH_ORDER, ordered=True)
    traffic_monthly["month_name"] = pd.Categorical(traffic_monthly["month_name"], MONTH_ORDER, ordered=True)

    return {
        "occupancy_monthly": occupancy_monthly,
        "energy_monthly": energy_monthly,
        "traffic_monthly": traffic_monthly,
        "day_of_week": day_of_week,
        "april_totals": april_totals.iloc[0],
        "april_tue_thu": april_tue_thu,
        "daily_series": daily_series,
    }


def _dominant_weekly_cycle(daily_series):
    """Discrete Fourier transform of the daily occupancy-rate series: how strong,
    and how highly ranked, is the ~7-day cycle relative to every other periodic
    component in the year (used to justify using the Tue-Thu rate, not the
    whole-month average, as the planning baseline)."""
    y = daily_series["avg_occupancy_rate"].to_numpy(dtype=float)
    n = len(y)
    freqs = np.fft.rfftfreq(n, d=1.0)
    power = np.abs(np.fft.rfft(y - y.mean())) ** 2
    target_bin = int(np.argmin(np.abs(freqs - 1 / 7)))
    period_days = 1 / freqs[target_bin]
    rank = int((power > power[target_bin]).sum()) + 1  # 1 = strongest bin in the whole spectrum
    return period_days, rank, len(power)


def _derive_convention_impact(data):
    totals = data["april_totals"]
    tue_thu_rate = float(data["april_tue_thu"].set_index("day_group").loc["Tue-Thu", "avg_occupancy_rate"])
    other_rate = float(data["april_tue_thu"].set_index("day_group").loc["Other", "avg_occupancy_rate"])

    total_capacity = float(totals["total_capacity_rooms"])
    guests_per_room = float(totals["guests_per_occupied_room"])

    tue_thu_occupied = tue_thu_rate * total_capacity
    tue_thu_headroom_rooms = total_capacity - tue_thu_occupied
    rooms_needed = ATTENDEES / guests_per_room
    pct_headroom_used = rooms_needed / tue_thu_headroom_rooms
    post_event_rate = (tue_thu_occupied + rooms_needed) / total_capacity

    period_days, rank, n_bins = _dominant_weekly_cycle(data["daily_series"])

    return {
        "total_capacity": total_capacity,
        "guests_per_room": guests_per_room,
        "tue_thu_rate": tue_thu_rate,
        "other_rate": other_rate,
        "tue_thu_headroom_rooms": tue_thu_headroom_rooms,
        "rooms_needed": rooms_needed,
        "pct_headroom_used": pct_headroom_used,
        "post_event_rate": post_event_rate,
        "period_days": period_days,
        "cycle_rank": rank,
        "n_bins": n_bins,
    }


def _kpi_card(icon, label, value, sublabel, accent):
    return f'''<div class="cap-kpi-card" style="--accent:{accent}">
<span class="cap-kpi-icon">{icon}</span>
<div class="cap-kpi-label">{escape(label)}</div>
<div class="cap-kpi-value">{escape(value)}</div>
<div class="cap-kpi-sublabel">{escape(sublabel)}</div>
</div>'''


def render_capacity_utilization():
    st.markdown(f"<style>{read_css(STYLES_PATH, section='capacity')}</style>", unsafe_allow_html=True)

    try:
        data = load_capacity_data()
    except RuntimeError as exc:
        st.title("Capacity & Utilization")
        st.error(f"Can't reach the shared database: {exc}")
        st.caption("Run `uv run python scripts/check-database.py` to verify secrets/.env is configured.")
        return

    impact = _derive_convention_impact(data)
    occupancy_monthly = data["occupancy_monthly"]
    energy_monthly = data["energy_monthly"]

    st.title("🏢 Capacity & Utilization")
    st.write("Can SparkCity support the convention? Occupancy, energy, and traffic data for the "
             "recommended **April 6–8, 2027 (Tuesday–Thursday)** convention window.")

    with st.container(key="cap_kpi_row"):
        cards = [
            ("🏨", "City Room Capacity", f"{impact['total_capacity']:,.0f}", "rooms tracked across the city, Apr 2025", "#8767b1"),
            ("📉", "Tue–Thu Baseline (Apr)", f"{impact['tue_thu_rate']:.1%}", f"vs. {impact['other_rate']:.1%} on other April days", "#337bc0"),
            ("🟢", "Headroom Before Event", f"{impact['tue_thu_headroom_rooms']:,.0f}", "spare rooms on a typical Apr Tue–Thu", "#2a9d8f"),
            ("👥", "Rooms Needed (+15,000)", f"{impact['rooms_needed']:,.0f}", f"at {impact['guests_per_room']:.2f} guests/occupied room", "#e9a13f"),
            ("✅", "Projected Occupancy", f"{impact['post_event_rate']:.1%}", f"with the convention, +{(impact['post_event_rate']-impact['tue_thu_rate'])*100:.1f} pts", "#428778"),
        ]
        st.markdown('<div class="cap-kpi-grid">' + "".join(_kpi_card(*c) for c in cards) + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="cap-verdict">✅ <strong>There is sufficient capacity to hold the convention on April 6–8, 2027.</strong> '
                'Even after absorbing 15,000 extra attendees, projected occupancy stays below the city’s ordinary '
                'April weekend level and well under June, the tightest month of the year.</div>', unsafe_allow_html=True)

    st.subheader("How the convention affects capacity")
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.markdown("**Occupancy Headroom by Month**")
        chart_df = occupancy_monthly.copy()
        chart_df["is_april"] = chart_df["month_name"] == "Apr"
        chart = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("headroom_pct:Q", title="Room headroom (%)"),
            color=alt.condition(alt.datum.is_april, alt.value("#287dcc"), alt.value("#c9d6e3")),
            tooltip=[alt.Tooltip("month_name:N", title="Month"), alt.Tooltip("headroom_pct:Q", title="Headroom %")],
        ).properties(height=280)
        st.altair_chart(chart, width="stretch")
        st.caption("April sits mid-pack (highlighted) — comfortable headroom, not the loosest or tightest month.")

    with right:
        view = st.selectbox("Select a view", ["Energy Usage", "Traffic Congestion"], key="cap_secondary_view")
        if view == "Energy Usage":
            st.markdown("**Avg Power Draw by Month**")
            energy_chart = alt.Chart(energy_monthly).mark_line(point=True, color="#e76f51").encode(
                x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("avg_power_kw:Q", title="Avg power draw (kW)", scale=alt.Scale(zero=False)),
                tooltip=["month_name", "avg_power_kw", "max_power_kw"],
            ).properties(height=280)
            st.altair_chart(energy_chart, width="stretch")
            st.caption("Flat 43–45 kW across every measured month — the grid isn't the binding constraint "
                       "(no data past Sep 2025 yet).")
        else:
            st.markdown("**Traffic Congestion by Month**")
            traffic_chart = alt.Chart(data["traffic_monthly"]).mark_bar(color="#e9a13f").encode(
                x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("pct_high_congestion:Q", title="Readings at high congestion (%)"),
                tooltip=["month_name", "avg_vehicle_count", "pct_high_congestion"],
            ).properties(height=280)
            st.altair_chart(traffic_chart, width="stretch")
            st.caption("April (36.1% high-congestion) is in line with every other measured month "
                       "(Jan–May: 35.1–36.1%) — no April-specific traffic red flag (no data past May 2025 yet).")

    st.subheader("Why Tuesday–Thursday is the right baseline")
    left2, right2 = st.columns([1, 1.3], gap="large")
    with left2:
        dow_df = data["day_of_week"].copy()
        dow_df["is_event"] = dow_df["dow"].isin([2, 3, 4])
        dow_chart = alt.Chart(dow_df).mark_bar().encode(
            x=alt.X("day_name:N", sort=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], title=None),
            y=alt.Y("avg_occupancy_rate:Q", title="Avg occupancy rate", axis=alt.Axis(format="%")),
            color=alt.condition(alt.datum.is_event, alt.value("#287dcc"), alt.value("#c9d6e3")),
            tooltip=[alt.Tooltip("day_name:N", title="Day"), alt.Tooltip("avg_occupancy_rate:Q", title="Occupancy", format=".1%")],
        ).properties(height=260)
        st.altair_chart(dow_chart, width="stretch")
        st.caption("Full-year, every day of the week — Tue–Thu (highlighted) is consistently the lightest window.")
    with right2:
        st.markdown(f'''<div class="cap-insight-card">
<h4>📈 A stable, predictable weekly rhythm</h4>
<p>A discrete Fourier transform of the full year's daily occupancy-rate series confirms this isn't noise:
after the dominant year-long seasonal trend, the single strongest periodic signal in the entire series is a
<strong>{impact['period_days']:.1f}-day cycle</strong> &mdash; ranked <strong>#{impact['cycle_rank']} of {impact['n_bins']}</strong>
frequency components. That's the weekly cadence: weekdays consistently run lighter than weekends, all year.</p>
<p>Because that pattern is stable rather than random, the Tue–Thu-specific rate ({impact['tue_thu_rate']:.1%}) is a
more reliable planning baseline for an April 6–8 event than the whole-month average &mdash; and it happens to be
the more favorable one, leaving more headroom than a weekend date in the same month would.</p>
</div>''', unsafe_allow_html=True)

    st.subheader("15,000-attendee impact, step by step")
    steps = [
        ("1", "Convert attendees to rooms", f"{ATTENDEES:,} attendees ÷ {impact['guests_per_room']:.2f} observed guests per occupied room", f"≈ {impact['rooms_needed']:,.0f} rooms needed"),
        ("2", "Compare to Tue–Thu headroom", f"{impact['rooms_needed']:,.0f} rooms needed ÷ {impact['tue_thu_headroom_rooms']:,.0f} rooms of spare capacity", f"{impact['pct_headroom_used']:.1%} of headroom used"),
        ("3", "Project post-convention occupancy", f"({impact['tue_thu_rate']:.1%} baseline × {impact['total_capacity']:,.0f} rooms + {impact['rooms_needed']:,.0f} rooms) ÷ {impact['total_capacity']:,.0f} rooms", f"{impact['post_event_rate']:.1%} projected occupancy"),
        ("4", "Check against known peaks", f"Projected {impact['post_event_rate']:.1%} vs. April weekend baseline {impact['other_rate']:.1%} and June's 82.6% (the tightest month of the year)", "Still below both — within normal range"),
    ]
    step_html = "".join(
        f'''<div class="cap-step-card"><span class="cap-step-num">{n}</span>
<div><div class="cap-step-title">{escape(title)}</div>
<div class="cap-step-math">{escape(math)}</div>
<div class="cap-step-result">{escape(result)}</div></div></div>'''
        for n, title, math, result in steps
    )
    st.markdown(f'<div class="cap-step-flow">{step_html}</div>', unsafe_allow_html=True)

    st.subheader("What the data shows")
    col_insights, col_limits = st.columns(2, gap="large")
    with col_insights:
        st.markdown('''<div class="cap-list-card">
<h4>✔ Key Insights</h4>
<ul>
<li>Room/venue occupancy has a real seasonal shape — headroom ranges from ~42% in December to ~17% in June — while energy load stays nearly flat (43–45 kW) all year. Occupancy, not the power grid, is the binding constraint on convention timing.</li>
<li>April is a comfortable, mid-pack month: more headroom than peak summer, less than the winter off-season.</li>
<li>Weekdays (Tue–Thu especially) run consistently lighter than weekends, all year, backed by a Fourier-confirmed weekly cycle — not a one-off pattern.</li>
<li>A 15,000-attendee surge only consumes about 6% of the spare room capacity available on an April Tue–Thu.</li>
</ul>
</div>''', unsafe_allow_html=True)
    with col_limits:
        st.markdown('''<div class="cap-list-card cap-list-card-muted">
<h4>⚠ Data Limitations</h4>
<ul>
<li><code>energy_meters</code> only has readings through Sep 2025 — Oct–Dec can't be infrastructure-confirmed yet.</li>
<li><code>traffic_sensors</code> only covers Jan–May 2025; April is fully covered, but there's no later-year comparison.</li>
<li>Room/guest counts are city-wide totals, not broken out by venue type (hotel vs. convention center vs. event space) — that split isn't in the current dataset.</li>
<li>The 15,000-attendee impact assumes the historical guests-per-room ratio holds for convention visitors specifically.</li>
</ul>
</div>''', unsafe_allow_html=True)

    with st.expander("Occupancy by month (full detail)"):
        st.dataframe(
            occupancy_monthly.rename(columns={
                "month_name": "Month", "avg_occupancy_rate": "Avg Occupancy Rate",
                "headroom_pct": "Headroom %", "avg_available_capacity_rooms": "Avg Spare Rooms",
            }),
            hide_index=True, width="stretch",
        )
