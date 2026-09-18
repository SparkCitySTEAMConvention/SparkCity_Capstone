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

# Kept as a live safety check, not a display fact: if the pinned notebook run's
# dates ever drift from the team's agreed dates again, the page should say so
# instead of silently presenting stale numbers as current.
TEAM_PROPOSED_DATES = ("2027-04-06", "2027-04-08")

METRIC_LABELS = {"revenue": "Revenue / observation", "expense": "Expense / observation",
                  "net_per_observation": "Net / observation"}


def _month_label(month):
    """Format e.g. "2025-06" as "June 2025"; falls back to the raw string if unparseable."""
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


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


def _section(icon_title, note=None):
    st.markdown(f'<div class="fiscal-section-title">{icon_title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="fiscal-section-note">{note}</div>', unsafe_allow_html=True)


def _render_decision_context(event_start, event_end, attendees):
    """Why a Tue-Thu week within April, and what fiscal analysis does/doesn't own.

    This is attributed context from the team's own multi-domain comparison
    (the Feb-vs-April planning memo), not something this fiscal notebook computes
    or independently verifies. Said plainly, rather than presented as if this
    page's fiscal analysis alone produced the overall recommendation. February
    only gets a brief mention here — it's not this page's focus.
    """
    _section("🧭 Why Spark City is looking at April 6–8, 2027")
    st.markdown(
        '<div class="fiscal-callout info">This is the fiscal piece of a four-factor team decision '
        "(capacity, fiscal, air quality, weather); February was the only other month with complete "
        "cross-dataset coverage and trailed on the team's overall score, so April carried the month-level "
        f"call. Within April, <strong>April 6–8</strong> falls inside <strong>April 5–11</strong>, reported "
        "as the month's strongest capacity week, and April 8 specifically was flagged as the best single "
        "operations day (lowest traffic and PM2.5) among the candidate days. "
        "<strong>This page independently verifies only the fiscal component</strong> — capacity, air "
        "quality and weather figures are cited from the team's comparison document, not recomputed here."
        "</div>",
        unsafe_allow_html=True,
    )
    _kpi_row([
        ("Recommended dates", f"{event_start} – {event_end}", "Tuesday–Thursday, 3 days"),
        ("Attendee target", f"{attendees:,}", "Design constraint for capacity planning"),
        ("Strongest capacity week", "April 5–11", "Per team comparison memo · cited, not recomputed here"),
    ])


