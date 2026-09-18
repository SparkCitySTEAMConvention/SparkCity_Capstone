"""Convention planner using verified monthly, weekly and daily 2025 exports."""
from components.shared import load_css
from components.planner_scores import (
    WEIGHTS, load_scores, monthly_explorer_scores,
)
import pandas as pd
import streamlit as st
import altair as alt


def ranking_chart(frame, label_column, selected=None):
    chart_data = frame[[label_column, "suitability"]].rename(columns={label_column: "Period", "suitability": "Score"})
    order = chart_data["Period"].tolist()
    base = alt.Chart(chart_data).encode(
        y=alt.Y("Period:N", sort=order, title=None, axis=alt.Axis(labelLimit=180)),
        x=alt.X("Score:Q", title="Suitability (0–100)", scale=alt.Scale(domain=[0, 100])),
        tooltip=["Period:N", alt.Tooltip("Score:Q", format=".2f")],
    )
    bars = base.mark_bar().encode(color=alt.condition(
        alt.datum.Period == (selected or order[0]), alt.value("#287dcc"), alt.value("#a9cdec")
    ))
    labels = base.mark_text(align="left", dx=5).encode(text=alt.Text("Score:Q", format=".2f"))
    st.altair_chart((bars + labels).properties(height=max(180, len(frame) * 29)), width="stretch")


def formatted_export(frame):
    display = frame.copy()
    for column in ["start_date", "end_date", "score_date"]:
        if column in display:
            display[column] = display[column].dt.strftime("%Y-%m-%d")
    return display


def render_period_results(frame, period):
    import calendar
    st.subheader(f"{period} comparisons")
    date_column = "score_date" if period == "Daily" else "start_date"
    selected_month = st.selectbox("Filter by month", ["All months", *calendar.month_name[1:]],
                                  key=f"planner_{period}_month")
    filtered = frame
    if selected_month != "All months":
        month_number = list(calendar.month_name).index(selected_month)
        if period == "Weekly":
            # Include full weeks that overlap either side of a month boundary.
            filtered = frame.loc[frame.start_date.dt.month.eq(month_number)
                                 | frame.end_date.dt.month.eq(month_number)]
        else:
            filtered = frame.loc[frame[date_column].dt.month.eq(month_number)]
    ordered = filtered.sort_values("suitability_rank", na_position="last").copy()
    st.caption("Filters keep the original annual ranking and scores. Weekly filters include full weeks overlapping the month.")
    if ordered.empty:
        st.info("No periods available for this filter.")
        return
    if period == "Weekly":
        ordered["Period"] = ordered.start_date.dt.strftime("%b %d") + " – " + ordered.end_date.dt.strftime("%b %d")
    else:
        ordered["Period"] = ordered.score_date.dt.strftime("%a, %b %d")
    st.write("**Top five in this view**")
    ranking_chart(ordered.head(5), "Period")
    labels = dict(zip(ordered[date_column], ordered["Period"]))
    selected_date = st.selectbox(f"Select a {period.lower()} period", ordered[date_column].tolist(),
        format_func=lambda value: labels[value], key=f"planner_{period}_date_{selected_month}")
    selected = ordered.loc[ordered[date_column] == selected_date].iloc[0]
    score_col, capacity_col = st.columns(2)
    score_col.metric("Suitability", f"{selected['suitability']:.2f}")
    capacity_col.metric("Relative Capacity score", f"{selected['capacity']:.2f}")
    with st.expander("View all scores and coverage"):
        st.dataframe(formatted_export(ordered.drop(columns="Period")), hide_index=True, width="stretch")
        st.caption("Coverage counts show dates or records with required measurements, not complete sensor coverage.")
    st.download_button(f"Download all {period.lower()} scores", formatted_export(frame).to_csv(index=False),
        file_name=f"{period.lower()}_scores_2025.csv", mime="text/csv", key=f"planner_download_{period}")


