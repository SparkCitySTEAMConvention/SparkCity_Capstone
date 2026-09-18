"""Fiscal Impact page.

Tells the fiscal half of "why April 6-8, 2027": why Feb/April were even in
contention, what the historical fiscal data actually shows favoring April over
February, where fiscal data goes quiet (the specific week/day was mostly a
capacity/operations call, not a fiscal-maximization one), and what the event's
modeled financial impact looks like. Renders the pinned, hash-verified output of
`notebooks/Hakeem_fiscal_analysis.ipynb` (see docs/fiscal_analysis.md) plus a
"try another date" explorer that runs the same audited methodology live.

This module formats numbers that already exist in
`data/processed/fiscal_analysis/<run>/`, or recomputes them via the same audited
`sparkcityx.fiscal_analysis.calendar_analogues` function used by that notebook —
it does not invent a separate calculation to make a different date look better or
worse. Where the analysis's own findings.md hedges a claim (synthetic data, no
causal/optimality claim, one complete historical April), that hedge is carried
onto the page rather than dropped for a cleaner story: the fiscal data does not
prove April 6-8 is the single best date, and this page says so, alongside what
it does show.
"""
import json
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import escape
from math import ceil
from pathlib import Path

import pandas as pd
import streamlit as st

from components.shared import STYLES_PATH, load_css, read_css
from sparkcityx.fiscal_analysis import MEASURES, calendar_analogues

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FISCAL_RUNS_DIR = PROJECT_ROOT / "data" / "processed" / "fiscal_analysis"
FISCAL_HERO_IMAGE = PROJECT_ROOT / "dashboard" / "assets" / "domains" / "fiscal_impact.png"

# Kept as a live safety check, not a display fact: if the pinned notebook run's
# dates ever drift from the team's agreed dates again, the page should say so
# instead of silently presenting stale numbers as current.
TEAM_PROPOSED_DATES = ("2027-04-06", "2027-04-08")

METRIC_LABELS = {"revenue": "Average revenue / record", "expense": "Average expense / record",
                  "net_per_observation": "Average net / record"}

JAVITS_SCENARIOS = {
    "Conservative": {
        "visitor_fraction": .40, "people_per_room": 2.3, "hotel_adr": 301,
        "nonhotel_spend": 40, "local_retention": .50, "facility_allowance": 300_000,
        "service_cost": 20,
    },
    "Planning": {
        "visitor_fraction": .65, "people_per_room": 1.8, "hotel_adr": 354,
        "nonhotel_spend": 90, "local_retention": .75, "facility_allowance": 500_000,
        "service_cost": 35,
    },
    "High activity": {
        "visitor_fraction": .85, "people_per_room": 1.3, "hotel_adr": 425,
        "nonhotel_spend": 160, "local_retention": .90, "facility_allowance": 800_000,
        "service_cost": 70,
    },
}


def _month_label(month):
    """Format e.g. "2025-06" as "June 2025"; falls back to the raw string if unparseable."""
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


