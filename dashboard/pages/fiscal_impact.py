"""Historical fiscal profile and date explorer for the Spark City dashboard."""
import base64
import hashlib
import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import escape
from math import ceil
from pathlib import Path

import pandas as pd
import streamlit as st

from components.shared import STYLES_PATH, read_css
from sparkcityx.fiscal_analysis import calendar_analogues

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# The dashboard snapshot is deliberately tracked with the application. Notebook
# output under data/processed/ is Git-ignored and therefore unavailable to other
# developers and deployments.
FISCAL_RUNS_DIR = PROJECT_ROOT / "dashboard" / "data" / "fiscal_analysis"
OCCUPANCY_SNAPSHOT = PROJECT_ROOT / "dashboard" / "data" / "convention_monthly_inputs_2025.csv"
SOURCE_ICON_DIR = PROJECT_ROOT / "dashboard" / "assets" / "source_icons"
DEFAULT_EVENT_START = date(2027, 11, 3)
NYC_2025_HOTEL_ADR = 333.71
NYC_HOTEL_PERCENT_TAX = 0.1475
NYC_HOTEL_FLAT_FEES = 3.50
EVENT_SCENARIOS = {
    "Conservative": {
        "visitor_fraction": .40,
        "people_per_room": 2.3,
        "nonhotel_spend": 40,
        "local_retention": .50,
        "facility_allowance": 300_000,
        "service_cost": 20,
    },
    "Planning": {
        "visitor_fraction": .65,
        "people_per_room": 1.8,
        "nonhotel_spend": 90,
        "local_retention": .75,
        "facility_allowance": 500_000,
        "service_cost": 35,
    },
    "High activity": {
        "visitor_fraction": .85,
        "people_per_room": 1.3,
        "nonhotel_spend": 160,
        "local_retention": .90,
        "facility_allowance": 800_000,
        "service_cost": 70,
    },
}


def _month_label(month):
    """Format e.g. "2025-06" as "June 2025"; falls back to the raw string if unparseable."""
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


def _planner_range_label(start, end):
    """Format date objects compactly, including ranges that cross a month."""
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.strftime('%B')} {start.day}–{end.day}, {start.year}"
    return f"{start.strftime('%B')} {start.day} – {end.strftime('%B')} {end.day}, {end.year}"


def _max_same_month_duration(start, limit=7):
    """Limit analogue windows to the month used for their fiscal index."""
    return min(limit, monthrange(start.year, start.month)[1] - start.day + 1)


def _latest_complete_run_in(runs_dir):
    """Newest run under `runs_dir` marked complete in its own manifest.json.

    Mirrors the lineage-selection pattern used elsewhere in this project
    (see src/sparkcityx/day5.py:select_sources): never guess which run is
    current, only take the newest one the notebook itself finished and signed.
    """
    if not runs_dir.exists():
        return None
    complete = sorted(
        p.parent for p in runs_dir.glob("*/manifest.json")
        if json.loads(p.read_text()).get("status") == "complete"
    )
    return complete[-1] if complete else None


def _verify_run_artifacts(run_dir, manifest, filenames):
    """Reject missing or modified notebook outputs before the dashboard reads them."""
    recorded = manifest.get("artifacts_sha256")
    if not isinstance(recorded, dict):
        raise ValueError("Fiscal run manifest has no artifact hash inventory")
    for filename in filenames:
        path = run_dir / filename
        expected = recorded.get(filename)
        if not expected or not path.is_file():
            raise ValueError(f"Fiscal run is missing its signed {filename} artifact")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Fiscal run artifact failed integrity verification: {filename}")


@st.cache_data(ttl=300, show_spinner=False)
def _load_run():
    run_dir = _latest_complete_run_in(FISCAL_RUNS_DIR)
    if run_dir is None:
        return None
    manifest = json.loads((run_dir / "manifest.json").read_text())
    filenames = ("findings.md", "monthly.csv", "daily.csv")
    _verify_run_artifacts(run_dir, manifest, filenames)
    return {
        "run_dir": run_dir,
        "manifest": manifest,
        "findings": (run_dir / "findings.md").read_text(),
        "monthly": pd.read_csv(run_dir / "monthly.csv"),
        "daily": pd.read_csv(run_dir / "daily.csv", parse_dates=["day"]).set_index("day"),
    }


