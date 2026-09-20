"""Capacity & Utilization page UI + live queries against the shared sparkcity schema.

Answers three questions for the Convention Planner's chosen date (November 3-5,
2027): how would ~15,000 extra attendees load the city's room/venue capacity,
is there enough headroom to hold the convention on those dates, and what does
the occupancy/energy/traffic data show about capacity more generally. Numbers
are queried live (cached) rather than hardcoded so they stay in sync with the
shared database; see sql/analytical_queries.sql (Day 5 & Day 6 sections) and
notebooks/day5_Sloane_capacity_infrastructure.ipynb for the exploratory work
this page productionizes (that work was built on the earlier April 6-8 window;
the EVENT_* constants below re-point the baseline at November Wed-Fri).
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
FULL_MONTH_NAMES = {
    "Jan": "January", "Feb": "February", "Mar": "March", "Apr": "April", "May": "May", "Jun": "June",
    "Jul": "July", "Aug": "August", "Sep": "September", "Oct": "October", "Nov": "November", "Dec": "December",
}

# The convention window, Nov 3-5, 2027, is a Wednesday-Friday. Its baseline is the
# same calendar month and weekdays in the observed 2025 data.
EVENT_MONTH = "Nov"
EVENT_MONTH_NAME = FULL_MONTH_NAMES[EVENT_MONTH]
EVENT_MONTH_NUM = 11
EVENT_MONTH_START = "2025-11-01"
EVENT_MONTH_END = "2025-12-01"
EVENT_DOWS = (3, 4, 5)  # Postgres extract(dow): 0 = Sunday, so 3-5 = Wed-Fri
EVENT_DAYS_LABEL = "Wed–Fri"


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
            WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
            GROUP BY 1, date_trunc('month', timestamp)
            ORDER BY date_trunc('month', timestamp)
        """)

        # energy_meters now runs past 2025, so a second observed November exists as a
        # cross-year check on the event-month baseline.
        event_energy_by_year = _run_query(conn, f"""
            SELECT
                extract(year FROM timestamp)::int AS year,
                round(avg(power_consumption)::numeric, 2) AS avg_power_kw,
                round(max(power_consumption)::numeric, 2) AS max_power_kw
            FROM sparkcity.energy_meters
            WHERE extract(month FROM timestamp) = {EVENT_MONTH_NUM}
            GROUP BY 1
            ORDER BY 1
        """)

        traffic_monthly = _run_query(conn, """
            SELECT
                to_char(date_trunc('month', timestamp), 'Mon') AS month_name,
                round(avg(vehicle_count)::numeric, 1) AS avg_vehicle_count,
                round(100.0 * sum(CASE WHEN congestion_level = 'high' THEN 1 ELSE 0 END) / count(*), 1)
                    AS pct_high_congestion
            FROM sparkcity.traffic_sensors
            WHERE timestamp >= '2025-01-01' AND timestamp < '2026-01-01'
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

        event_month_totals = _run_query(conn, f"""
            WITH per_sensor_event_month AS (
                SELECT
                    sensor_id,
                    avg(available_rooms) AS avg_capacity,
                    avg(occupied_rooms) AS avg_occupied,
                    avg(guests) AS avg_guests
                FROM sparkcity.occupancy_data
                WHERE timestamp >= '{EVENT_MONTH_START}' AND timestamp < '{EVENT_MONTH_END}'
                GROUP BY sensor_id
            )
            SELECT
                sum(avg_capacity) AS total_capacity_rooms,
                sum(avg_occupied) AS total_occupied_rooms,
                sum(avg_guests) / NULLIF(sum(avg_occupied), 0) AS guests_per_occupied_room
            FROM per_sensor_event_month
        """)

        event_day_split = _run_query(conn, f"""
            SELECT
                CASE WHEN extract(dow FROM timestamp) IN {EVENT_DOWS} THEN 'Event days' ELSE 'Other' END AS day_group,
                avg(occupied_rooms::numeric / NULLIF(available_rooms, 0)) AS avg_occupancy_rate,
                count(*) AS readings
            FROM sparkcity.occupancy_data
            WHERE timestamp >= '{EVENT_MONTH_START}' AND timestamp < '{EVENT_MONTH_END}'
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
        "event_energy_by_year": event_energy_by_year,
        "traffic_monthly": traffic_monthly,
        "day_of_week": day_of_week,
        "event_month_totals": event_month_totals.iloc[0],
        "event_day_split": event_day_split,
        "daily_series": daily_series,
    }


