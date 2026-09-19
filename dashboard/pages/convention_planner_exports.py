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
    display = ordered.copy()
    for column in ["start_date", "end_date", "score_date"]:
        if column in display:
            display[column] = display[column].dt.strftime("%Y-%m-%d")
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
    st.caption("Source: saved PostgreSQL exports supplied September 18, 2026. Scores are historical comparisons, not forecasts or confirmed event dates.")
    monthly = exports["Monthly"]
    weekly = exports["Weekly"]
    daily = exports["Daily"]
    best_month = monthly.loc[monthly["suitability"].idxmax()]
    best_week = weekly.loc[weekly["suitability"].idxmax()]
    best_day = daily.loc[daily["suitability"].idxmax()]
    month_card, week_card, day_card = st.columns(3)
    month_card.metric(f"Leading month: {best_month['start_date']:%B}", f"{best_month['suitability']:.2f}")
    week_card.metric(f"Leading week: {best_week['start_date']:%b %d} – {best_week['end_date']:%b %d}", f"{best_week['suitability']:.2f}")
    day_card.metric(f"Leading day: {best_day['score_date']:%b %d}", f"{best_day['suitability']:.2f}")
    st.caption(f"The leading week's Capacity score is {best_week['capacity']:.2f}. Check lodging and venue availability before choosing dates.")
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
        st.latex(r"S = 0.30C + 0.30F + 0.15A + 0.15W + 0.10E")
        st.write("Min–max normalization uses 12 months, 51 full Monday–Sunday weeks, or 365 days separately. Partial weeks are excluded before normalization. Missing inputs or zero ranges leave scores unavailable.")
        st.write("The original analysis document used four factors and different weights. These exports use the updated five-factor model, so the earlier April/February recommendation is not the current ranking.")
        st.warning("Relative room availability does not establish lodging capacity for 15,000 attendees. Scores are not probabilities, and a single day's ranking does not establish the best multi-day event window.")
    with monthly_tab:
        exploratory_scores = monthly_explorer_scores(monthly)
        header_area, month_area = st.columns([3, 1])
        with header_area:
            st.subheader("12-Month Suitability Explorer")
            st.caption(
                "Verified 2025 monthly export with Energy included. "
                "Adjust the slider below to explore alternate factor weightings."
            )
        with month_area:
            explorer_month = st.selectbox(
                "Select a Month", exploratory_scores["Month"].tolist(),
                index=int(exploratory_scores["Baseline score"].idxmax()), key="explorer_month",
            )

        # MCC: three standalone cards — score, factor breakdown, and the
        # comparison chart with its sensitivity slider — matching the mockup layout.
        score_tile, breakdown_tile, comparison_tile = st.columns([0.85, 1.25, 1.3])

        with comparison_tile:
            with st.container(border=True, key="planner_comparison"):
                st.markdown("#### Monthly Scores: Baseline vs Adjusted Weights")
                comparison_chart_area = st.container()
                adjustment = st.select_slider(
                    "Capacity weight adjustment · percentage points",
                    options=[-15, -10, 0, 10, 15], value=0,
                    key="explorer_adjustment",
                )
                st.caption(
                    "0 = baseline 30/30/15/15/10 weights. Capacity changes by the selected "
                    "amount; other weights rebalance to 100%. All monthly totals update."
                )

        baseline_weights = WEIGHTS
        results = exploratory_scores.copy()
        results["Adjusted score"], adjusted_weights = adjusted_scores(results, adjustment)

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

                baseline_score = selected_result["Baseline score"]
                adjusted_score = selected_result["Adjusted score"]

                if pd.isna(adjusted_score):
                    st.metric("Adjusted score", "Unavailable")
                    st.caption("One or more required factors are unavailable.")
                else:
                    st.metric(
                        "Adjusted score",
                        f"{adjusted_score:.2f}",
                        delta=f"{adjusted_score - baseline_score:+.2f} vs baseline",
                        delta_color="off",
                    )

                st.write(
                    "**Baseline:** "
                    + (
                        "Unavailable"
                        if pd.isna(baseline_score)
                        else f"{baseline_score:.2f}"
                    )
                )
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
                st.caption("Factor scores stay fixed; weights and contributions respond to the adjustment.")

                calculation_caption_area = st.container()

        with comparison_chart_area:
            # Use calendar order and prevent alphabetical sorting of month names.
            monthly_comparison = results.sort_values(
                "Month",
                key=lambda months: pd.to_datetime(months, format="%B").dt.month,
            )[["Month", "Baseline score", "Adjusted score"]]
            monthly_comparison["Month"] = monthly_comparison["Month"].str[:3]

            # Long format for a grouped bar chart with a tight y-domain, so bars
            # fill the tile's height instead of the wide auto-padding st.bar_chart adds.
            chart_data = monthly_comparison.melt(
                "Month", var_name="Series", value_name="Score"
            )
            score_max = chart_data["Score"].max()
            y_domain = [0, float(score_max) * 1.08] if pd.notna(score_max) else [0, 100]

            comparison_chart = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X("Month:N", sort=None, title=None,
                            axis=alt.Axis(labelAngle=-45)),
                    xOffset=alt.XOffset("Series:N", sort=["Adjusted score", "Baseline score"]),
                    y=alt.Y("Score:Q", title=None, scale=alt.Scale(domain=y_domain)),
                    color=alt.Color(
                        "Series:N",
                        sort=["Adjusted score", "Baseline score"],
                        scale=alt.Scale(
                            domain=["Adjusted score", "Baseline score"],
                            range=["#287dcc", "#a9cdec"],
                        ),
                        legend=alt.Legend(title=None, orient="top"),
                    ),
                )
                .properties(height=340)
            )
            st.altair_chart(comparison_chart, use_container_width=True)
            st.caption(
                "Baseline and adjusted results for all 12 months. "
                "At zero adjustment, they are identical."
            )

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
                    adjusted_max = eligible["Adjusted score"].max()

                    baseline_leaders = eligible.loc[
                        (eligible["Baseline score"] - baseline_max).abs() < 1e-9,
                        "Month",
                    ].tolist()

                    adjusted_leaders = eligible.loc[
                        (eligible["Adjusted score"] - adjusted_max).abs() < 1e-9,
                        "Month",
                    ].tolist()

                    if adjustment == 0:
                        st.caption(f"**Leader:** {', '.join(baseline_leaders)} · {baseline_max:.2f}")
                        st.caption("Move the slider to explore.")
                    else:
                        st.caption(f"**Adjusted leader:** {', '.join(adjusted_leaders)} · {adjusted_max:.2f}")
                        if set(baseline_leaders) == set(adjusted_leaders):
                            st.caption("Leader unchanged in this scenario.")
                        else:
                            st.caption(f"Was {', '.join(baseline_leaders)} · {baseline_max:.2f} at baseline.")

        # MCC: inline contribution explanation belongs to the monthly suitability tile.
        with calculation_caption_area:
            st.caption("Weighted calculation · factor score × weight = contribution")
            st.caption("Baseline weights: Capacity 30%, Fiscal 30%, Air Quality 15%, Weather 15%, Energy 10%. Baselines preserve exported totals; adjusted scenarios use rounded category scores.")


        st.subheader("All monthly scores")
        st.dataframe(monthly, hide_index=True, use_container_width=True)
        st.download_button("Download monthly scores", monthly.to_csv(index=False),
                           file_name="monthly_scores_2025.csv", mime="text/csv")
