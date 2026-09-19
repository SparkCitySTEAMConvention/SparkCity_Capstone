"""Convention planner using verified monthly, weekly and daily 2025 exports."""
from components.shared import load_css
from components.planner_scores import (
    WEIGHTS, adjusted_scores, load_scores, monthly_explorer_scores,
)
import pandas as pd
import streamlit as st
import altair as alt


def render_period_results(frame, period):
    st.subheader(f"{period} suitability rankings")
    st.caption("Each time scale is normalized separately. Compare rankings within a time scale.")
    ordered = frame.sort_values(["suitability_rank"], na_position="last")
    date_column = "score_date" if period == "Daily" else "start_date"
    options = ordered[date_column].tolist()
    selected_date = st.selectbox(
        f"Select a {period.lower()} period", options,
        format_func=lambda value: value.strftime("%B %d, %Y"),
        key=f"planner_{period}_date",
    )
    selected = frame.loc[frame[date_column] == selected_date].iloc[0]
    score_col, capacity_col = st.columns(2)
    score_col.metric("Suitability", f"{selected['suitability']:.2f}")
    capacity_col.metric("Capacity score", f"{selected['capacity']:.2f}")
    if period == "Weekly":
        st.caption(f"Week ends {selected['end_date']:%B %d, %Y}. Partial weeks are excluded.")

    trend_columns = [
        date_column, "suitability", "suitability_rank",
        "capacity", "fiscal", "energy",
    ]
    trend = frame.loc[:, trend_columns].sort_values(date_column).copy()
    trend[date_column] = pd.to_datetime(trend[date_column], errors="raise")
    for column in trend_columns[1:]:
        trend[column] = pd.to_numeric(trend[column], errors="coerce")
    trend_chart = (
        alt.Chart(trend)
        .mark_line(point=True, color="#287dcc")
        .encode(
            x=alt.X(f"{date_column}:T", title=period),
            y=alt.Y("suitability:Q", title="Suitability score", scale=alt.Scale(domain=[0, 100])),
            tooltip=[
                alt.Tooltip(f"{date_column}:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("suitability:Q", title="Suitability", format=".2f"),
                alt.Tooltip("suitability_rank:Q", title="Rank"),
                alt.Tooltip("capacity:Q", title="Capacity", format=".2f"),
                alt.Tooltip("fiscal:Q", title="Fiscal", format=".2f"),
                alt.Tooltip("energy:Q", title="Energy", format=".2f"),
            ],
        )
        .properties(height=300, title=f"2025 {period.lower()} suitability trend")
    )
    selected_point_data = pd.DataFrame({
        date_column: pd.to_datetime([selected[date_column]], errors="raise"),
        "suitability": [float(selected["suitability"])],
    })
    selected_point = (
        alt.Chart(selected_point_data)
        .mark_point(size=150, filled=True, color="#e87935")
        .encode(
            x=alt.X(f"{date_column}:T"),
            y=alt.Y("suitability:Q"),
        )
    )
    st.altair_chart(trend_chart + selected_point, width="stretch")

    factor_chart_data = pd.DataFrame({
        "Factor": list(WEIGHTS),
        "Score": [float(selected[column]) for column in [
            "capacity", "fiscal", "air_quality", "weather", "energy"
        ]],
    })
    factor_chart = (
        alt.Chart(factor_chart_data)
        .mark_bar(color="#49ae83")
        .encode(
            x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("Factor:N", sort=list(WEIGHTS), title=None),
            tooltip=["Factor:N", alt.Tooltip("Score:Q", format=".2f")],
        )
        .properties(height=190, title=f"Selected {period.lower()} factor scores")
    )
    st.altair_chart(factor_chart, width="stretch")

    display = ordered.copy().dropna(axis=1, how="all")
    for column in ["start_date", "end_date", "score_date"]:
        if column in display:
            display[column] = pd.to_datetime(
                display[column], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.download_button(
        f"Download {period.lower()} scores", display.to_csv(index=False),
        file_name=f"{period.lower()}_scores_2025.csv", mime="text/csv",
        key=f"planner_download_{period}",
    )
    st.caption("Coverage counts show dates or records with required measurements, not complete sensor coverage.")


def render_convention_planner_exports():
    load_css(section="convention_planner")
    st.markdown(
        '<section class="planner-banner">'
        '<div><span class="planner-eyebrow">SPARKCITY · COMMUNITY PLANNING</span>'
        '<h1>Find the Best Time to Host the STEAM Convention</h1>'
        '<p>Compare monthly, weekly and daily suitability.</p></div>'
        '<div class="planner-banner-meta">Convention planning<br>'
        '<span>Historical observations · 2025</span></div></section>',
        unsafe_allow_html=True,
    )
    try:
        exports = {period: load_scores(period) for period in ("Monthly", "Weekly", "Daily")}
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Unable to load the saved score exports: {exc}")
        return
    monthly = exports["Monthly"]
    weekly = exports["Weekly"]
    daily = exports["Daily"]
    best_month = monthly.loc[monthly["suitability"].idxmax()]
    best_week = weekly.loc[weekly["suitability"].idxmax()]
    best_day = daily.loc[daily["suitability"].idxmax()]
    st.markdown(
        '<section class="planner-leaders-banner">'
        '<div class="planner-leaders-heading">'
        '<div><span class="planner-eyebrow">TOP-RANKED 2025 PERIODS</span>'
        '<h2>Leading Month, Week, and Day</h2>'
        '<p>The strongest periods at each time scale under the approved suitability model.</p></div>'
        '<div class="planner-leaders-meta">Decision summary<br>'
        '<span>Scores range from 0–100</span></div></div>'
        '<div class="planner-leaders-grid">'
        f'<article class="planner-leader-card month"><span>Leading month</span>'
        f'<strong>{best_month["start_date"]:%B}</strong>'
        f'<div>Suitability <b>{best_month["suitability"]:.2f}</b></div></article>'
        f'<article class="planner-leader-card week"><span>Leading week</span>'
        f'<strong>{best_week["start_date"]:%b %d}–{best_week["end_date"]:%b %d}</strong>'
        f'<div>Suitability <b>{best_week["suitability"]:.2f}</b></div></article>'
        f'<article class="planner-leader-card day"><span>Leading day</span>'
        f'<strong>{best_day["score_date"]:%b %d}</strong>'
        f'<div>Suitability <b>{best_day["suitability"]:.2f}</b></div></article>'
        '</div>'
        f'<p class="planner-leaders-note"><b>Operational check:</b> The leading week’s '
        f'Capacity score is {best_week["capacity"]:.2f}. Confirm the Javits date hold '
        'and sufficient hotel room blocks before choosing dates.</p></section>',
        unsafe_allow_html=True,
    )
    st.caption("Source: saved PostgreSQL exports supplied September 18, 2026. Scores are historical comparisons, not forecasts or confirmed event dates.")
    st.markdown(
        '<section class="planner-decision-panel">'
        '<span class="planner-eyebrow">CROSS-DOMAIN OPERATIONAL RECOMMENDATION</span>'
        '<h2>Advance June 8–10, 2027 at Javits for feasibility checks</h2>'
        '<p class="planner-decision-intro">June remains the strongest overall month, '
        'but the event should use a Tuesday–Thursday pattern and proceed only after '
        'the Javits date hold and hotel room blocks are confirmed. The capacity score '
        'measures lodging pressure; it does not establish Javits hall capacity or '
        'availability. These dates are a planning inference from 2025 trends, not a '
        'forecast or confirmed booking.</p>'
        '<div class="planner-decision-grid">'
        '<article><span>Hotel occupancy</span><strong>55.3% June headroom</strong>'
        '<p>June is the tightest lodging month. Current analyses estimate 5,417–5,977 '
        'rooms per night for 15,000 attendees; reconcile the assumptions and contract '
        'the required blocks before approval.</p></article>'
        '<article><span>Javits mobility</span><strong>36.12% high congestion</strong>'
        '<p>June averages 76.44 vehicles and 18.95 km/h, with a 5 PM peak. Coordinate '
        'Javits arrival windows, transit guidance, shuttle staging, and departures '
        'outside the peak.</p></article>'
        '<article><span>Javits fiscal scenario</span><strong>$8.39M visitor spending</strong>'
        '<p>The authored 15,000-attendee scenario also estimates a $2.08M organizer '
        'budget and $1.14M in taxes and fees. These are planning assumptions, not quotes '
        'or guaranteed impact; June’s historical fiscal score ranks first.</p></article>'
        '<article><span>Energy &amp; environment</span><strong>44.02 kW June average</strong>'
        '<p>Energy is stable and is not the binding constraint. Javits provides the main '
        'indoor setting, but covered arrival routes, heat/rain plans, and live air and '
        'weather checks are still required.</p></article>'
        '</div>'
        '<p class="planner-decision-verdict"><b>Decision rule:</b> June scores 61.73, '
        '2.63 points above July and 3.14 above April. Use April as the operational '
        'fallback if the Javits hold or required June hotel blocks cannot be secured.</p>'
        '</section>',
        unsafe_allow_html=True,
    )
    monthly_tab, weekly_tab, daily_tab, methodology_tab = st.tabs([
        "Monthly", "Weekly", "Daily", "Scoring method"
    ])
    with weekly_tab:
        render_period_results(weekly, "Weekly")
    with daily_tab:
        render_period_results(daily, "Daily")
    with methodology_tab:
        st.write("Capacity averages available-room and occupancy scores. Fiscal averages revenue and net-profit scores. Air Quality averages PM2.5 and NO₂ scores. Weather uses precipitation; Energy uses power consumption.")
        st.write("More available rooms, revenue and net profit score higher. Lower occupancy, PM2.5, NO₂, precipitation and power consumption score higher. Traffic and temperature are outside the weighted score.")
        st.write("Occupancy rate = occupied rooms / (available rooms + occupied rooms) × 100, averaged per observation. Other inputs are also observation averages, not citywide totals.")
        st.latex(r"S = 0.30C + 0.30F + 0.10A + 0.10W + 0.20E")
        st.write("Min–max normalization uses 12 months, 51 full Monday–Sunday weeks, or 365 days separately. Partial weeks are excluded before normalization. Missing inputs or zero ranges leave scores unavailable.")
        st.write("The original analysis document used four factors and different weights. These exports use the updated five-factor model, so the earlier April/February recommendation is not the current ranking.")
        st.warning("Relative room availability does not establish lodging capacity for 15,000 attendees or Javits hall capacity and availability. Scores are not probabilities, and a single day's ranking does not establish the best multi-day event window.")
    with monthly_tab:
        exploratory_scores = monthly_explorer_scores(monthly)
        header_area, month_area = st.columns([3, 1])
        with header_area:
            st.subheader("12-Month Suitability Explorer")
            st.caption(
                "Verified 2025 monthly export using the approved fixed weights."
            )
        with month_area:
            explorer_month = st.selectbox(
                "Select a Month", exploratory_scores["Month"].tolist(),
                index=int(exploratory_scores["Baseline score"].idxmax()), key="explorer_month",
            )

        # Three cards summarize the selected month and the full-year ranking.
        score_tile, breakdown_tile, comparison_tile = st.columns([0.85, 1.25, 1.3])

        with comparison_tile:
            with st.container(border=True, key="planner_comparison"):
                st.markdown("#### Monthly Suitability Scores")
                comparison_chart_area = st.container()
                st.caption(
                    "Capacity 30% · Fiscal 30% · Air Quality 10% · "
                    "Weather 10% · Energy 20%"
                )

        baseline_weights = WEIGHTS
        results = exploratory_scores.copy()
        results["Adjusted score"], adjusted_weights = adjusted_scores(results, 0)

        selected_result = results.loc[
            results["Month"] == explorer_month
        ].iloc[0]

        breakdown = pd.DataFrame({
            "Factor": list(baseline_weights),
            "Factor score": [
                selected_result[factor] for factor in baseline_weights
            ],
            "Baseline weight (%)": [
                weight * 100 for weight in baseline_weights.values()
            ],
            "Adjusted weight (%)": [
                adjusted_weights[factor] * 100
                for factor in baseline_weights
            ],
        })

        breakdown["Contribution"] = (
            breakdown["Factor score"]
            * breakdown["Adjusted weight (%)"]
            / 100
        )

        with score_tile:
            with st.container(border=True, key="planner_score"):
                st.markdown("#### Suitability Score")

                adjusted_score = selected_result["Adjusted score"]

                if pd.isna(adjusted_score):
                    st.metric("Suitability", "Unavailable")
                    st.caption("One or more required factors are unavailable.")
                else:
                    st.metric("Suitability", f"{adjusted_score:.2f}")
                st.caption("Scale: 0–100 • Not a probability")

            explorer_takeaways_area = st.container()

        with breakdown_tile:
            with st.container(border=True, key="planner_breakdown"):
                st.markdown("#### Factor Scores")

                # MCC: contributions expose how each factor builds the overall score.
                factor_colors = {"Capacity": "#287dcc", "Fiscal": "#e5ad35",
                                 "Air Quality": "#49ae83", "Weather": "#8b5cf6", "Energy": "#e87935"}
                rows = []
                for _, row in breakdown.iterrows():
                    factor = row["Factor"]
                    score = row["Factor score"]
                    score_label = "—" if pd.isna(score) else f"{score:.2f}"
                    contribution = row["Contribution"]
                    contribution_label = "—" if pd.isna(contribution) else f"{contribution:.2f}"
                    width = 0 if pd.isna(score) else max(0, min(100, float(score)))
                    rows.append(
                        f'<tr><th scope="row">{factor}'
                        f'<div class="planner-factor-track"><div style="width:{width}%;'
                        f'background:{factor_colors[factor]}"></div></div></th>'
                        f'<td>{score_label}</td><td>{row["Adjusted weight (%)"]:.2f}%</td>'
                        f'<td><strong>{contribution_label}</strong></td></tr>'
                    )
                st.markdown(
                    '<div class="planner-factor-table-wrap"><table class="planner-factor-table">'
                    '<thead><tr><th>Factor</th><th>Score</th><th>Weight</th>'
                    '<th>Contribution</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table></div>',
                    unsafe_allow_html=True,
                )
                st.caption("Each contribution equals the factor score multiplied by its approved weight.")

                calculation_caption_area = st.container()

        with comparison_chart_area:
            # Use calendar order and prevent alphabetical sorting of month names.
            monthly_comparison = results.sort_values(
                "Month",
                key=lambda months: pd.to_datetime(months, format="%B").dt.month,
            )[["Month", "Baseline score"]].rename(
                columns={"Baseline score": "Score"}
            )
            monthly_comparison["Month"] = monthly_comparison["Month"].str[:3]

            score_max = monthly_comparison["Score"].max()
            y_domain = [0, float(score_max) * 1.08] if pd.notna(score_max) else [0, 100]

            comparison_chart = (
                alt.Chart(monthly_comparison)
                .mark_bar(color="#287dcc")
                .encode(
                    x=alt.X("Month:N", sort=None, title=None,
                            axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("Score:Q", title="Suitability", scale=alt.Scale(domain=y_domain)),
                    tooltip=["Month:N", alt.Tooltip("Score:Q", format=".2f")],
                )
                .properties(height=340)
            )
            st.altair_chart(comparison_chart, width="stretch")
            st.caption("Monthly scores use the approved fixed weighting model.")

        # MCC: exploratory takeaways, compacted into a smaller tile stacked
        # under the Suitability Score card so the row stays level.
        with explorer_takeaways_area:
            with st.container(border=True, key="planner_takeaways"):
                st.markdown("##### Key Takeaways")
                eligible = results.dropna(
                    subset=["Baseline score", "Adjusted score"]
                )

                if eligible.empty:
                    st.caption("No complete monthly scores are available.")
                else:
                    baseline_max = eligible["Baseline score"].max()
                    baseline_leaders = eligible.loc[
                        (eligible["Baseline score"] - baseline_max).abs() < 1e-9,
                        "Month",
                    ].tolist()
                    ranked = eligible.sort_values("Baseline score", ascending=False)
                    leader = ranked.iloc[0]
                    runner_up = ranked.iloc[1]
                    st.caption(f"**Leader:** {', '.join(baseline_leaders)} · {baseline_max:.2f}")
                    st.caption(
                        f"{leader['Month']} leads because its Fiscal score is "
                        f"{leader['Fiscal']:.2f} and its Energy score is "
                        f"{leader['Energy']:.2f}; its Capacity score of "
                        f"{leader['Capacity']:.2f} remains the main operational constraint."
                    )
                    st.caption(
                        f"It ranks {leader['Baseline score'] - runner_up['Baseline score']:.2f} "
                        f"points above {runner_up['Month']}."
                    )

        # MCC: inline contribution explanation belongs to the monthly suitability tile.
        with calculation_caption_area:
            st.caption("Weighted calculation · factor score × weight = contribution")
            st.caption("Weights: Capacity 30%, Fiscal 30%, Air Quality 10%, Weather 10%, Energy 20%.")

        st.subheader("Monthly Ranking Table")
        st.caption(
            "Calendar-order comparison using the approved 30/30/10/10/20 weights. "
            "Rank 1 is the highest suitability score."
        )
        monthly_table = (
            monthly.sort_values("start_date")
            .assign(Month=lambda frame: frame["start_date"].dt.strftime("%B"))
            [[
                "Month", "suitability_rank", "capacity", "fiscal",
                "air_quality", "weather", "energy", "suitability",
            ]]
            .rename(columns={
                "suitability_rank": "Rank",
                "capacity": "Capacity",
                "fiscal": "Fiscal",
                "air_quality": "Air Quality",
                "weather": "Weather",
                "energy": "Energy",
                "suitability": "Suitability",
            })
        )
        st.dataframe(
            monthly_table,
            hide_index=True,
            width="stretch",
            column_config={
                "Month": st.column_config.TextColumn("Month", width="medium"),
                "Rank": st.column_config.NumberColumn("Rank", format="%d"),
                "Capacity": st.column_config.NumberColumn("Capacity", format="%.2f"),
                "Fiscal": st.column_config.NumberColumn("Fiscal", format="%.2f"),
                "Air Quality": st.column_config.NumberColumn("Air Quality", format="%.2f"),
                "Weather": st.column_config.NumberColumn("Weather", format="%.2f"),
                "Energy": st.column_config.NumberColumn("Energy", format="%.2f"),
                "Suitability": st.column_config.NumberColumn("Suitability", format="%.2f"),
            },
        )
        st.download_button(
            "Download monthly ranking table",
            monthly_table.to_csv(index=False),
            file_name="monthly_scores_2025.csv",
            mime="text/csv",
        )