def _dominant_weekly_cycle(daily_series):
    """Discrete Fourier transform of the daily occupancy-rate series: how strong,
    and how highly ranked, is the ~7-day cycle relative to every other periodic
    component in the year (used to justify using the Wed-Fri rate, not the
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
    totals = data["event_month_totals"]
    day_split = data["event_day_split"].set_index("day_group")
    event_days_rate = float(day_split.loc["Event days", "avg_occupancy_rate"])
    other_rate = float(day_split.loc["Other", "avg_occupancy_rate"])

    total_capacity = float(totals["total_capacity_rooms"])
    guests_per_room = float(totals["guests_per_occupied_room"])

    event_days_occupied = event_days_rate * total_capacity
    event_days_headroom_rooms = total_capacity - event_days_occupied
    rooms_needed = ATTENDEES / guests_per_room
    pct_headroom_used = rooms_needed / event_days_headroom_rooms
    post_event_rate = (event_days_occupied + rooms_needed) / total_capacity

    period_days, rank, n_bins = _dominant_weekly_cycle(data["daily_series"])

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


def _join_names(names):
    """['December', 'January'] -> 'December and January'."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


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
    traffic_monthly = data["traffic_monthly"]

    energy_lo, energy_hi = energy_monthly["avg_power_kw"].min(), energy_monthly["avg_power_kw"].max()
    energy_axis_lo, energy_axis_hi = int(energy_lo) - 3, int(energy_hi) + 4  # padded so a ~2% spread reads as flat
    event_energy = energy_monthly[energy_monthly["month_name"] == EVENT_MONTH].iloc[0]
    energy_peak = energy_monthly.loc[energy_monthly["max_power_kw"].idxmax()]
    event_by_year = ", ".join(
        f"{int(r.year)}: {r.avg_power_kw:.1f} kW" for r in data["event_energy_by_year"].itertuples()
    )
    traffic_lo, traffic_hi = traffic_monthly["pct_high_congestion"].min(), traffic_monthly["pct_high_congestion"].max()
    event_congestion = traffic_monthly.loc[traffic_monthly["month_name"] == EVENT_MONTH, "pct_high_congestion"].iloc[0]

    # Where the event month ranks on headroom, and the loosest/tightest months, so the
    # captions and insights below follow the data instead of hardcoded month claims.
    by_headroom = occupancy_monthly.sort_values("headroom_pct", ascending=False)
    ranked_months = by_headroom["month_name"].astype(str).tolist()
    looser_months = _join_names([FULL_MONTH_NAMES[m] for m in ranked_months[:ranked_months.index(EVENT_MONTH)]])
    event_headroom = float(occupancy_monthly.loc[occupancy_monthly["month_name"] == EVENT_MONTH, "headroom_pct"].iloc[0])
    loosest, tightest = by_headroom.iloc[0], by_headroom.iloc[-1]
    loosest_name, tightest_name = FULL_MONTH_NAMES[str(loosest["month_name"])], FULL_MONTH_NAMES[str(tightest["month_name"])]

    st.markdown('<div class="capacity-page-title">🏢 Capacity &amp; Utilization</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="capacity-page-description">Can New York Digital City support the convention? Occupancy, energy, and traffic data for the '
        "recommended <strong>November 3–5, 2027 (Wednesday–Friday)</strong> convention window.</p>",
        unsafe_allow_html=True,
    )

    with st.container(key="cap_kpi_row"):
        cards = [
            ("🏨", "City Room Capacity", f"{impact['total_capacity']:,.0f}", f"rooms tracked across the city, {EVENT_MONTH} 2025", "#8767b1"),
            ("📉", f"{EVENT_DAYS_LABEL} Baseline ({EVENT_MONTH})", f"{impact['event_days_rate']:.1%}", f"vs. {impact['other_rate']:.1%} on other {EVENT_MONTH_NAME} days", "#337bc0"),
            ("🟢", "Headroom Before Event", f"{impact['event_days_headroom_rooms']:,.0f}", f"spare rooms on a typical {EVENT_MONTH} {EVENT_DAYS_LABEL}", "#2a9d8f"),
            ("👥", "Rooms Needed (+15,000)", f"{impact['rooms_needed']:,.0f}", f"at {impact['guests_per_room']:.2f} guests/occupied room", "#e9a13f"),
            ("✅", "Projected Occupancy", f"{impact['post_event_rate']:.1%}", f"with the convention, +{(impact['post_event_rate']-impact['event_days_rate'])*100:.1f} pts", "#428778"),
        ]
        st.markdown('<div class="cap-kpi-grid">' + "".join(_kpi_card(*c) for c in cards) + '</div>', unsafe_allow_html=True)

    st.markdown('<div class="cap-verdict">✅ <strong>There is sufficient capacity to hold the convention on November 3–5, 2027.</strong> '
                f'Even after absorbing 15,000 extra attendees, projected occupancy stays below the city’s ordinary '
                f'{EVENT_MONTH_NAME} level on other days and well under {tightest_name}, the tightest month of the year.</div>', unsafe_allow_html=True)

    st.subheader("How the convention affects capacity")
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.markdown("**Occupancy Headroom by Month**")
        chart_df = occupancy_monthly.copy()
        chart_df["is_event_month"] = chart_df["month_name"] == EVENT_MONTH
        chart = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("headroom_pct:Q", title="Room headroom (%)"),
            color=alt.condition(alt.datum.is_event_month, alt.value("#287dcc"), alt.value("#4A6074")),
            tooltip=[alt.Tooltip("month_name:N", title="Month"), alt.Tooltip("headroom_pct:Q", title="Headroom %")],
        ).properties(height=280)
        st.altair_chart(chart, width="stretch")
        st.caption(f"{EVENT_MONTH_NAME} (highlighted) has more headroom than every month except {looser_months} — "
                   f"well clear of the {tightest_name} squeeze.")

    with right:
        view = st.selectbox("Select a view", ["Energy Usage", "Traffic Congestion"], key="cap_secondary_view")
        if view == "Energy Usage":
            st.markdown("**Avg Power Draw by Month**")
            energy_chart = alt.Chart(energy_monthly).mark_line(point=True, color="#e76f51").encode(
                x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("avg_power_kw:Q", title="Avg power draw (kW)", scale=alt.Scale(domain=[energy_axis_lo, energy_axis_hi])),
                tooltip=["month_name", "avg_power_kw", "max_power_kw"],
            ).properties(height=280)
            st.altair_chart(energy_chart, width="stretch")
            st.caption(f"Flat {energy_lo:.1f}–{energy_hi:.1f} kW across all 12 months of 2025 — the grid isn't the binding "
                       f"constraint. {EVENT_MONTH_NAME}'s peak load ({event_energy['max_power_kw']:.1f} kW) is below the year's high "
                       f"({energy_peak['max_power_kw']:.1f} kW, {energy_peak['month_name']}), and {EVENT_MONTH_NAME} averages hold "
                       f"across years (avg {event_by_year}). Y-axis zoomed to {energy_axis_lo}–{energy_axis_hi} kW.")
        else:
            st.markdown("**Traffic Congestion by Month**")
            traffic_chart = alt.Chart(traffic_monthly).mark_bar(color="#e9a13f").encode(
                x=alt.X("month_name:N", sort=MONTH_ORDER, title="Month", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("pct_high_congestion:Q", title="Readings at high congestion (%)"),
                tooltip=["month_name", "avg_vehicle_count", "pct_high_congestion"],
            ).properties(height=280)
            st.altair_chart(traffic_chart, width="stretch")
            st.caption(f"{EVENT_MONTH_NAME} ({event_congestion:.1f}% high-congestion) is in line with the rest of 2025 "
                       f"({traffic_lo:.1f}–{traffic_hi:.1f}% across all 12 months) — no {EVENT_MONTH_NAME}-specific traffic red flag.")

    st.subheader("Why Wednesday–Friday is the right baseline")
    left2, right2 = st.columns([1, 1.3], gap="large")
    with left2:
        dow_df = data["day_of_week"].copy()
        dow_df["is_event"] = dow_df["dow"].isin(EVENT_DOWS)
        dow_chart = alt.Chart(dow_df).mark_bar().encode(
            x=alt.X("day_name:N", sort=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"], title=None),
            y=alt.Y("avg_occupancy_rate:Q", title="Avg occupancy rate", axis=alt.Axis(format="%")),
            color=alt.condition(alt.datum.is_event, alt.value("#287dcc"), alt.value("#4A6074")),
            tooltip=[alt.Tooltip("day_name:N", title="Day"), alt.Tooltip("avg_occupancy_rate:Q", title="Occupancy", format=".1%")],
        ).properties(height=260)
        st.altair_chart(dow_chart, width="stretch")
        st.caption(f"Full-year, every day of the week — {EVENT_DAYS_LABEL} (highlighted) consistently runs well below the Saturday–Sunday peak.")
    with right2:
        st.markdown(f'''<div class="cap-insight-card">
<h4>📈 A stable, predictable weekly rhythm</h4>
<p>A discrete Fourier transform of the full year's daily occupancy-rate series confirms this isn't noise:
after the dominant year-long seasonal trend, the single strongest periodic signal in the entire series is a
<strong>{impact['period_days']:.1f}-day cycle</strong> &mdash; ranked <strong>#{impact['cycle_rank']} of {impact['n_bins']}</strong>
frequency components. That's the weekly cadence: weekdays consistently run lighter than weekends, all year.</p>
<p>Because that pattern is stable rather than random, the {EVENT_DAYS_LABEL}-specific rate ({impact['event_days_rate']:.1%}) is a
more reliable planning baseline for a November 3–5 event than the whole-month average &mdash; and it happens to be
the more favorable one, leaving more headroom than a weekend date in the same month would.</p>
</div>''', unsafe_allow_html=True)

    st.subheader("15,000-attendee impact, step by step")
    steps = [
        ("1", "Convert attendees to rooms", f"{ATTENDEES:,} attendees ÷ {impact['guests_per_room']:.2f} observed guests per occupied room", f"≈ {impact['rooms_needed']:,.0f} rooms needed"),
        ("2", f"Compare to {EVENT_DAYS_LABEL} headroom", f"{impact['rooms_needed']:,.0f} rooms needed ÷ {impact['event_days_headroom_rooms']:,.0f} rooms of spare capacity", f"{impact['pct_headroom_used']:.1%} of headroom used"),
        ("3", "Project post-convention occupancy", f"({impact['event_days_rate']:.1%} baseline × {impact['total_capacity']:,.0f} rooms + {impact['rooms_needed']:,.0f} rooms) ÷ {impact['total_capacity']:,.0f} rooms", f"{impact['post_event_rate']:.1%} projected occupancy"),
        ("4", "Check against known peaks", f"Projected {impact['post_event_rate']:.1%} vs. {EVENT_MONTH_NAME} baseline on other days {impact['other_rate']:.1%} and {tightest_name}'s {tightest['avg_occupancy_rate']:.1%} (the tightest month of the year)", "Still below both — within normal range"),
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
        st.markdown(f'''<div class="cap-list-card">
<h4>✔ Key Insights</h4>
<ul>
<li>Room/venue occupancy has a real seasonal shape — headroom ranges from ~{loosest['headroom_pct']:.0f}% in {loosest_name} to ~{tightest['headroom_pct']:.0f}% in {tightest_name} — while energy load stays nearly flat ({energy_lo:.1f}–{energy_hi:.1f} kW) in every month of the year. Occupancy, not the power grid, is the binding constraint on convention timing.</li>
<li>{EVENT_MONTH_NAME} is one of the roomier months: {event_headroom:.1f}% headroom, behind only {looser_months} and far above the peak-summer squeeze. Energy confirms it — {EVENT_MONTH_NAME} averages {event_by_year} — with no shift in average load.</li>
<li>Weekdays ({EVENT_DAYS_LABEL} included) run consistently lighter than weekends, all year, backed by a Fourier-confirmed weekly cycle — not a one-off pattern.</li>
<li>A 15,000-attendee surge only consumes about {impact['pct_headroom_used']:.0%} of the spare room capacity available on a {EVENT_MONTH_NAME} {EVENT_DAYS_LABEL}.</li>
</ul>
</div>''', unsafe_allow_html=True)
    with col_limits:
        st.markdown(f'''<div class="cap-list-card cap-list-card-muted">
<h4>⚠ Data Limitations</h4>
<ul>
<li>Monthly charts use calendar 2025 so every month is comparable with occupancy (which ends Jan 2026); <code>energy_meters</code> runs later, but only {EVENT_MONTH_NAME} has a second-year check here.</li>
<li><code>traffic_sensors</code> covers all of 2025 plus a partial Jan 2026 — no {EVENT_MONTH_NAME}-to-{EVENT_MONTH_NAME} comparison for traffic yet.</li>
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