def render_convention_planner():
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
    st.caption("2025 historical rankings · Proposed periods for further planning")
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
    st.caption("Scores are normalized separately for months, weeks and days; compare within each time scale.")
    by_month = monthly_explorer_scores(monthly).set_index("Month")
    june, july, april = [by_month.loc[m] for m in ["June", "July", "April"]]
    st.subheader("Key takeaways")
    st.write(f"**Why June:** it leads at {june['Baseline score']:.2f}. Its Fiscal score of "
             f"{june['Fiscal']:.2f} contributes {june['Fiscal'] * WEIGHTS['Fiscal']:.2f} points, "
             "helping outweigh its weaker lodging capacity and precipitation score.")
    st.write(f"**Alternatives:** July scores {july['Baseline score']:.2f} and has stronger Capacity "
             f"({july['Capacity']:.2f} versus June’s {june['Capacity']:.2f}). April scores "
             f"{april['Baseline score']:.2f} and has better Weather and Capacity. June’s lead is "
             "modest; operational requirements could favor an alternative.")
    st.info(f"**Operational impact:** capacity contributes 30% of the model. June’s relative "
            f"Capacity score is {june['Capacity']:.2f}; the leading week’s is "
            f"{best_week['capacity']:.2f}. This suggests greater lodging coordination may be needed. "
            "For the 15,000-attendee planning target, prioritize hotel partnerships, room blocks "
            "and transport coordination. July and April remain alternatives if lodging logistics "
            "outweigh June’s overall score advantage. These scores do not measure rooms or beds "
            "and do not verify accommodation for 15,000 attendees.")
    st.caption("Event duration: a single day is ranked here. June 13–15 is a candidate three-day "
               "window within the leading week, pending comparison of consecutive windows. "
               "These historical dates are not 2027 forecasts or confirmed bookings.")
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
        st.caption("Source: saved PostgreSQL exports supplied September 18, 2026. Export checks cover dates and score arithmetic, not source-level validation. Scores are not probabilities.")
        with st.expander("Changes from previous analysis"):
            st.write("The earlier model used Capacity 35%, Fiscal 35%, Air Quality 15% and Weather 15%. The expanded data and revised five-factor weights replace that earlier ranking. No statistical significance has been established for differences in scores.")
    with monthly_tab:
        exploratory_scores = monthly_explorer_scores(monthly)
        header_area, month_area = st.columns([3, 1])
        with header_area:
            st.subheader("12-Month Suitability Explorer")
            st.caption(
                "Verified 2025 monthly export with Energy included. "
                "Final analysis uses fixed 30/30/15/15/10 weights."
            )
        with month_area:
            explorer_month = st.selectbox(
                "Select a Month", exploratory_scores["Month"].tolist(),
                index=int(exploratory_scores["Baseline score"].idxmax()), key="explorer_month",
            )

        results = exploratory_scores.copy()
        selected_result = results.loc[results["Month"] == explorer_month].iloc[0]
        score_tile, breakdown_tile, comparison_tile = st.columns([0.85, 1.25, 1.3])
        with score_tile:
            with st.container(border=True, key="planner_score"):
                st.markdown("#### Suitability Score")
                score = selected_result["Baseline score"]
                st.metric(explorer_month, "Unavailable" if pd.isna(score) else f"{score:.2f}")
                st.caption("Fixed analysis weights · Scale 0–100 · Not a probability")
                st.caption(f"Monthly rank: {int(selected_result['suitability_rank'])} of 12")

        with breakdown_tile:
            with st.container(border=True, key="planner_breakdown"):
                st.markdown("#### Factor Scores")
                factor_colors = {"Capacity": "#287dcc", "Fiscal": "#e5ad35",
                                 "Air Quality": "#49ae83", "Weather": "#8b5cf6", "Energy": "#e87935"}
                rows = []
                for factor, weight in WEIGHTS.items():
                    score = selected_result[factor]
                    label = "—" if pd.isna(score) else f"{score:.2f}"
                    contribution = "—" if pd.isna(score) else f"{score * weight:.2f}"
                    width = 0 if pd.isna(score) else max(0, min(100, float(score)))
                    rows.append(
                        f'<tr><th scope="row">{factor}'
                        f'<div class="planner-factor-track"><div style="width:{width}%;'
                        f'background:{factor_colors[factor]}"></div></div></th>'
                        f'<td>{label}</td><td>{weight * 100:.0f}%</td></tr>'
                    )
                st.markdown(
                    '<div class="planner-factor-table-wrap"><table class="planner-factor-table">'
                    '<thead><tr><th>Factor</th><th>Score</th><th>Weight</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table></div>', unsafe_allow_html=True,
                )
                with st.expander("Weighted contributions"):
                    contributions = pd.DataFrame({"Factor": list(WEIGHTS), "Points": [selected_result[f] * w for f, w in WEIGHTS.items()]})
                    st.dataframe(contributions.round(2), hide_index=True, width="stretch")
                    st.caption("Rounded contributions may differ slightly from the exported total.")

        with comparison_tile:
            with st.container(border=True, key="planner_comparison"):
                st.markdown("#### Monthly ranking")
                chart_data = monthly.copy()
                chart_data["Month"] = chart_data.start_date.dt.month_name()
                ranking_chart(chart_data.sort_values("suitability", ascending=False), "Month", explorer_month)

        with st.expander("View all monthly scores and coverage"):
            st.dataframe(formatted_export(monthly), hide_index=True, width="stretch")
            st.caption("Coverage counts indicate dates with required measurements, not complete sensor coverage.")
        st.download_button("Download monthly scores", formatted_export(monthly).to_csv(index=False),
                           file_name="monthly_scores_2025.csv", mime="text/csv")
