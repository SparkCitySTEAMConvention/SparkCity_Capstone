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
        "scenarios": pd.read_csv(run_dir / "convention_financial_scenarios.csv"),
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


def _render_date_explorer(daily_indexed, pinned_net):
    """Modular "try another date" tool for event planners.

    Reuses `sparkcityx.fiscal_analysis.calendar_analogues` — the exact function
    the pinned notebook uses — parameterized to an arbitrary planner-chosen start
    date and length, so any candidate is scored by the identical, audited
    methodology. It reads the same historical daily series already produced by
    the pinned run; it does not touch the pinned dates, files or any chart above.
    """
    _section("🛠️ Test another date")
    with st.container(key="fiscal_explorer"):
        st.markdown(
            '<div class="fiscal-explorer-intro"><strong>How would another 2027 date compare?</strong>'
            '<span>Choose a date and event length. We will find matching weekday patterns in the same '
            'month of 2025 and compare their average fiscal records.</span></div>',
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            start = st.date_input(
                "Event start", value=date(2027, 4, 6),
                min_value=date(2027, 1, 1), max_value=date(2027, 12, 31),
                key="fiscal_explorer_start",
            )
        with col2:
            duration = st.slider("Event length", 1, 7, 3, format="%d day(s)", key="fiscal_explorer_duration")
    end = start + timedelta(days=duration - 1)
    weekday_span = start.strftime("%A") if duration == 1 else f"{start.strftime('%A')}–{end.strftime('%A')}"
    st.markdown(
        f'<div class="fiscal-test-summary"><span>TESTING</span><strong>{_planner_range_label(start, end)}</strong>'
        f'<p>{weekday_span} · compared with matching '
        f'{start.strftime("%B")} 2025 sequences</p></div>',
        unsafe_allow_html=True,
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
    with st.expander("How to interpret this comparison"):
        st.write(
            "This is a historical analogue from synthetic 2025 data, not a 2027 forecast or a claim "
            "that a date is optimal. Matching weekdays help make alternatives comparable, but one "
            "historical year cannot establish a repeatable seasonal pattern."
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
    candidates, scenarios, run_dir, daily_indexed = data["candidates"], data["scenarios"], data["run_dir"], data["daily"]

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
    _render_date_explorer(daily_indexed, pinned_net=pinned_row["mean"])

    # --- Financial impact of the event ---
    _section(
        "💵 Illustrative event spending scenario",
        "A planning scenario for a three-day, approximately 15,000-attendee event. These estimates come "
        "from authored assumptions—not from the historical fiscal records above.",
    )
    mixed = scenarios[scenarios["venue_archetype"] == "Mixed-access"].set_index("metric")
    impact_kpis = []
    for metric, label in [
        ("potential_gross_visitor_receipts", "Visitor receipts (P50)"),
        ("potential_retained_gross_spending", "Retained local spending (P50)"),
        ("organizer_cost", "Organizer cost (P50)"),
    ]:
        row = mixed.loc[metric]
        impact_kpis.append((label, _fmt_money(row["p50"]), f"P10–P90: {_fmt_money(row['p10'])} – {_fmt_money(row['p90'])}"))
    _kpi_row(impact_kpis)
    st.caption(
        "Headline values use the mixed-access venue scenario. P10–P90 shows the range produced by 5,000 "
        "assumption draws, not a statistical confidence interval."
    )
    st.markdown(
        '<div class="fiscal-evidence-note"><strong>Do not calculate city profit from these cards.</strong> '
        'Visitor receipts, retained local spending, and organizer costs belong to different accounting scopes.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Compare all venue scenarios"):
        scenario_table = scenarios.drop(columns=["draws"]).rename(columns={
            "venue_archetype": "Venue archetype", "metric": "Metric",
            "p10": "P10", "p50": "P50 (median)", "p90": "P90", "interpretation": "Read as",
        })
        for col in ("P10", "P50 (median)", "P90"):
            scenario_table[col] = scenario_table[col].map(_fmt_money)
        scenario_table["Metric"] = scenario_table["Metric"].str.replace("_", " ").str.capitalize()
        st.dataframe(scenario_table, hide_index=True, width="stretch")

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