def _date_label(value):
    """Format an ISO date for planner-facing copy; preserve unknown values."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    except (TypeError, ValueError):
        return str(value)


def _date_range_label(start, end):
    """Compact same-month ranges, with a readable fallback for other ranges."""
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
    except (TypeError, ValueError):
        return f"{_date_label(start)} – {_date_label(end)}"
    if (start_date.year, start_date.month) == (end_date.year, end_date.month):
        return f"{start_date.strftime('%B')} {start_date.day}–{end_date.day}, {start_date.year}"
    return f"{_date_label(start)} – {_date_label(end)}"


def _planner_range_label(start, end):
    """Format date objects compactly, including ranges that cross a month."""
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.strftime('%B')} {start.day}–{end.day}, {start.year}"
    return f"{start.strftime('%B')} {start.day} – {end.strftime('%B')} {end.day}, {end.year}"


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


@lru_cache(maxsize=1)
def _load_run():
    run_dir = _latest_complete_run_in(FISCAL_RUNS_DIR)
    if run_dir is None:
        return None
    return {
        "run_dir": run_dir,
        "manifest": json.loads((run_dir / "manifest.json").read_text()),
        "findings": (run_dir / "findings.md").read_text(),
        "monthly": pd.read_csv(run_dir / "monthly.csv"),
        "candidates": pd.read_csv(run_dir / "candidate_summary.csv"),
        "daily": pd.read_csv(run_dir / "daily.csv", parse_dates=["day"]).set_index("day"),
    }


def _fmt_units(value):
    return f"{value:,.2f}"


def _fmt_money(value):
    return f"${value:,.0f}"


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


def _bar_row(tag, value, max_value, fill_color):
    pct = max(6, round(100 * value / max_value)) if max_value else 0
    return (
        '<div class="fiscal-bar-row">'
        f'<span class="fiscal-bar-tag">{escape(tag)}</span>'
        '<div class="fiscal-bar-track">'
        f'<div class="fiscal-bar-fill" style="width:{pct}%;background:{fill_color};">{_fmt_units(value)}</div>'
        "</div></div>"
    )


def _monthly_net_chart(monthly):
    """Compact dashboard-native comparison; source PNG remains in the run artifacts."""
    complete = monthly[monthly["complete_month"] & monthly["month"].str.startswith("2025-")].copy()
    max_value = complete["net_per_observation"].max()
    rows = []
    for row in complete.itertuples():
        month_name = datetime.strptime(row.month, "%Y-%m").strftime("%b")
        selected = row.month == "2025-04"
        width = 100 * row.net_per_observation / max_value if max_value else 0
        rows.append(
            f'<div class="fiscal-month-row{" selected" if selected else ""}">'
            f'<span class="fiscal-month-label">{month_name}</span>'
            '<div class="fiscal-month-track">'
            f'<div class="fiscal-month-fill" style="width:{width:.1f}%"></div></div>'
            f'<strong>{_fmt_units(row.net_per_observation)}</strong>'
            f'{"<em>Selected month</em>" if selected else ""}</div>'
        )
    st.markdown('<div class="fiscal-month-chart">' + "".join(rows) + "</div>", unsafe_allow_html=True)


def _candidate_range_chart(net_rows):
    """Show candidate means and historical min–max ranges without a dense static plot."""
    chart_min = float(net_rows["minimum"].min())
    chart_max = float(net_rows["maximum"].max())
    span = chart_max - chart_min or 1
    rows = []
    for row in net_rows.itertuples():
        start = datetime.strptime(row.candidate_start, "%Y-%m-%d")
        end = datetime.strptime(row.candidate_end, "%Y-%m-%d")
        left = 100 * (row.minimum - chart_min) / span
        width = 100 * (row.maximum - row.minimum) / span
        mean = 100 * (row.mean - chart_min) / span
        label = f"{start.strftime('%b')} {start.day}–{end.day}"
        rows.append(
            f'<div class="fiscal-range-row{" selected" if row.selected else ""}">'
            f'<div class="fiscal-range-label"><strong>{label}</strong>'
            f'<span>{"Recommended" if row.selected else start.strftime("%a") + " start"}</span></div>'
            '<div class="fiscal-range-track">'
            f'<div class="fiscal-range-line" style="left:{left:.1f}%;width:{width:.1f}%"></div>'
            f'<div class="fiscal-range-dot" style="left:{mean:.1f}%"></div></div>'
            f'<div class="fiscal-range-value"><strong>{_fmt_units(row.mean)}</strong><span>mean net/record</span></div>'
            '</div>'
        )
    st.markdown(
        '<div class="fiscal-range-chart">' + "".join(rows) +
        f'<div class="fiscal-range-axis"><span>{_fmt_units(chart_min)}</span>'
        f'<span>Historical range</span><span>{_fmt_units(chart_max)}</span></div></div>',
        unsafe_allow_html=True,
    )


def _section(icon_title, note=None):
    st.markdown(f'<div class="fiscal-section-title">{icon_title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="fiscal-section-note">{note}</div>', unsafe_allow_html=True)


def _javits_impact(attendees, duration, scenario):
    """Deterministic, transparent planning arithmetic for one named scenario."""
    assumptions = JAVITS_SCENARIOS[scenario]
    overnight_visitors = round(attendees * assumptions["visitor_fraction"])
    rooms_per_night = ceil(overnight_visitors / assumptions["people_per_room"])
    room_nights = rooms_per_night * duration
    hotel_spending = room_nights * assumptions["hotel_adr"]
    nonhotel_spending = overnight_visitors * duration * assumptions["nonhotel_spend"]
    gross_spending = hotel_spending + nonhotel_spending
    retained_spending = gross_spending * assumptions["local_retention"]
    organizer_cost = assumptions["facility_allowance"] + attendees * duration * assumptions["service_cost"]
    # Planning estimate: current combined NYC hotel taxes plus state unit fee;
    # assumes all non-hotel visitor spending is subject to the combined sales tax.
    hotel_taxes_fees = hotel_spending * .1475 + room_nights * 3.50
    nonhotel_sales_tax = nonhotel_spending * .08875
    return assumptions | {
        "overnight_visitors": overnight_visitors, "rooms_per_night": rooms_per_night,
        "room_nights": room_nights, "hotel_spending": hotel_spending,
        "nonhotel_spending": nonhotel_spending, "gross_spending": gross_spending,
        "retained_spending": retained_spending, "organizer_cost": organizer_cost,
        "taxes_fees": hotel_taxes_fees + nonhotel_sales_tax,
    }


def _render_date_explorer(daily_indexed, pinned_net, attendees):
    """Interactive Javits planning scenario plus historical fiscal context."""
    _section(
        "🏙️ Javits fiscal scenario explorer",
        "Test how event timing, duration, and planning assumptions change the estimated economic footprint.",
    )
    with st.container(key="fiscal_explorer"):
        st.markdown(
            '<div class="fiscal-explorer-intro"><strong>Jacob K. Javits Convention Center · New York City</strong>'
            '<span>Choose a date, duration, and scenario. Dollar outputs are planning estimates—not quotes '
            'or guaranteed economic impact.</span></div>',
            unsafe_allow_html=True,
        )
        col1, col2, col3 = st.columns([1.5, 1, 1.2])
        with col1:
            start = st.date_input(
                "Event start", value=date(2027, 4, 6),
                min_value=date(2027, 1, 1), max_value=date(2027, 12, 31),
                key="fiscal_explorer_start",
            )
        with col2:
            duration = st.slider("Event length", 1, 7, 3, format="%d day(s)", key="fiscal_explorer_duration")
        with col3:
            scenario = st.selectbox(
                "Scenario", list(JAVITS_SCENARIOS), index=1, key="fiscal_explorer_scenario",
                help="Conservative, planning, and high-activity cases use explicit assumption sets.",
            )
    end = start + timedelta(days=duration - 1)
    weekday_span = start.strftime("%A") if duration == 1 else f"{start.strftime('%A')}–{end.strftime('%A')}"
    impact = _javits_impact(attendees, duration, scenario)
    st.markdown(
        f'<div class="fiscal-test-summary"><span>TESTING</span><strong>{_planner_range_label(start, end)}</strong>'
        f'<p>{weekday_span} · {scenario} scenario · {attendees:,} attendees</p></div>',
        unsafe_allow_html=True,
    )

    _kpi_row([
        ("Visitor spending", _fmt_money(impact["gross_spending"]), "Hotel + non-hotel spending"),
        ("Organizer budget", _fmt_money(impact["organizer_cost"]), "Facility + event-service allowance"),
        ("Taxes & fees", _fmt_money(impact["taxes_fees"]), "Estimated hotel and sales taxes/fees"),
        ("Hotel demand", f'{impact["rooms_per_night"]:,}', "Rooms per night"),
    ])
    hotel_share = 100 * impact["hotel_spending"] / impact["gross_spending"] if impact["gross_spending"] else 0
    st.markdown(
        '<div class="fiscal-impact-breakdown">'
        f'<div><span>Hotel spending</span><strong>{_fmt_money(impact["hotel_spending"])}</strong></div>'
        f'<div><span>Other visitor spending</span><strong>{_fmt_money(impact["nonhotel_spending"])}</strong></div>'
        f'<div><span>Locally retained activity</span><strong>{_fmt_money(impact["retained_spending"])}</strong></div>'
        f'<div><span>Room nights</span><strong>{impact["room_nights"]:,}</strong></div>'
        f'<div class="fiscal-spend-bar"><i style="width:{hotel_share:.1f}%"></i></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Scenario assumptions"):
        st.markdown(
            f"- **Overnight visitor share:** {impact['visitor_fraction']:.0%}\n"
            f"- **Guests per room:** {impact['people_per_room']:.1f}\n"
            f"- **Hotel rate:** {_fmt_money(impact['hotel_adr'])} per night\n"
            f"- **Other visitor spending:** {_fmt_money(impact['nonhotel_spend'])} per visitor/day\n"
            f"- **Javits facility allowance:** {_fmt_money(impact['facility_allowance'])}\n"
            f"- **Event services:** {_fmt_money(impact['service_cost'])} per attendee/day\n"
            f"- **Local retention:** {impact['local_retention']:.0%}"
        )
        st.caption(
            "The planning hotel rate updates NYC's $334 2025 average by approximately 3% annually to "
            "2027. The facility amount is an authored allowance pending a Javits proposal; it is not a quote."
        )
        st.markdown(
            "Sources: [NYC Tourism 2025 hotel performance]"
            "(https://business.nyctourism.com/fr/press-media/press-releases/NYC-Tourism-Annual-Report-March-2026) "
            "· [Javits event planning and facility details](https://www.javitscenter.com/plan) "
            "· [NYC hotel occupancy tax](https://www.nyc.gov/site/finance/business/business-hotel-room-occupancy-tax.page)"
        )

    st.markdown('<div class="fiscal-subheading">Historical date context</div>', unsafe_allow_html=True)
    st.caption(
        f"For context only: matching {start.strftime('%B')} 2025 weekday sequences are summarized below. "
        "This historical synthetic series does not drive the dollar estimates above."
    )

    try:
        _, summary = calendar_analogues(
            daily_indexed, event_start=start, event_end=end, candidate_start=start, candidate_end=end,
        )
    except ValueError as exc:
        st.warning(f"⚠️ {exc} — try a different date.")
        return

    cols = st.columns(3)
    net_mean = None
    for col, metric in zip(cols, MEASURES):
        row = summary[summary["metric"] == metric].iloc[0]
        if metric == "net_per_observation":
            net_mean = row["mean"]
        with col:
            st.markdown(
                _kpi_html(
                    METRIC_LABELS[metric], _fmt_units(row["mean"]),
                    f"Range {_fmt_units(row['minimum'])}–{_fmt_units(row['maximum'])} across "
                    f"{int(row['analogue_windows'])} historical matches",
                ),
                unsafe_allow_html=True,
            )

    if net_mean is not None and pinned_net:
        delta = 100 * (net_mean - pinned_net) / pinned_net
        direction = "higher than" if delta >= 0 else "lower than"
        st.markdown(
            f'<div class="fiscal-comparison-result"><strong>{abs(delta):.0f}% {direction}</strong> '
            f'the recommended window’s historical net/record benchmark ({_fmt_units(pinned_net)}).</div>',
            unsafe_allow_html=True,
        )

    weekend_days = sum(1 for i in range(duration) if (start + timedelta(days=i)).weekday() >= 5)
    if weekend_days:
        st.caption(
            f"⚠️ This window includes {weekend_days} weekend day(s) — the generator applies a 15% weekend "
            "revenue premium, so higher revenue here partly reflects that, not just the date choice."
        )
    with st.expander("Method, tax treatment, and important limits"):
        st.write(
            "The hotel estimate uses a 14.75% combined hotel tax rate plus $3.50 in room fees per "
            "occupied room-night. Other visitor spending is provisionally treated as fully taxable at "
            "8.875%, which likely overstates collections because not every purchase is taxable. Tax rules, "
            "exemptions, and the 2027 rates must be reconfirmed. Historical matches use synthetic 2025 "
            "records and are not a 2027 forecast. Gross spending, organizer cost, and taxes belong to "
            "different accounting scopes and must not be netted into city profit."
        )


def render_fiscal_impact():
    load_css(section="shared")
    st.markdown(f"<style>{read_css(STYLES_PATH, section='fiscal_impact')}</style>", unsafe_allow_html=True)

    data = _load_run()
    if data is None:
        st.title("💰 Fiscal Impact")
        st.info(
            "No completed fiscal analysis run found under data/processed/fiscal_analysis/. "
            "Run notebooks/Hakeem_fiscal_analysis.ipynb first (see docs/fiscal_analysis.md)."
        )
        return

    manifest, monthly = data["manifest"], data["monthly"]
    candidates, run_dir, daily_indexed = data["candidates"], data["run_dir"], data["daily"]

    event_start, event_end = manifest.get("event_start"), manifest.get("event_end")
    attendees = manifest.get("attendees")
    pinned_window_label = f"{event_start} – {event_end}"
    display_window_label = _date_range_label(event_start, event_end)

    # --- Hero ---
    with st.container(key="fiscal_hero"):
        st.markdown('<span class="fiscal-eyebrow">FISCAL IMPACT · THE DECISION, IN THE DATA</span>', unsafe_allow_html=True)
        st.markdown("<h1>April is the stronger fiscal choice—but fiscal data does not pick the exact week</h1>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="fiscal-hero-summary">Recommended window: <strong>{escape(display_window_label)}</strong> '
            f'· approximately <strong>{attendees:,} attendees</strong></div>',
            unsafe_allow_html=True,
        )
        if FISCAL_HERO_IMAGE.exists():
            st.image(str(FISCAL_HERO_IMAGE), width="stretch")
        st.markdown(
            '<div class="fiscal-hero-takeaways">'
            '<div><span>WHAT THE DATA SUPPORTS</span><strong>April outperforms February</strong>'
            '<p>April is the stronger fiscal option among the two months with complete cross-domain coverage.</p></div>'
            '<div><span>WHAT IT DOES NOT PROVE</span><strong>April 6–8 is uniquely optimal</strong>'
            '<p>The exact week was selected mainly through capacity and operating conditions.</p></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="fiscal-data-note">Historical figures are synthetic source units per observation—'
            'not verified city revenue or a 2027 forecast.</div>',
            unsafe_allow_html=True,
        )

    team_start, team_end = TEAM_PROPOSED_DATES
    if (event_start, event_end) != (team_start, team_end):
        st.markdown(
            '<div class="fiscal-callout warn">⚠️ <strong>Date mismatch:</strong> '
            f"the team's agreed dates are <strong>{team_start} – {team_end}</strong>, "
            f"but this pinned fiscal run analyzes <strong>{pinned_window_label}</strong>. "
            "Re-run notebooks/Hakeem_fiscal_analysis.ipynb against the team's current dates "
            "before treating this page as current.</div>",
            unsafe_allow_html=True,
        )

    # --- April's historical baseline ---
    feb = monthly[monthly["month"] == "2025-02"].iloc[0]
    apr = monthly[monthly["month"] == "2025-04"].iloc[0]
    delta_pct = 100 * (apr["net_per_observation"] - feb["net_per_observation"]) / feb["net_per_observation"]
    best_month = monthly.loc[monthly["net_per_observation"].idxmax()]
    apr_rank = int((monthly["net_per_observation"] > apr["net_per_observation"]).sum()) + 1

    _section(
        "📊 April 2025 fiscal baseline",
        "Complete-month averages across 2,880 synthetic 15-minute records. These figures describe the "
        "historical month, not the proposed event dates or a citywide total.",
    )
    _kpi_row([
        ("Average revenue / record", _fmt_units(apr["revenue"]), "Synthetic source units"),
        ("Average expense / record", _fmt_units(apr["expense"]), "Synthetic source units"),
        ("Average net / record", _fmt_units(apr["net_per_observation"]), "Revenue minus expense"),
        ("2025 net ranking", f"#{apr_rank} of 12", f"{_month_label(best_month['month'])} ranks first"),
    ])
    st.markdown(
        f'<div class="fiscal-comparison-result"><strong>April’s average net is {delta_pct:.0f}% higher '
        f'than February’s</strong> ({_fmt_units(apr["net_per_observation"])} vs. '
        f'{_fmt_units(feb["net_per_observation"])} per record).</div>',
        unsafe_allow_html=True,
    )

    with st.expander("See all 12 months of 2025"):
        st.write(
            f"April is stronger than February, but it is not the annual peak. "
            f"**{_month_label(best_month['month'])}** ranks first at "
            f"{_fmt_units(best_month['net_per_observation'])} average net per record."
        )
        _monthly_net_chart(monthly)
        st.caption("Bars show average net per synthetic record. April is highlighted.")

    # --- Why this specific week within April ---
    net_rows = candidates[candidates["metric"] == "net_per_observation"].copy()
    net_rows["window"] = net_rows["candidate_start"] + " to " + net_rows["candidate_end"]
    highest = net_rows.loc[net_rows["mean"].idxmax()]
    pinned_row = net_rows[net_rows["selected"]].iloc[0]

    _section(
        "🗓️ Does fiscal data favor April 6–8?",
        "Not clearly. The five candidate windows have overlapping historical ranges, so their small "
        "differences should not be treated as a ranking of future performance.",
    )
    st.markdown(
        f'<div class="fiscal-verdict"><span>FISCAL VERDICT</span><strong>A sound option, not a unique winner</strong>'
        f'<p>The recommended window averages {_fmt_units(pinned_row["mean"])} net units per record. '
        f'The highest historical mean belongs to {escape(highest["candidate_start"])}–'
        f'{escape(highest["candidate_end"])} at {_fmt_units(highest["mean"])}; capacity and operations '
        'provide the stronger reason for choosing April 6–8.</p></div>',
        unsafe_allow_html=True,
    )
    _candidate_range_chart(net_rows)
    st.caption(
        "Dots are historical means; lines show the minimum-to-maximum range across four matching "
        "April 2025 sequences. They are not forecast intervals."
    )
    with st.expander("See the exact candidate values"):
        table = net_rows[["window", "selected", "analogue_windows", "mean", "minimum", "maximum"]].rename(columns={
            "window": "Window", "selected": "Recommended", "analogue_windows": "Historical matches",
            "mean": "Mean net/record", "minimum": "Minimum", "maximum": "Maximum",
        })
        for col in ("Mean net/record", "Minimum", "Maximum"):
            table[col] = table[col].map(_fmt_units)
        st.dataframe(table, hide_index=True, width="stretch")

    # --- Modular date explorer ---
    _render_date_explorer(daily_indexed, pinned_net=pinned_row["mean"], attendees=attendees)

    # --- Decision takeaways ---
    _section("🔑 What planners should take away")
    st.markdown(
        '<div class="fiscal-takeaway-grid">'
        f'<div><span>01</span><strong>April clears the fiscal comparison</strong><p>Average net per record is '
        f'{delta_pct:.0f}% higher than February.</p></div>'
        '<div><span>02</span><strong>Operations choose the week</strong><p>Fiscal differences among the five '
        'April windows are not decisive.</p></div>'
        '<div><span>03</span><strong>Validate before budgeting</strong><p>Currency, accounting meaning, and '
        'real venue costs still need confirmation.</p></div></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Technical findings and interpretation notes"):
        st.markdown(
            "- Only one complete historical April exists, so repeatable April seasonality is unconfirmed.\n"
            "- Revenue and expense correlate at 0.61 across records but approximately 0.00 across daily means.\n"
            "- Expense exceeds revenue in 13% of individual synthetic records.\n"
            "- The source does not establish currency, accounting period, or whether values are flows or snapshots."
        )

    # --- Limitations ---
    st.markdown(
        '<div class="fiscal-callout warn">⚠️ <strong>Planning context, not budget approval:</strong> '
        'these synthetic historical comparisons and authored scenarios do not establish causal impact, '
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
