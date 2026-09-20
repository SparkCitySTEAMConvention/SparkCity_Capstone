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
    st.dataframe(display, hide_index=True, width="stretch")
    st.download_button(
        f"Download {period.lower()} scores", display.to_csv(index=False),
        file_name=f"{period.lower()}_scores_2025.csv", mime="text/csv",
        key=f"planner_download_{period}",
    )
    st.caption("Coverage counts show dates or records with required measurements, not complete sensor coverage.")


def render_convention_planner():
    load_css(section="convention_planner")
    st.markdown(
        '<section class="planner-banner">'
        '<div><span class="planner-eyebrow">NEW YORK DIGITAL CITY · COMMUNITY PLANNING</span>'
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
    october_weeks = weekly.loc[weekly["start_date"].dt.month == 10]
    best_october_week = october_weeks.loc[october_weeks["suitability"].idxmax()]
    november = monthly.loc[monthly["start_date"].dt.month == 11].iloc[0]
    november_weeks = weekly.loc[weekly["start_date"].dt.month == 11]
    best_november_week = november_weeks.loc[november_weeks["suitability"].idxmax()]
    st.markdown(
        '<section class="planner-decision-panel">'
            '<div class="planner-window-hero">'
            '<div class="planner-date-tile"><span>NOV</span><strong>3–5</strong>'
                '<small>2027 · WED–FRI</small></div>'
            '<div class="planner-window-copy"><span class="planner-eyebrow">RECOMMENDED OPERATING WINDOW</span>'
                '<h2>Early November balances the data with real operations</h2>'
                '<p class="planner-decision-intro">The model favors December, but its leading '
                'week overlaps Christmas. November provides the strongest usable window after '
                'holiday and travel checks.</p>'
            '<div class="planner-score-chips">'
                f'<div><span>MONTH</span><strong>{november["suitability"]:.2f}</strong><small>rank 2</small></div>'
                f'<div><span>WEEK</span><strong>{best_november_week["suitability"]:.2f}</strong>'
                f'<small>rank {int(best_november_week["suitability_rank"])}</small></div>'
            '<div><span>DURATION</span><strong>3</strong><small>days</small></div>'
            '</div></div></div>'
            '<div class="planner-decision-grid">'
                f'<article><span>Why November</span><strong>{best_november_week["suitability"] - best_october_week["suitability"]:.2f} points stronger</strong>'
                '<p>The best November week outperforms October’s best observed week and avoids '
                'the Christmas conflict attached to December’s numerical lead.</p></article>'
                '<article><span>Calendar check</span><strong>Clear of major November holidays</strong>'
                '<p>The window follows Election Day on November 2 and precedes Veterans Day and '
                'Thanksgiving. Confirm election-adjacent staffing and November 2 travel.</p></article>'
                '<article><span>Alternative Window</span><strong>October 19–21, 2027</strong>'
                f'<p>Use October if the Election Day check fails. Its best observed week scores '
                f'{best_october_week["suitability"]:.2f}, with lodging availability as the main constraint.</p></article>'
            '</div>'
            '<p class="planner-decision-verdict"><b>Decision gates:</b> confirm venue '
            'availability, hotel room blocks, election-adjacent staffing and travel, and '
            'competing citywide events before final approval.</p>'
            '</section>',
            unsafe_allow_html=True,
        )
    st.caption(
        f"Model leaders: {best_month['start_date']:%B} month {best_month['suitability']:.2f} · "
        f"{best_week['start_date']:%b %d}–{best_week['end_date']:%b %d} week "
        f"{best_week['suitability']:.2f} · {best_day['score_date']:%b %d} day "
        f"{best_day['suitability']:.2f}. Historical 2025 comparisons, not forecasts."
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
        st.write("More available rooms score higher. Lower occupancy, revenue, net profit, PM2.5, NO₂, precipitation and power consumption score higher. Traffic and temperature are outside the weighted score.")
        st.write("Occupancy rate = occupied rooms / (available rooms + occupied rooms) × 100, averaged per observation. Other inputs are also observation averages, not citywide totals.")
        st.latex(r"S = 0.30C + 0.30F + 0.10A + 0.10W + 0.20E")
        st.write("Min–max normalization uses 12 months, 51 full Monday–Sunday weeks, or 365 days separately. Partial weeks are excluded before normalization. Missing inputs or zero ranges leave scores unavailable.")
        st.write("The original analysis document used four factors and different weights. These exports use the updated five-factor model, so the earlier April/February recommendation is not the current ranking.")
        st.warning("Relative room availability does not establish lodging capacity for 15,000 attendees or venue capacity and availability. Scores are not probabilities, and a single day's ranking does not establish the best multi-day event window.")
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

            st.markdown('<div class="planner-left-spacer"></div>', unsafe_allow_html=True)

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
        with st.expander("View all monthly rankings", expanded=False):
            st.caption(
                "Calendar-order comparison using the approved 30/30/10/10/20 weights. "
                "Rank 1 is the highest suitability score."
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