def _render_date_explorer(daily_indexed, pinned_net):
    """Modular "try another date" tool for event planners.

    Reuses `sparkcityx.fiscal_analysis.calendar_analogues` — the exact function
    the pinned notebook uses — parameterized to an arbitrary planner-chosen start
    date and length, so any candidate is scored by the identical, audited
    methodology. It reads the same historical daily series already produced by
    the pinned run; it does not touch the pinned dates, files or any chart above.
    """
    _section(
        "🛠️ Explore an alternative date",
        "Run the same historical-analogue methodology used above against any start date and length, "
        "compared against same-weekday sequences in the matching month of 2025 (the one complete "
        "historical year in the data). This does not change the pinned April 6–8 recommendation or "
        "any figure above — it's a sanity-check tool for comparing options.",
    )
    col1, col2 = st.columns([2, 1])
    with col1:
        start = st.date_input(
            "Candidate start date (2027)", value=date(2027, 4, 6),
            min_value=date(2027, 1, 1), max_value=date(2027, 12, 31),
            key="fiscal_explorer_start",
        )
    with col2:
        duration = st.slider("Length (days)", 1, 7, 3, key="fiscal_explorer_duration")
    end = start + timedelta(days=duration - 1)
    weekday_span = start.strftime("%A") if duration == 1 else f"{start.strftime('%A')}–{end.strftime('%A')}"
    st.caption(
        f"Testing {weekday_span}, {start.isoformat()} – {end.isoformat()} ({duration} day"
        f"{'s' if duration != 1 else ''}) vs. {start.strftime('%B')} 2025."
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
                    f"{int(row['analogue_windows'])} analogue day(s)",
                ),
                unsafe_allow_html=True,
            )

    if net_mean is not None and pinned_net:
        delta = 100 * (net_mean - pinned_net) / pinned_net
        direction = "higher than" if delta >= 0 else "lower than"
        st.caption(
            f"Net/observation here is {abs(delta):.0f}% {direction} the pinned April 6–8 window "
            f"({_fmt_units(pinned_net)})."
        )

    weekend_days = sum(1 for i in range(duration) if (start + timedelta(days=i)).weekday() >= 5)
    if weekend_days:
        st.caption(
            f"⚠️ This window includes {weekend_days} weekend day(s) — the generator applies a 15% weekend "
            "revenue premium, so higher revenue here partly reflects that, not just the date choice."
        )
    st.caption(
        "Same caveats as the rest of this page apply: a historical analogue from synthetic 2025 data, "
        "not a 2027 forecast, causal estimate, or claim that any window is fiscally optimal."
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

    # --- Hero ---
    with st.container(key="fiscal_hero"):
        st.markdown('<span class="fiscal-eyebrow">FISCAL IMPACT · THE DECISION, IN THE DATA</span>', unsafe_allow_html=True)
        st.markdown("<h1>How the fiscal case for April 6–8, 2027 came together</h1>", unsafe_allow_html=True)
        st.write(
            f"Pinned dates: **{pinned_window_label}**, roughly {attendees:,} attendees. This page walks "
            "through what the historical fiscal data shows about April, why this specific week within it, "
            "and what the event itself could mean financially for SparkCity. All historical figures are "
            "synthetic, per-observation values from the SparkCity fiscal sensor feed — not verified city "
            "revenue, and not a forecast for 2027."
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

    # --- Why Feb vs April, why this week (attributed team context) ---
    _render_decision_context(event_start, event_end, attendees)

    # --- April's own fiscal snapshot (the centerpiece; February is a footnote) ---
    feb = monthly[monthly["month"] == "2025-02"].iloc[0]
    apr = monthly[monthly["month"] == "2025-04"].iloc[0]
    delta_pct = 100 * (apr["net_per_observation"] - feb["net_per_observation"]) / feb["net_per_observation"]
    best_month = monthly.loc[monthly["net_per_observation"].idxmax()]
    apr_rank = int((monthly["net_per_observation"] > apr["net_per_observation"]).sum()) + 1

    _section(
        "📊 April 6–8: the fiscal snapshot",
        "Historical April 2025, complete-month means, source units per observation (not city totals — "
        "see Limitations).",
    )
    _kpi_row([
        ("April revenue / observation", _fmt_units(apr["revenue"]), "2025-04, complete month"),
        ("April expense / observation", _fmt_units(apr["expense"]), "2025-04, complete month"),
        ("April net / observation", _fmt_units(apr["net_per_observation"]), "2025-04, complete month"),
        ("Rank among 2025's 12 months", f"#{apr_rank}", f"By net/obs · {_month_label(best_month['month'])} leads at {_fmt_units(best_month['net_per_observation'])}"),
    ])
    st.caption(
        f"For context: April's net/obs is {delta_pct:.0f}% higher than February's — the only other month "
        "with complete cross-dataset coverage (see Why Spark City is looking at April 6–8, above). "
        "Full year-over-year detail is in the expander below."
    )

    with st.expander("Full-year context: how April compares to the rest of 2025"):
        st.write(
            f"April is comfortably ahead of the shoulder months around it — but it is not the fiscal peak "
            f"of the year. That's **{_month_label(best_month['month'])}** "
            f"({_fmt_units(best_month['net_per_observation'])} net/obs). Fiscal data alone would not single "
            "out April as the single best month to hold the event; April was the stronger fiscal choice "
            "specifically against February, the only other month with complete cross-dataset coverage."
        )
        chart_path = run_dir / "04_monthly_patterns.png"
        if chart_path.exists():
            st.image(str(chart_path))
        yearly = monthly[["month", "revenue", "expense", "net_per_observation", "complete_month"]].copy()
        for col in ("revenue", "expense", "net_per_observation"):
            yearly[col] = yearly[col].map(_fmt_units)
        st.dataframe(yearly, hide_index=True, width="stretch")

    # --- Why this specific week within April ---
    net_rows = candidates[candidates["metric"] == "net_per_observation"].copy()
    net_rows["window"] = net_rows["candidate_start"] + " to " + net_rows["candidate_end"]
    highest = net_rows.loc[net_rows["mean"].idxmax()]
    pinned_row = net_rows[net_rows["selected"]].iloc[0]

    _section(
        "🗓️ Why this specific week, not another one in April",
        "Every complete-weekday-sequence window inside April 2025 matching each candidate's weekday "
        "pattern (4 analogue days per window). Min–max are historical ranges, not prediction intervals; "
        "overlapping windows are not independent evidence.",
    )
    st.markdown(
        f'<div class="fiscal-section-note">Fiscal data does not favor {pinned_window_label} over the other four '
        "candidate weeks — differences between them are small relative to their overlapping historical ranges, "
        f"and the highest historical mean ({escape(highest['candidate_start'])}–{escape(highest['candidate_end'])}, "
        f"{_fmt_units(highest['mean'])}) belongs to a different week. Per the team's comparison memo, the specific "
        "week was set by <strong>capacity/operations</strong> factors outside fiscal scope — April 5–11 was reported "
        "as the strongest capacity week of the month, and April 8 as the best single operations day. "
        f"Fiscal analysis confirms {pinned_window_label} is a solid, unexceptional choice within a strong month "
        "— not a weak one, and not a uniquely optimal one either.</div>",
        unsafe_allow_html=True,
    )
    table = net_rows[["window", "selected", "analogue_windows", "mean", "minimum", "maximum"]].rename(columns={
        "window": "Window", "selected": "Pinned window", "analogue_windows": "Analogue days",
        "mean": "Mean net/obs", "minimum": "Min", "maximum": "Max",
    })
    for col in ("Mean net/obs", "Min", "Max"):
        table[col] = table[col].map(_fmt_units)
    st.dataframe(table, hide_index=True, width="stretch")

    chart_path = run_dir / "07_candidate_analogues.png"
    if chart_path.exists():
        st.image(str(chart_path))
        st.markdown(
            '<div class="fiscal-chart-caption">Source chart: 07_candidate_analogues.png — reused as-is from the '
            "audited notebook run; not redrawn for this page.</div>",
            unsafe_allow_html=True,
        )

    # --- Modular date explorer ---
    _render_date_explorer(daily_indexed, pinned_net=pinned_row["mean"])

    # --- Financial impact of the event ---
    _section(
        "💵 What the event itself could mean for the city",
        "Authored assumption draws for a 3-day, ~15,000-attendee event (5,000 draws per venue archetype). "
        "These are separately authored scenario quantiles, independent of the historical fiscal values above "
        "— not forecast confidence intervals, and not calibrated to April weather or actual venue quotes.",
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
        "Mixed-access venue archetype shown as the headline case; see all three archetypes below. "
        "Receipts, retained spending and organizer cost are separate accounting scopes — do not subtract "
        "one from another and call it city profit."
    )
    with st.expander("All venue archetypes"):
        scenario_table = scenarios.drop(columns=["draws"]).rename(columns={
            "venue_archetype": "Venue archetype", "metric": "Metric",
            "p10": "P10", "p50": "P50 (median)", "p90": "P90", "interpretation": "Read as",
        })
        for col in ("P10", "P50 (median)", "P90"):
            scenario_table[col] = scenario_table[col].map(_fmt_money)
        scenario_table["Metric"] = scenario_table["Metric"].str.replace("_", " ").str.capitalize()
        st.dataframe(scenario_table, hide_index=True, width="stretch")

    # --- Key insights ---
    _section("🔑 Key insights")
    insights = [
        f"April 6–8's historical net revenue per observation ({_fmt_units(pinned_row['mean'])}) sits within "
        f"a strong month — April ranks #{apr_rank} of 2025's 12 months on net/obs, and comfortably ahead of "
        f"February ({_fmt_units(feb['net_per_observation'])}), the only other cross-dataset-complete month.",
        f"April is not the fiscal peak of the year, though — {_month_label(best_month['month'])} is higher "
        f"({_fmt_units(best_month['net_per_observation'])} net/obs). The month was shortlisted for "
        "cross-dataset coverage against February, not because it's the single richest month available.",
        f"Within April, fiscal data is roughly flat across the five candidate weeks; the pinned "
        f"{pinned_window_label} window is not the highest "
        f"({escape(highest['candidate_start'])}–{escape(highest['candidate_end'])} is, at {_fmt_units(highest['mean'])}) "
        "— the specific week was primarily a capacity/operations call, not a fiscal one.",
        "Only one complete historical April (2025) exists in the source data, so April seasonality "
        "and any 2027 read-through remain unconfirmed, not a repeatable pattern.",
        "Revenue and expense correlate at 0.61 across raw observations but only 0.00 across daily means; "
        "the relationship changes with the level of aggregation used.",
        "Currency, accounting period, and whether values are flows or snapshots are unconfirmed — treat "
        "these as source units per observation, not city totals, profit, or tax revenue.",
    ]
    st.markdown("<ul class='fiscal-insights'>" + "".join(f"<li>{escape(i)}</li>" for i in insights) + "</ul>", unsafe_allow_html=True)

    # --- Limitations ---
    st.markdown(
        '<div class="fiscal-callout warn">⚠️ <strong>Limitations to weigh in the decision:</strong> figures are '
        "descriptive synthetic historical analysis and separately authored event-cost assumptions — "
        "no causal effect, no date-optimality claim, and no verified city fiscal outcome is asserted. "
        "The overall multi-domain suitability score cited above comes from the team's own comparison "
        "memo and is not independently reproduced in this repository. Expense exceeds revenue in 13% of "
        "raw observations. Confirm venue/hotel quotes, attendee definition, overnight share, displacement, "
        "and organizer budget before using any of these figures for funding decisions.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="fiscal-footer">Source: notebooks/Hakeem_fiscal_analysis.ipynb, run <code>{escape(run_dir.name)}</code> · '
        f"docs/fiscal_analysis.md · claim scope: {escape(manifest.get('claim_scope', ''))}</div>",
        unsafe_allow_html=True,
    )
