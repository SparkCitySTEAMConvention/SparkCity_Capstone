# MCC / Convention Planner: load only this page's CSS section; shared shell stays in shared.py.
from components.shared import load_css
import pandas as pd
import streamlit as st
import os
import altair as alt
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sparkcityx.database import get_database_url



# MCC: automatic monthly loading, 15-minute cache, and explicit demo fallback.
PLANNER_SNAPSHOT = Path(__file__).resolve().parents[1] / "data" / "convention_monthly_inputs_2025.csv"
MONTHLY_INPUT_QUERY = "\n                WITH months AS (\n                    SELECT generate_series(\n                        DATE '2025-01-01',\n                        DATE '2025-12-01',\n                        INTERVAL '1 month'\n                    )::date AS month_start\n                ),\n                capacity AS (\n                    SELECT\n                        DATE_TRUNC('month', timestamp)::date AS month_start,\n                        AVG(available_rooms) AS available_rooms,\n                        AVG(\n                            100.0 * occupied_rooms\n                            / NULLIF(\n                                occupied_rooms::numeric + available_rooms,\n                                0\n                            )\n                        ) AS occupancy_rate,\n                        COUNT(DISTINCT timestamp::date) AS capacity_days\n                    FROM sparkcity.occupancy_data\n                    WHERE timestamp >= DATE '2025-01-01'\n                      AND timestamp < DATE '2026-01-01'\n                    GROUP BY 1\n                ),\n                fiscal AS (\n                    SELECT\n                        DATE_TRUNC('month', timestamp)::date AS month_start,\n                        AVG(revenue) AS revenue,\n                        AVG(revenue - expense) AS net_profit,\n                        COUNT(DISTINCT timestamp::date) AS fiscal_days\n                    FROM sparkcity.fiscal_data\n                    WHERE timestamp >= DATE '2025-01-01'\n                      AND timestamp < DATE '2026-01-01'\n                    GROUP BY 1\n                ),\n                air AS (\n                    SELECT\n                        DATE_TRUNC('month', timestamp)::date AS month_start,\n                        AVG(pm25) AS pm25,\n                        AVG(no2) AS no2,\n                        COUNT(DISTINCT timestamp::date) AS air_days\n                    FROM sparkcity.air_quality\n                    WHERE timestamp >= DATE '2025-01-01'\n                      AND timestamp < DATE '2026-01-01'\n                    GROUP BY 1\n                ),\n                weather AS (\n                    SELECT\n                        DATE_TRUNC('month', timestamp)::date AS month_start,\n                        AVG(precipitation) AS precipitation,\n                        COUNT(DISTINCT timestamp::date) AS weather_days\n                    FROM sparkcity.weather_data\n                    WHERE timestamp >= DATE '2025-01-01'\n                      AND timestamp < DATE '2026-01-01'\n                    GROUP BY 1\n                )\n                SELECT\n                    m.month_start,\n                    c.available_rooms,\n                    c.occupancy_rate,\n                    f.revenue,\n                    f.net_profit,\n                    a.pm25,\n                    a.no2,\n                    w.precipitation,\n                    c.capacity_days,\n                    f.fiscal_days,\n                    a.air_days,\n                    w.weather_days\n                FROM months m\n                LEFT JOIN capacity c USING (month_start)\n                LEFT JOIN fiscal f USING (month_start)\n                LEFT JOIN air a USING (month_start)\n                LEFT JOIN weather w USING (month_start)\n                ORDER BY m.month_start\n            "


@st.cache_resource(show_spinner=False)
def get_planner_engine(database_url):
    validated_url = get_database_url(database_url)
    return create_engine(
        validated_url, pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=15000"},
    )


@st.cache_data(ttl=900, show_spinner=False)
def load_planner_monthly_inputs(database_url):
    try:
        with get_planner_engine(database_url).connect() as connection:
            frame = pd.read_sql_query(
                text(MONTHLY_INPUT_QUERY), connection, parse_dates=["month_start"]
            )
        if frame.empty or frame["available_rooms"].notna().sum() == 0:
            raise ValueError("No usable monthly capacity data returned.")
        return frame, "PostgreSQL", pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        # Never expose connection credentials in a user-facing error.
        frame = pd.read_csv(PLANNER_SNAPSHOT, parse_dates=["month_start"])
        return frame, "Saved CSV snapshot", "Export supplied September 18, 2026"