def _fmt_units(value):
    return f"{value:,.2f}"


def _fmt_money(value):
    return f"${value:,.0f}"


@lru_cache(maxsize=8)
def _source_icon_data_uri(filename):
    """Embed a tracked source favicon so it renders consistently for every user."""
    encoded = base64.b64encode((SOURCE_ICON_DIR / filename).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _source_list_html():
    """Build the cited source list with the originating organizations' marks."""
    sources = (
        (
            "nys_comptroller.png",
            "NYS Comptroller: 2025 NYC hotel ADR — 333.71 USD",
            "https://www.osc.ny.gov/press/releases/2026/07/dinapoli-nyc-hotel-industry-among-nations-largest-strongest",
            "",
        ),
        (
            "nyc_finance.png",
            "NYC Finance: hotel occupancy tax and 2 USD room fee",
            "https://www.nyc.gov/site/finance/business/business-hotel-room-occupancy-tax.page",
            " nyc-mark",
        ),
        (
            "nyc_311.png",
            "NYC 311: current 5.875% hotel occupancy tax",
            "https://portal.311.nyc.gov/article/?kanumber=KA-02794",
            "",
        ),
        (
            "nys_tax.png",
            "NYS Tax: current NYC combined sales-tax publications",
            "https://www.tax.ny.gov/pubs_and_bulls/publications/sales/local_rates_current.htm",
            "",
        ),
        (
            "nys_tax.png",
            "NYS Tax: 1.50 USD NYC hotel unit fee",
            "https://www.tax.ny.gov/pubs_and_bulls/tg_bulletins/st/hotel_and_motel_occupancy.htm",
            "",
        ),
        (
            "javits.png",
            "Javits: The Overview published package",
            "https://javitscenter.com/media/121804/the-overview_holiday-2025_v4.pdf",
            "",
        ),
    )
    links = []
    for filename, label, url, extra_class in sources:
        icon = _source_icon_data_uri(filename)
        links.append(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="fiscal-source-icon-shell{extra_class}">'
            f'<img class="fiscal-source-icon" src="{icon}" alt=""></span>'
            f'<span>{escape(label)}</span></a>'
        )
    return '<div class="fiscal-source-list">' + "".join(links) + "</div>"


@st.cache_data(ttl=900, show_spinner=False)
def _load_occupancy_snapshot():
    """Load the team's tracked monthly occupancy handoff used by the planner."""
    frame = pd.read_csv(OCCUPANCY_SNAPSHOT, parse_dates=["month_start"])
    required = {"month_start", "available_rooms", "occupancy_rate", "capacity_days"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Monthly occupancy snapshot is missing required fields")
    complete = frame[
        frame["month_start"].dt.year.eq(2025)
        & frame["capacity_days"].ge(frame["month_start"].dt.days_in_month)
    ].copy()
    if len(complete) != 12 or complete[list(required - {"month_start"})].isna().any().any():
        raise ValueError("Monthly occupancy snapshot does not contain 12 complete 2025 months")
    return complete.sort_values("month_start").reset_index(drop=True)


def _monthly_occupancy_context(occupancy, month_number):
    """Return relative demand pressure without treating sensor averages as inventory."""
    selected = occupancy[occupancy["month_start"].dt.month.eq(month_number)]
    if selected.empty:
        raise ValueError("Selected month has no complete 2025 occupancy baseline")
    annual_rate = float(
        (occupancy["occupancy_rate"] * occupancy["capacity_days"]).sum()
        / occupancy["capacity_days"].sum()
    )
    selected_rate = float(selected.iloc[0]["occupancy_rate"])
    return {
        "occupancy_rate": selected_rate,
        "annual_rate": annual_rate,
        "pressure_index": selected_rate / annual_rate,
        "available_rooms_observation": float(selected.iloc[0]["available_rooms"]),
    }


def _monthly_fiscal_index(monthly, month_number):
    """Revenue index for a complete 2025 month, weighted to the source records."""
    complete = _complete_2025_months(monthly)
    annual_revenue = float(
        (complete["revenue"] * complete["observations"]).sum()
        / complete["observations"].sum()
    )
    selected = complete[complete["month"] == f"2025-{month_number:02d}"]
    if selected.empty:
        raise ValueError("Selected month has no complete 2025 fiscal baseline")
    return float(selected.iloc[0]["revenue"] / annual_revenue)


def _combined_event_impact(attendees, duration, scenario, fiscal_index, facility_allowance=None):
    """Combine a fiscal seasonality proxy with separately scoped event assumptions."""
    assumptions = EVENT_SCENARIOS[scenario]
    overnight_visitors = round(attendees * assumptions["visitor_fraction"])
    rooms_per_night = ceil(overnight_visitors / assumptions["people_per_room"])
    room_nights = rooms_per_night * duration
    hotel_spending = room_nights * NYC_2025_HOTEL_ADR
    baseline_nonhotel = overnight_visitors * duration * assumptions["nonhotel_spend"]
    indexed_nonhotel = baseline_nonhotel * fiscal_index
    visitor_activity = hotel_spending + indexed_nonhotel
    hotel_taxes_fees = hotel_spending * NYC_HOTEL_PERCENT_TAX + room_nights * NYC_HOTEL_FLAT_FEES
    nonhotel_sales_tax = indexed_nonhotel * .08875
    venue_cost = assumptions["facility_allowance"] if facility_allowance is None else facility_allowance
    service_cost = attendees * duration * assumptions["service_cost"]
    lodging_total = hotel_spending + hotel_taxes_fees
    organizer_cost = venue_cost + service_cost
    return assumptions | {
        "overnight_visitors": overnight_visitors,
        "rooms_per_night": rooms_per_night,
        "room_nights": room_nights,
        "hotel_spending": hotel_spending,
        "lodging_total": lodging_total,
        "baseline_nonhotel": baseline_nonhotel,
        "indexed_nonhotel": indexed_nonhotel,
        "visitor_activity": visitor_activity,
        "locally_retained_activity": visitor_activity * assumptions["local_retention"],
        "taxes_fees": hotel_taxes_fees + nonhotel_sales_tax,
        "hotel_taxes_fees": hotel_taxes_fees,
        "venue_cost": venue_cost,
        "event_service_total": service_cost,
        "organizer_cost": organizer_cost,
        "organizer_cost_per_attendee": organizer_cost / attendees,
        "fiscal_index": fiscal_index,
    }


def _kpi_html(label, value, sub):
    return (
        f'<div class="fiscal-kpi"><div class="fiscal-kpi-label">{escape(label)}</div>'
        f'<div class="fiscal-kpi-value">{escape(str(value))}</div>'
        f'<div class="fiscal-kpi-sub">{sub}</div></div>'
    )


def _kpi_row(kpis):
    """kpis: list of (label, value, sub_html) — sub_html is inserted unescaped
    (so callers can bold/link within it), label/value are escaped."""
    st.markdown('<div class="fiscal-kpi-row">', unsafe_allow_html=True)
    for col, (label, value, sub) in zip(st.columns(len(kpis)), kpis):
        with col:
            st.markdown(_kpi_html(label, value, sub), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _complete_2025_months(monthly):
    """Return the comparable full calendar-year rows used for ranks and charts."""
    return monthly[
        monthly["complete_month"] & monthly["month"].str.startswith("2025-")
    ].copy()


def _monthly_revenue_chart(monthly):
    """Show the complete 2025 revenue cycle without privileging a planning month."""
    complete = _complete_2025_months(monthly)
    max_value = complete["revenue"].max()
    peak_month = complete.loc[complete["revenue"].idxmax(), "month"]
    low_month = complete.loc[complete["revenue"].idxmin(), "month"]
    rows = []
    for row in complete.itertuples():
        month_name = datetime.strptime(row.month, "%Y-%m").strftime("%b")
        marker = "peak" if row.month == peak_month else "low" if row.month == low_month else ""
        width = 100 * row.revenue / max_value if max_value else 0
        note = "Annual peak" if marker == "peak" else "Annual low" if marker == "low" else ""
        rows.append(
            f'<div class="fiscal-month-row {marker}">'
            f'<span class="fiscal-month-label">{month_name}</span>'
            '<div class="fiscal-month-track">'
            f'<div class="fiscal-month-fill" style="width:{width:.1f}%"></div></div>'
            f'<strong>{_fmt_units(row.revenue)}</strong>'
            f'<em>{note}</em></div>'
        )
    st.markdown('<div class="fiscal-month-chart">' + "".join(rows) + "</div>", unsafe_allow_html=True)


def _section(icon_title, note=None):
    st.markdown(f'<div class="fiscal-section-title">{icon_title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="fiscal-section-note">{note}</div>', unsafe_allow_html=True)


def _explorer_summary(daily_indexed, start, duration):
    """Return like-for-like historical fiscal analogues for a proposed window."""
    end = start + timedelta(days=duration - 1)
    _, summary = calendar_analogues(
        daily_indexed,
        event_start=start,
        event_end=end,
        candidate_start=start,
        candidate_end=end,
    )
    return summary.set_index("metric")


def _render_date_explorer(daily_indexed, monthly, occupancy):
    """Combine instructor-data seasonality with transparent event assumptions."""
    _section(
        "📅 Seasonally indexed event explorer",
        "Combine the instructor-provided monthly revenue pattern with sourced NYC rates and explicit event assumptions.",
    )
    with st.container(key="fiscal_explorer"):
        st.markdown(
            '<div class="fiscal-explorer-intro"><strong>Jacob K. Javits Convention Center · New York City</strong>'
            '<span>The selected month changes the fiscal index and variable visitor activity. Hotel and '
            'organizer costs remain separate planning assumptions.</span></div>',
            unsafe_allow_html=True,
        )
        col1, col2, col3, col4 = st.columns([1.4, 1, 1.2, 1])
        with col1:
            start = st.date_input(
                "Event start", value=DEFAULT_EVENT_START,
                min_value=date(2027, 1, 1), max_value=date(2027, 12, 31),
                key="fiscal_explorer_start",
            )
        with col2:
            max_duration = _max_same_month_duration(start)
            if st.session_state.get("fiscal_explorer_duration", 3) > max_duration:
                st.session_state["fiscal_explorer_duration"] = max_duration
            duration = st.slider(
                "Event length", 1, max_duration, min(3, max_duration),
                format="%d day(s)", key="fiscal_explorer_duration",
            )
        with col3:
            scenario = st.selectbox(
                "Scenario", list(EVENT_SCENARIOS), index=1, key="fiscal_explorer_scenario",
            )
        with col4:
            attendees = st.number_input(
                "Attendees", min_value=1_000, max_value=50_000, value=15_000,
                step=500, key="fiscal_explorer_attendees",
            )
        scenario_allowance = EVENT_SCENARIOS[scenario]["facility_allowance"]
        if st.session_state.get("fiscal_last_scenario") != scenario:
            st.session_state["fiscal_venue_allowance"] = scenario_allowance
            st.session_state["fiscal_last_scenario"] = scenario
        facility_allowance = st.number_input(
            "Javits proposal / planning allowance",
            min_value=0,
            max_value=5_000_000,
            step=25_000,
            key="fiscal_venue_allowance",
            help="Starts at the selected scenario allowance. Replace it with a custom Javits proposal when available.",
        )
        if max_duration < 7:
            st.caption(
                f"Duration is limited to {max_duration} day(s) so the historical analogue and monthly "
                "fiscal index remain within {start.strftime('%B')}."
            )
    end = start + timedelta(days=duration - 1)
    weekday_span = start.strftime("%A") if duration == 1 else f"{start.strftime('%A')}–{end.strftime('%A')}"

    try:
        summary = _explorer_summary(daily_indexed, start, duration)
        fiscal_index = _monthly_fiscal_index(monthly, start.month)
        occupancy_context = _monthly_occupancy_context(occupancy, start.month)
    except ValueError as exc:
        st.warning(f"⚠️ {exc} — try a different date.")
        return

    revenue = summary.loc["revenue"]
    expense = summary.loc["expense"]
    net = summary.loc["net_per_observation"]
    impact = _combined_event_impact(
        attendees, duration, scenario, fiscal_index, facility_allowance=facility_allowance,
    )
    st.markdown(
        f'<div class="fiscal-test-summary"><span>TESTING</span><strong>{_planner_range_label(start, end)}</strong>'
        f'<p>{weekday_span} · {scenario} scenario · {attendees:,} attendees · '
        f'{start.strftime("%B")} fiscal index {fiscal_index:.2f} · '
        f'occupancy pressure {occupancy_context["pressure_index"]:.2f}</p></div>',
        unsafe_allow_html=True,
    )

    _kpi_row([
        ("Potential visitor activity", _fmt_money(impact["visitor_activity"]), "Lodging + indexed non-hotel spending"),
        ("Attendee lodging bill", _fmt_money(impact["lodging_total"]), "Room charges + hotel taxes and fees"),
        ("Organizer planning cost", _fmt_money(impact["organizer_cost"]), f'{_fmt_money(impact["organizer_cost_per_attendee"])} per attendee'),
        ("Estimated taxes & fees", _fmt_money(impact["taxes_fees"]), "Hotel taxes/fees + provisional sales tax"),
    ])
    st.markdown(
        '<div class="fiscal-impact-breakdown">'
        f'<div><span>Hotel spending</span><strong>{_fmt_money(impact["hotel_spending"])}</strong></div>'
        f'<div><span>Indexed non-hotel spending</span><strong>{_fmt_money(impact["indexed_nonhotel"])}</strong></div>'
        f'<div><span>Venue + event services</span><strong>{_fmt_money(impact["organizer_cost"])}</strong></div>'
        f'<div><span>Hotel demand</span><strong>{impact["rooms_per_night"]:,} rooms/night</strong></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    index_delta = 100 * (fiscal_index - 1)
    direction = "above" if index_delta >= 0 else "below"
    st.markdown(
        f'<div class="fiscal-comparison-result"><strong>{abs(index_delta):.0f}% {direction} the annual revenue '
        f'baseline:</strong> {_fmt_money(impact["baseline_nonhotel"])} in unadjusted non-hotel spending becomes '
        f'{_fmt_money(impact["indexed_nonhotel"])} after applying the {start.strftime("%B")} fiscal index.</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Underlying historical analogue: revenue {_fmt_units(revenue['mean'])}, expense "
        f"{_fmt_units(expense['mean'])}, and net {_fmt_units(net['mean'])} per record across "
        f"{int(net['analogue_windows'])} matching {start.strftime('%B')} 2025 sequences."
    )
    pressure_delta = 100 * (occupancy_context["pressure_index"] - 1)
    pressure_direction = "above" if pressure_delta >= 0 else "below"
    st.markdown(
        f'<div class="fiscal-evidence-note"><strong>Occupancy context:</strong> '
        f'{start.strftime("%B")} historical occupancy is {occupancy_context["occupancy_rate"]:.1f}%, '
        f'{abs(pressure_delta):.0f}% {pressure_direction} the 2025 average of '
        f'{occupancy_context["annual_rate"]:.1f}%. This signals relative demand pressure; it does not '
        'change the published ADR or prove citywide room availability.</div>',
        unsafe_allow_html=True,
    )

    weekend_days = sum(1 for i in range(duration) if (start + timedelta(days=i)).weekday() >= 5)
    if weekend_days:
        st.caption(
            f"⚠️ This window includes {weekend_days} weekend day(s) — the generator applies a 15% weekend "
            "revenue premium, so higher revenue here partly reflects that, not just the date choice."
        )
    with st.expander("Full assumptions, rates, and calculation method"):
        st.markdown(
            f"**Selected scenario**\n\n"
            f"- Attendees: **{attendees:,}**\n"
            f"- Event duration: **{duration} day(s)**\n"
            f"- Overnight visitor share: **{impact['visitor_fraction']:.0%}**\n"
            f"- Guests per room: **{impact['people_per_room']:.1f}**\n"
            f"- Non-hotel spending: **{_fmt_money(impact['nonhotel_spend'])} per overnight visitor/day**\n"
            f"- Local retention assumption: **{impact['local_retention']:.0%}**\n"
            f"- Javits proposal / allowance: **{_fmt_money(impact['venue_cost'])}**\n"
            f"- Event services: **{_fmt_money(impact['service_cost'])} per attendee/day**\n\n"
            f"**Occupancy context**\n\n"
            f"- Selected-month occupancy: **{occupancy_context['occupancy_rate']:.1f}%**\n"
            f"- 2025 average occupancy: **{occupancy_context['annual_rate']:.1f}%**\n"
            f"- Relative occupancy-pressure index: **{occupancy_context['pressure_index']:.2f}**\n"
            "- The dataset's available-room value is an average synthetic observation, not citywide inventory.\n\n"
            f"**Published rates and provisional tax treatment**\n\n"
            f"- NYC 2025 hotel ADR: **${NYC_2025_HOTEL_ADR:,.2f} per room-night**\n"
            f"- Hotel percentage taxes: **{NYC_HOTEL_PERCENT_TAX:.2%}**\n"
            f"- Hotel flat fees: **${NYC_HOTEL_FLAT_FEES:.2f} per room-night**\n"
            "- Provisional non-hotel sales tax: **8.875%**\n\n"
            "**Method**\n\n"
            "The monthly fiscal index equals that month's average instructor-data revenue divided by the "
            "observation-weighted 2025 average. It adjusts only non-hotel visitor spending. Hotel spending, "
            "facility allowances, and service costs are not multiplied by the index. Occupancy is shown as "
            "context rather than converted into an unsupported room-price formula."
        )
        st.warning(
            "Potential visitor activity is a transparent proxy scenario, not measured convention impact, "
            "a forecast, a vendor quote, city profit, or guaranteed tax revenue. Facility and service "
            "allowances are authored assumptions pending an event-specific Javits proposal."
        )
        st.markdown("**🔗 Sources and scope**")
        st.markdown(_source_list_html(), unsafe_allow_html=True)
        st.caption(
            "Rates and tax rules must be rechecked when budgeting. Exemptions, negotiated group rates, "
            "seasonality, room type, and contract terms can materially change actual cost."
        )


def render_fiscal_impact():
    st.markdown(f"<style>{read_css(STYLES_PATH, section='fiscal_impact')}</style>", unsafe_allow_html=True)

    try:
        data = _load_run()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        st.title("💰 Fiscal Impact")
        st.error(f"The latest fiscal analysis run could not be verified: {exc}")
        return
    if data is None:
        st.title("💰 Fiscal Impact")
        st.info(
            "No packaged fiscal analysis snapshot was found under "
            "dashboard/data/fiscal_analysis/. See docs/fiscal_analysis.md."
        )
        return

    try:
        occupancy = _load_occupancy_snapshot()
    except (OSError, ValueError) as exc:
        st.title("💰 Fiscal Impact")
        st.error(f"The shared occupancy snapshot could not be loaded: {exc}")
        return

    manifest, monthly = data["manifest"], data["monthly"]
    run_dir, daily_indexed = data["run_dir"], data["daily"]
    complete = _complete_2025_months(monthly)
    complete_month_count = len(complete)
    complete_record_count = int(complete["observations"].sum())
    peak = complete.loc[complete["revenue"].idxmax()]
    revenue_rise = 100 * (peak["revenue"] - complete.iloc[0]["revenue"]) / complete.iloc[0]["revenue"]
    revenue_cooling = 100 * (peak["revenue"] - complete.iloc[-1]["revenue"]) / peak["revenue"]

    # --- Hero ---
    with st.container(key="fiscal_hero"):
        # Large hero banner image removed (2026-09-19): redundant with the shared image-backed navigation header. Text/chart below untouched.
        st.markdown('<span class="fiscal-eyebrow">FISCAL IMPACT · HISTORICAL PROFILE</span>', unsafe_allow_html=True)
        st.markdown("<h1>Fiscal activity builds toward summer, then cools through year-end</h1>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="fiscal-hero-summary">A neutral view of <strong>{complete_month_count} complete '
            f'months</strong> and <strong>{complete_record_count:,} fiscal records</strong> from the shared '
            'instructor dataset.</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="fiscal-chart-title">2025 monthly revenue pattern</div>', unsafe_allow_html=True)
        _monthly_revenue_chart(monthly)
        st.markdown(
            '<div class="fiscal-data-note">Monthly average revenue per record · instructor-provided '
            'synthetic fiscal data · source currency and accounting grain unconfirmed.</div>',
            unsafe_allow_html=True,
        )

    _section(
        "📈 Trend and fiscal periodicity",
        "The year forms a clear single-cycle arc in revenue and net values. Expenses remain comparatively stable.",
    )
    st.markdown(
        '<div class="fiscal-takeaway-grid">'
        f'<div><span>01 · EXPANSION</span><strong>January to June: +{revenue_rise:.0f}%</strong>'
        '<p>Average revenue climbs steadily through the first half of the year.</p></div>'
        f'<div><span>02 · PEAK</span><strong>{_month_label(peak["month"])} leads the year</strong>'
        f'<p>Revenue reaches {_fmt_units(peak["revenue"])} and net reaches '
        f'{_fmt_units(peak["net_per_observation"])} per record.</p></div>'
        f'<div><span>03 · COOLING</span><strong>June to December: −{revenue_cooling:.0f}%</strong>'
        '<p>Revenue retreats through the second half and returns near winter levels.</p></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="fiscal-callout info"><strong>Periodicity signal, not a proven annual cycle:</strong> '
        'the rise-and-fall pattern is strong within 2025, but the dataset contains only one complete year. '
        'Multiple complete years are required to establish that this seasonality reliably repeats.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("See the complete monthly fiscal table"):
        table = complete[["month", "revenue", "expense", "net_per_observation"]].copy()
        table["month"] = table["month"].map(_month_label)
        table = table.rename(columns={
            "month": "Month", "revenue": "Revenue / record", "expense": "Expense / record",
            "net_per_observation": "Net / record",
        })
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            column: st.column_config.NumberColumn(format="%.2f")
            for column in ("Revenue / record", "Expense / record", "Net / record")
        })

    _render_date_explorer(daily_indexed, monthly, occupancy)

    _section("🔎 What the fiscal data establishes")
    st.markdown(
        '<div class="fiscal-takeaway-grid">'
        '<div><span>01</span><strong>Revenue drives the annual movement</strong><p>Monthly expenses vary much '
        'less than revenue, so net values largely follow the revenue curve.</p></div>'
        '<div><span>02</span><strong>Summer is historically stronger</strong><p>June records the highest '
        'average revenue and net in the complete 2025 data.</p></div>'
        '<div><span>03</span><strong>Impact remains descriptive</strong><p>The data does not identify currency, '
        'citywide totals, event causality, or future convention impact.</p></div></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Technical findings and interpretation notes"):
        st.markdown(
            "- One complete year supports within-year comparison but cannot confirm repeating annual seasonality.\n"
            "- Revenue and expense correlate at 0.61 across records but approximately 0.00 across daily means.\n"
            "- Expense exceeds revenue in 13% of individual synthetic records.\n"
            "- The source does not establish currency, accounting period, or whether values are flows or snapshots."
        )

    # --- Limitations ---
    st.markdown(
        '<div class="fiscal-callout warn">⚠️ <strong>Planning context, not budget approval:</strong> '
        'these synthetic historical comparisons do not establish causal impact, '
        'future performance, tax revenue, or city profit.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("What must be confirmed before a funding decision"):
        st.markdown(
            "- Currency, accounting period, and the entity represented by each fiscal record\n"
            "- Actual venue and hotel quotes, organizer income, and organizer budget\n"
            "- Attendee definition, overnight share, lodging nights, and displaced normal activity\n"
            "- Capacity, traffic, air-quality, and weather findings from their owning team analyses"
        )

    st.markdown(
        f'<div class="fiscal-footer">Source: notebooks/Hakeem_fiscal_analysis.ipynb, run <code>{escape(run_dir.name)}</code> · '
        f"docs/fiscal_analysis.md · claim scope: {escape(manifest.get('claim_scope', ''))}</div>",
        unsafe_allow_html=True,
    )