def calculate_exploratory_scores(monthly_inputs):
    data = monthly_inputs.copy()

    def normalize(column, higher_is_better=True):
        values = pd.to_numeric(data[column], errors="coerce")
        minimum = values.min()
        maximum = values.max()

        # No usable range means normalization is undefined.
        if pd.isna(minimum) or maximum == minimum:
            return pd.Series(float("nan"), index=data.index)

        if higher_is_better:
            return 100 * (values - minimum) / (maximum - minimum)

        return 100 * (maximum - values) / (maximum - minimum)

    scores = pd.DataFrame(index=data.index)
    scores["Month"] = pd.to_datetime(
        data["month_start"]
    ).dt.month_name()

    scores["Capacity"] = (
        normalize("available_rooms")
        + normalize("occupancy_rate", higher_is_better=False)
    ) / 2

    scores["Fiscal"] = (
        normalize("revenue")
        + normalize("net_profit")
    ) / 2

    scores["Air Quality"] = (
        normalize("pm25", higher_is_better=False)
        + normalize("no2", higher_is_better=False)
    ) / 2

    scores["Weather"] = normalize(
        "precipitation",
        higher_is_better=False,
    )

    scores["Baseline score"] = (
        scores["Capacity"] * 0.35
        + scores["Fiscal"] * 0.35
        + scores["Air Quality"] * 0.15
        + scores["Weather"] * 0.15
    )

    return scores


# MCC: published category scores from Leigh's Day 4 notebook (section 8.3),
# which used coverage-aware year-then-month averaging and Day 2/3 cleaned
# feature data that isn't available in this checkout (data/features/ is
# gitignored). Recomputing from the raw live tables does not reproduce these
# values — see calculate_exploratory_scores docstring note above — so the
# 12-Month Suitability Explorer uses these authoritative published numbers
# directly instead, matching the team analysis document exactly.
LEIGH_DAY4_CATEGORY_SCORES = {
    "January":   {"Capacity": 65.81, "Fiscal": 3.95,   "Air Quality": 35.64, "Weather": 25.61, "Confidence": "HIGH"},
    "February":  {"Capacity": 53.15, "Fiscal": 18.25,  "Air Quality": 28.30, "Weather": 36.02, "Confidence": "HIGH"},
    "March":     {"Capacity": 50.92, "Fiscal": 47.05,  "Air Quality": 28.66, "Weather": 0.00,  "Confidence": "HIGH"},
    "April":     {"Capacity": 48.28, "Fiscal": 69.19,  "Air Quality": 36.20, "Weather": 100.00, "Confidence": "HIGH"},
    "May":       {"Capacity": 37.90, "Fiscal": 87.04,  "Air Quality": 22.17, "Weather": 72.08, "Confidence": "MODERATE"},
    "June":      {"Capacity": 34.57, "Fiscal": 100.00, "Air Quality": 66.53, "Weather": 39.72, "Confidence": "MODERATE"},
    "July":      {"Capacity": 51.88, "Fiscal": 83.82,  "Air Quality": 63.25, "Weather": 68.76, "Confidence": "MODERATE"},
    "August":    {"Capacity": 6.66,  "Fiscal": 76.31,  "Air Quality": 21.54, "Weather": 70.08, "Confidence": "MODERATE"},
    "September": {"Capacity": 42.97, "Fiscal": 47.35,  "Air Quality": 17.06, "Weather": 49.36, "Confidence": "MODERATE"},
    "October":   {"Capacity": 44.88, "Fiscal": 21.48,  "Air Quality": 55.40, "Weather": 84.80, "Confidence": "LIMITED"},
    "November":  {"Capacity": 52.79, "Fiscal": 6.33,   "Air Quality": 18.52, "Weather": 38.18, "Confidence": "LIMITED"},
    "December":  {"Capacity": 71.14, "Fiscal": 0.00,   "Air Quality": 88.79, "Weather": 68.84, "Confidence": "LIMITED"},
}


def get_published_monthly_scores():
    month_order = list(LEIGH_DAY4_CATEGORY_SCORES.keys())
    scores = pd.DataFrame(LEIGH_DAY4_CATEGORY_SCORES).T
    scores.insert(0, "Month", month_order)
    scores["Capacity"] = scores["Capacity"].astype(float)
    scores["Fiscal"] = scores["Fiscal"].astype(float)
    scores["Air Quality"] = scores["Air Quality"].astype(float)
    scores["Weather"] = scores["Weather"].astype(float)
    scores["Baseline score"] = (
        scores["Capacity"] * 0.35
        + scores["Fiscal"] * 0.35
        + scores["Air Quality"] * 0.15
        + scores["Weather"] * 0.15
    ).round(2)
    return scores.reset_index(drop=True)


def render_convention_planner():
    # MCC: paired with the convention_planner section in dashboard/styles/styles.css.
    load_css(section="convention_planner")
    env_path = Path(__file__).resolve().parents[2] / "secrets" / ".env"
    load_dotenv(env_path)
    DATABASE_URL = os.getenv("DATABASE_URL")
    try:
        engine = get_planner_engine(DATABASE_URL)
    except Exception:
        engine = None  # Monthly snapshot still works without database configuration.

    # Candidate results from the team's analysis document
    candidates = {
        "April": {
            "score": 61.54,
            "confidence": "HIGH",
            "proposed_week": "April 5–11, 2027",
            "proposed_dates": "April 6–8, 2027",
            "proposed_duration": "3 days",
            "capacity": 48.28,
            "fiscal": 69.19,
            "air_quality": 36.20,
            "weather": 100.00,
            "status": "Recommended candidate",
            "summary": (
                "April is the recommended candidate among the months "
                "evaluated with complete analytical coverage. Its stronger "
                "fiscal and precipitation scores outweigh February's "
                "modest capacity advantage."
            ),
        },
        "February": {
            "score": 34.64,
            "confidence": "HIGH",
            "proposed_week": "February 1–7, 2027",
            "proposed_dates": "February 1–3, 2027",
            "proposed_duration": "3 days",
            "capacity": 53.15,
            "fiscal": 18.25,
            "air_quality": 28.30,
            "weather": 36.02,
            "status": "Alternative candidate",
            "summary": (
                "February offers slightly stronger relative lodging capacity "
                "than April, but weaker fiscal and environmental scores "
                "reduce its overall suitability."
            ),
        },
    }

    FACTOR_WEIGHTS = {
        "Capacity": 0.35,
        "Fiscal": 0.35,
        "Air Quality": 0.15,
        "Weather": 0.15,
    }

    # MCC: domain banner only; shared navigation is untouched.
    st.markdown(
        '<section class="planner-banner">'
        '<div><span class="planner-eyebrow">SPARKCITY · COMMUNITY PLANNING</span>'
        '<h1>Find the Best Time to Host the STEAM Convention</h1>'
        '<p>Compare monthly suitability and explore how priorities change the ranking.</p></div>'
        '<div class="planner-banner-meta">2027 conference planning<br>'
        '<span>Historical source data · 2025</span></div></section>',
        unsafe_allow_html=True,
    )

    # MCC: Proposed Conference Window sits right under the banner, ahead of
    # the exploratory sections — the team's concrete recommendation, styled
    # to match the banner (planner-window-banner in styles.css).
    with st.container(key="planner_window"):
        window_heading, window_selector = st.columns([3, 1])
        with window_heading:
            st.subheader("Proposed Conference Window")
        with window_selector:
            selected_month = st.selectbox(
                "Candidate details",
                ["April", "February"],
            )

        selected = candidates[selected_month]

        factor_df = pd.DataFrame({
            "Factor": ["Capacity", "Fiscal", "Air Quality", "Weather"],
            "Score": [
                selected["capacity"],
                selected["fiscal"],
                selected["air_quality"],
                selected["weather"],
            ],
            "Weight (%)": [35, 35, 15, 15],
        })
        factor_df["Contribution"] = (
            factor_df["Score"] * factor_df["Weight (%)"] / 100
        )

        month_col, week_col, dates_col, duration_col, confidence_col = st.columns(5)
        month_col.metric("Candidate month", selected_month)
        week_col.metric("Proposed week", selected["proposed_week"])
        dates_col.metric("Proposed dates", selected["proposed_dates"])
        duration_col.metric("Proposed duration", selected["proposed_duration"])
        confidence_col.metric("Confidence", selected["confidence"])
        st.write(
            "Source: SparkCity February/April Convention Analysis (2027). "
            "These windows map historical 2025 weekday patterns to 2027; "
            "they are not forecasts of 2027 conditions or confirmed bookings."
        )

    st.divider()

    explorer_area = st.container(key="planner_explorer")

    st.divider()
    st.subheader("Convention Candidate Recommendation")
    st.caption("Team-reported scores, separate from the exploratory model above.")

    # MCC: one compact team recommendation row; exploratory results remain separate.
    # MCC: recommendation, alternative, and doc-sourced takeaways share one tile row.
    april_card, february_card, team_takeaways_card = st.columns(3)
    with april_card:
        with st.container(border=True, key="planner_candidate_score"):
            st.markdown("#### Recommended: April")
            st.metric("April Suitability", f"{candidates['April']['score']:.2f}")
            st.write("Stronger Fiscal and Weather scores; complete analytical coverage reported.")
            st.caption(f"Proposed: April 6–8, 2027 • Confidence: {candidates['April']['confidence']}")
            st.caption("Confidence is HIGH because April has complete coverage across all six time-based analytical datasets.")
    with february_card:
        with st.container(border=True, key="planner_candidate_alternative"):
            st.markdown("#### Alternative: February")
            st.metric("February Suitability", f"{candidates['February']['score']:.2f}")
            st.write("Capacity score 53.15 versus April's 48.28, but lower overall suitability.")
            st.caption(f"Proposed: February 1–3, 2027 • Confidence: {candidates['February']['confidence']}")
            st.caption("Confidence is HIGH because February has complete coverage across all six time-based analytical datasets.")
    with team_takeaways_card:
        with st.container(border=True, key="planner_team_takeaways"):
            st.markdown("#### Key Takeaways")
            st.caption("Team analysis document • February vs. April")
            st.write(
                "April has the stronger overall suitability score "
                "(61.54 vs. 34.64), driven by Fiscal and Weather."
            )
            st.write("February holds a slight capacity edge (53.15 vs. 48.28).")
            st.write(
                "Both months are HIGH confidence with complete coverage "
                "across all six analytical datasets."
            )
            st.caption(
                "July scored highest (67.30) but is MODERATE confidence "
                "(Traffic ends in May); November is LIMITED (Traffic and "
                "Energy unavailable)."
            )

    data_tab, calculation_tab, limitations_tab = st.tabs([
        "Monthly Source Data",
        "Score Calculation",
        "Planning Notes",
    ])

    # MCC: monthly inputs render into this bottom tab after automatic loading.
    with data_tab:
        source_data_area = st.container()

    with calculation_tab:
        st.write(
            "Metrics are min–max normalized across the observed months "
            "to a relative 0–100 scale."
        )
        st.markdown(
            "**Higher is better:** available rooms, revenue, net profit.  \n"
            "**Lower is better:** occupancy rate, PM2.5, NO₂, precipitation."
        )
        st.latex(
            r"\text{Higher-is-better score} = "
            r"100 \times \frac{x-\min(x)}{\max(x)-\min(x)}"
        )
        st.latex(
            r"\text{Lower-is-better score} = "
            r"100 \times \frac{\max(x)-x}{\max(x)-\min(x)}"
        )
        st.write(
            "Capacity, Fiscal, and Air Quality each average their two "
            "normalized inputs. Weather uses precipitation."
        )
        st.latex(r"S = 0.35C + 0.35F + 0.15A + 0.15W")
        st.dataframe(
            factor_df.round(2),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "Contributions use rounded component scores. Small differences "
            "from reported totals can result. This score is not a probability."
        )

    with limitations_tab:
        st.markdown("**Why July and November were not selected**")
        st.write(
            "July had the highest reported score, 67.30, but Traffic coverage "
            "ends in May, giving it MODERATE confidence. November shows "
            "occupancy advantages but has LIMITED analytical coverage because "
            "both Traffic and Energy are unavailable for that month. The team "
            "selected April from the final candidates with complete analytical "
            "coverage across all six time-based datasets."
        )
        st.write(
            "Traffic and Energy are outside the weighted model. "
            "Temperature is Fahrenheit and is not part of the Weather score."
        )
        st.markdown("**Weekly validation**")
        st.write(
            "Validate the selected candidate's proposed 2027 window against "
            "venue availability, capacity, event conflicts, and operational "
            "conditions before confirming dates. The proposal maps historical "
            "2025 weekday patterns to 2027; it is not a 2027 forecast."
        )
        st.warning(
            "The dataset supports relative capacity comparisons. It does not "
            "independently verify lodging for all 15,000 attendees."
        )

    st.divider()
    st.caption(
        "Scores and recommendation: team analysis document, using 2025 data. "
        "Monthly inputs below: automatically loaded through SELECT queries, with a labeled snapshot fallback. "
        "Category scores in the explorer above match the published document exactly."
    )

    with explorer_area:
        with st.expander("Data source and refresh", expanded=False):
            st.caption("Monthly data loads automatically and is cached for 15 minutes.")
            refresh_inputs = st.button("Refresh monthly data", key="planner_refresh")
            if refresh_inputs:
                load_planner_monthly_inputs.clear(DATABASE_URL)

        try:
            with st.spinner("Loading monthly suitability inputs…"):
                monthly_inputs, source, loaded_at = load_planner_monthly_inputs(DATABASE_URL)
        except Exception:
            st.error("Neither database inputs nor the saved snapshot could be loaded.")
            return

        if source == "Saved CSV snapshot":
            st.warning("Database unavailable — showing saved 2025 CSV snapshot supplied September 18, 2026.")
        else:
            st.caption(f"Source: PostgreSQL · Retrieved {loaded_at} · Cached up to 15 minutes")

        if monthly_inputs.empty:
            st.info("No monthly model inputs are available.")
            return

        exploratory_scores = get_published_monthly_scores()

        header_area, month_area = st.columns([3, 1])
        with header_area:
            st.subheader("12-Month Suitability Explorer")
            st.caption(
                "Published category scores from the team analysis document "
                "(Leigh's Day 4 notebook), using 2025 observations. "
                "Adjust the slider below to explore alternate factor weightings."
            )
        with month_area:
            explorer_month = st.selectbox(
                "Select a Month", exploratory_scores["Month"].tolist(),
                index=min(3, len(exploratory_scores) - 1), key="explorer_month",
            )

        # MCC: three standalone cards — score, factor breakdown, and the
        # comparison chart with its sensitivity slider — matching the mockup layout.
        score_tile, breakdown_tile, comparison_tile = st.columns([0.85, 1.25, 1.3])

        with comparison_tile:
            with st.container(border=True, key="planner_comparison"):
                st.markdown("#### Monthly Scores: Baseline vs Adjusted Weights")
                comparison_chart_area = st.container()
                adjusted_factor = "Capacity"
                adjustment = st.select_slider(
                    "Capacity weight adjustment · percentage points",
                    options=[-15, -10, 0, 10, 15], value=0,
                    key="explorer_adjustment",
                )
                st.caption(
                    "0 = original 35/35/15/15 weights. Capacity changes by the selected "
                    "amount; other weights rebalance to 100%. All monthly totals update."
                )

        # Zero adjustment means the original team weights.
        baseline_weights = {
            "Capacity": 0.35,
            "Fiscal": 0.35,
            "Air Quality": 0.15,
            "Weather": 0.15,
        }

        original_weight = baseline_weights[adjusted_factor]
        new_weight = original_weight + adjustment / 100

        # Redistribute the remaining weight proportionally.
        adjusted_weights = {
            factor: (
                new_weight
                if factor == adjusted_factor
                else weight * (1 - new_weight) / (1 - original_weight)
            )
            for factor, weight in baseline_weights.items()
        }

        results = exploratory_scores.copy()
        results["Adjusted score"] = sum(
            results[factor] * weight
            for factor, weight in adjusted_weights.items()
        )

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
                                 "Air Quality": "#49ae83", "Weather": "#8b5cf6"}
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
            st.caption("Baseline weights: Capacity 35%, Fiscal 35%, Air Quality 15%, Weather 15%. Calculations use unrounded values.")

        with source_data_area:
            st.caption(f"Source: {source} · {loaded_at} · Historical observations: 2025")
            st.dataframe(
                monthly_inputs.round(2),
                hide_index=True,
                use_container_width=True,
            )

            st.download_button(
                "Download monthly model inputs",
                data=monthly_inputs.to_csv(index=False),
                file_name="sparkcity_monthly_inputs_2025.csv",
                mime="text/csv",
            )

            st.caption(
                "Values are averages per observation, not citywide totals. "
                "Occupancy assumes total rooms = occupied + available rooms. "
                "Day counts indicate dates with records, not complete "
                "sensor coverage or complete metric values."
            )
