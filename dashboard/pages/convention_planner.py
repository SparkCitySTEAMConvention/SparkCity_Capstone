import pandas as pd
import streamlit as st
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


import pandas as pd
import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


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


def render_convention_planner():
    # All your existing code below the imports goes here,
    # indented four spaces.
    env_path = Path(__file__).resolve().parents[2] / "secrets" / ".env"
    load_dotenv(env_path)

    # Continue with existing connection, candidate data,
    # and page display code.


    env_path = Path(__file__).resolve().parents[2] / "secrets" / ".env"
    load_dotenv(env_path)

    DATABASE_URL = os.getenv("DATABASE_URL")

    engine = create_engine(DATABASE_URL)

    # Candidate results from the team's analysis document
    candidates = {
        "April": {
            "score": 61.54,
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

    st.title("🏙️ SparkCity Convention Planner")
    st.caption("2027 conference planning • Historical source data: 2025")

    explorer_area = st.container()

    st.divider()
    st.subheader("Team-Reported Candidate Recommendation")

    heading, selector = st.columns([3, 1])

    with heading:
        st.subheader("Find the Best Time to Host the STEAM Convention")
        st.caption(
            "Compare candidate months across capacity, fiscal conditions, "
            "air quality, and weather."
        )

    with selector:
        selected_month = st.selectbox(
            "Select a month",
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

    comparison_df = pd.DataFrame({
        "Month": ["April", "February"],
        "Score": [candidates["April"]["score"], candidates["February"]["score"]],
    })

    # Top row: matches the mockup's three main panels.
    score_card, factors_card, comparison_card = st.columns([1, 1.25, 1.25])

    with score_card:
        with st.container(border=True):
            st.markdown("#### Overall Suitability Score")
            st.metric(selected_month, f"{selected['score']:.2f}")
            st.success(selected["status"])
            st.caption("Complete analytical coverage reported by the team.")
            st.write(selected["summary"])

    with factors_card:
        with st.container(border=True):
            st.markdown(f"#### Factor Scores for {selected_month}")

            for _, row in factor_df.iterrows():
                st.write(f"**{row['Factor']}** — {row['Score']:.2f}")
                st.progress(float(row["Score"]) / 100)

            st.caption("Normalized scores • Scale: 0–100")

    with comparison_card:
        with st.container(border=True):
            st.markdown("#### Month Comparison")
            st.bar_chart(
                comparison_df.set_index("Month"),
                y="Score",
                height=230,
                color="#2563EB",
            )
            st.caption("April 61.54 | February 34.64")
            st.write("**April leads by 26.90 points.**")

    # Second row: recommendation, alternative, and takeaways.
    why_card, alternative_card, takeaway_card = st.columns(3)

    with why_card:
        with st.container(border=True):
            st.markdown("#### ✅ Why April?")
            st.write("Stronger overall suitability among the final candidates.")
            st.write("• Fiscal score: **69.19**")
            st.write("• Weather score: **100.00**")
            st.write("• Complete analytical coverage reported")
            st.caption("Weather reflects relative precipitation conditions.")

    with alternative_card:
        with st.container(border=True):
            st.markdown("#### 🏅 Alternative: February")
            st.metric("Overall suitability", "34.64")
            st.write("Capacity score: **53.15**, versus April’s **48.28**.")
            st.write(
                "A capacity-focused alternative with weaker fiscal "
                "and environmental scores."
            )

    with takeaway_card:
        with st.container(border=True):
            st.markdown("#### Key Takeaways")
            st.write("• April is the recommended candidate.")
            st.write("• Capacity and Fiscal each carry 35% weight.")
            st.write("• Traffic and Energy support operational planning.")
            st.write("• Dates and event duration remain pending.")

    st.subheader("Proposed Conference Window")
    with st.container(border=True):
        month_col, week_col, dates_col, duration_col = st.columns(4)
        month_col.metric("Month", "April")
        week_col.metric("Week", "Pending")
        dates_col.metric("Dates", "Pending")
        duration_col.metric("Duration", "Pending")

    data_tab, calculation_tab, limitations_tab = st.tabs([
        "Live Data Summaries",
        "Score Calculation",
        "Planning Notes",
    ])

    with data_tab:
        st.caption(
            f"{selected_month} 2025 • Observation averages from PostgreSQL. "
            "These are source metrics, not normalized factor scores."
        )

        # Queries run only when requested, keeping the main view responsive.
        if st.button(f"Load {selected_month} database summary"):
            month_number = {"February": 2, "April": 4}[selected_month]
            start_date = pd.Timestamp(
                year=2025, month=month_number, day=1
            )
            end_date = start_date + pd.offsets.MonthBegin(1)

            summary_query = text("""
                SELECT
                    'Capacity' AS category,
                    'Available rooms' AS metric,
                    AVG(available_rooms)::double precision AS average,
                    COUNT(available_rooms) AS observations
                FROM sparkcity.occupancy_data
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Fiscal', 'Revenue',
                    AVG(revenue), COUNT(revenue)
                FROM sparkcity.fiscal_data
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Fiscal', 'Revenue minus expense',
                    AVG(revenue - expense), COUNT(revenue - expense)
                FROM sparkcity.fiscal_data
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Air Quality', 'PM2.5',
                    AVG(pm25), COUNT(pm25)
                FROM sparkcity.air_quality
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Air Quality', 'NO₂',
                    AVG(no2), COUNT(no2)
                FROM sparkcity.air_quality
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Weather', 'Precipitation',
                    AVG(precipitation), COUNT(precipitation)
                FROM sparkcity.weather_data
                WHERE timestamp >= :start_date AND timestamp < :end_date

                UNION ALL

                SELECT 'Weather', 'Temperature (°F)',
                    AVG(temperature), COUNT(temperature)
                FROM sparkcity.weather_data
                WHERE timestamp >= :start_date AND timestamp < :end_date
            """)

            try:
                with engine.connect() as connection:
                    summary_df = pd.read_sql_query(
                        summary_query,
                        connection,
                        params={
                            "start_date": start_date.to_pydatetime(),
                            "end_date": end_date.to_pydatetime(),
                        },
                    )

                st.dataframe(
                    summary_df,
                    hide_index=True,
                    column_config={
                        "average": st.column_config.NumberColumn(
                            "Average per observation",
                            format="%.2f",
                        ),
                        "observations": "Non-null observations",
                        "category": "Category",
                        "metric": "Metric",
                    },
                    use_container_width=True,
                )
                st.caption(
                    "Room values are not citywide totals. Currency, pollutant, "
                    "and precipitation units require confirmation. "
                    "Missing values are excluded from each average."
                )
            except Exception:
                st.warning(
                    "Live data could not be loaded. "
                    "The team-reported candidate analysis remains available."
                )

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
        st.markdown("**Why July was not selected**")
        st.write(
            "July had the highest reported score, 67.30, but Traffic coverage "
            "ends in May. The team selected April from the final candidates "
            "with complete analytical coverage."
        )
        st.write(
            "Traffic and Energy are outside the weighted model. "
            "Temperature is Fahrenheit and is not part of the Weather score."
        )
        st.markdown("**Weekly validation**")
        st.write(
            "Review April's dated capacity and operational conditions before "
            "confirming a week, dates, or duration. The document's proposed "
            "2025 windows are historical analysis, not confirmed future dates."
        )
        st.warning(
            "The dataset supports relative capacity comparisons. It does not "
            "independently verify lodging for all 15,000 attendees."
        )

    st.divider()
    st.caption(
        "Scores and recommendation: team analysis document, using 2025 data. "
        "Live summaries: PostgreSQL, loaded on request through SELECT queries. "
        "Monthly scores have not yet been independently reproduced."
    )

    with explorer_area:
        st.caption(
            "2025 historical observations for 2027 planning. "
            "Monthly aggregation is pending team confirmation."
        )

        if st.button("Load monthly model inputs"):
            monthly_query = text("""
                WITH months AS (
                    SELECT generate_series(
                        DATE '2025-01-01',
                        DATE '2025-12-01',
                        INTERVAL '1 month'
                    )::date AS month_start
                ),
                capacity AS (
                    SELECT
                        DATE_TRUNC('month', timestamp)::date AS month_start,
                        AVG(available_rooms) AS available_rooms,
                        AVG(
                            100.0 * occupied_rooms
                            / NULLIF(
                                occupied_rooms::numeric + available_rooms,
                                0
                            )
                        ) AS occupancy_rate,
                        COUNT(DISTINCT timestamp::date) AS capacity_days
                    FROM sparkcity.occupancy_data
                    WHERE timestamp >= DATE '2025-01-01'
                      AND timestamp < DATE '2026-01-01'
                    GROUP BY 1
                ),
                fiscal AS (
                    SELECT
                        DATE_TRUNC('month', timestamp)::date AS month_start,
                        AVG(revenue) AS revenue,
                        AVG(revenue - expense) AS net_profit,
                        COUNT(DISTINCT timestamp::date) AS fiscal_days
                    FROM sparkcity.fiscal_data
                    WHERE timestamp >= DATE '2025-01-01'
                      AND timestamp < DATE '2026-01-01'
                    GROUP BY 1
                ),
                air AS (
                    SELECT
                        DATE_TRUNC('month', timestamp)::date AS month_start,
                        AVG(pm25) AS pm25,
                        AVG(no2) AS no2,
                        COUNT(DISTINCT timestamp::date) AS air_days
                    FROM sparkcity.air_quality
                    WHERE timestamp >= DATE '2025-01-01'
                      AND timestamp < DATE '2026-01-01'
                    GROUP BY 1
                ),
                weather AS (
                    SELECT
                        DATE_TRUNC('month', timestamp)::date AS month_start,
                        AVG(precipitation) AS precipitation,
                        COUNT(DISTINCT timestamp::date) AS weather_days
                    FROM sparkcity.weather_data
                    WHERE timestamp >= DATE '2025-01-01'
                      AND timestamp < DATE '2026-01-01'
                    GROUP BY 1
                )
                SELECT
                    m.month_start,
                    c.available_rooms,
                    c.occupancy_rate,
                    f.revenue,
                    f.net_profit,
                    a.pm25,
                    a.no2,
                    w.precipitation,
                    c.capacity_days,
                    f.fiscal_days,
                    a.air_days,
                    w.weather_days
                FROM months m
                LEFT JOIN capacity c USING (month_start)
                LEFT JOIN fiscal f USING (month_start)
                LEFT JOIN air a USING (month_start)
                LEFT JOIN weather w USING (month_start)
                ORDER BY m.month_start
            """)

            with engine.connect() as connection:
                monthly_inputs = pd.read_sql_query(
                    monthly_query,
                    connection,
                    parse_dates=["month_start"],
                )

            st.session_state["planner_monthly_inputs"] = monthly_inputs

        # The explorer needs loaded data on every Streamlit rerun.
        if "planner_monthly_inputs" not in st.session_state:
            st.info("Click ‘Load monthly model inputs’ to open the suitability explorer.")
            return

        monthly_inputs = st.session_state["planner_monthly_inputs"]
        if monthly_inputs.empty:
            st.info("No monthly model inputs are available. Load the inputs again to retry.")
            return

        exploratory_scores = calculate_exploratory_scores(monthly_inputs)

        st.subheader("12-Month Suitability Explorer")
        st.caption(
            "Exploratory reconstruction using 2025 observations. "
            "Environmental factors remain unreconciled with the team model. "
            "The team-reported April recommendation remains separate."
        )

        # Controls
        month_control, factor_control, adjustment_control = st.columns(3)

        with month_control:
            explorer_month = st.selectbox(
                "Explore month",
                exploratory_scores["Month"].tolist(),
                index=min(3, len(exploratory_scores) - 1),
                key="explorer_month",
            )

        with factor_control:
            adjusted_factor = st.selectbox(
                "Factor to adjust",
                ["Capacity", "Fiscal", "Air Quality", "Weather"],
                key="explorer_factor",
            )

        with adjustment_control:
            adjustment = st.select_slider(
                "Weight change (percentage points)",
                options=[-15, -10, 0, 10, 15],
                value=0,
                key="explorer_adjustment",
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

        # Three main panels, following the mockup.
        score_tile, breakdown_tile, comparison_tile = st.columns([1, 1.4, 1.4])

        with score_tile:
            with st.container(border=True):
                st.markdown(f"#### {explorer_month} Suitability")

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

        with breakdown_tile:
            with st.container(border=True):
                st.markdown("#### Weighted Calculation")
                st.dataframe(
                    breakdown.round(2),
                    hide_index=True,
                    use_container_width=True,
                )
                st.caption(
                    "Contribution = factor score × adjusted weight. "
                    "Weights total 100%; calculations use unrounded values."
                )

        with comparison_tile:
            with st.container(border=True):
                st.markdown("#### Monthly Comparison")
                # Use calendar order and prevent alphabetical sorting of month names.
                monthly_comparison = results.sort_values(
                    "Month",
                    key=lambda months: pd.to_datetime(months, format="%B").dt.month,
                ).set_index("Month")[["Baseline score", "Adjusted score"]]
                st.bar_chart(
                    monthly_comparison,
                    sort=False,
                    height=300,
                    stack=False,
                )
                st.caption(
                    "Baseline and adjusted results for all 12 months. "
                    "At zero adjustment, they are identical."
                )

        # Summarize this scenario, without claiming universal robustness.
        st.markdown("#### Key Takeaways")

        eligible = results.dropna(
            subset=["Baseline score", "Adjusted score"]
        )

        if eligible.empty:
            st.info("No complete monthly scores are available.")
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

            st.write(
                f"• Baseline score leader: **{', '.join(baseline_leaders)}** "
                f"({baseline_max:.2f})."
            )
            st.write(
                f"• Adjusted score leader: **{', '.join(adjusted_leaders)}** "
                f"({adjusted_max:.2f})."
            )

            if adjustment == 0:
                st.write(
                    "• Original weights are active. Move the slider "
                    "to explore sensitivity."
                )
            elif set(baseline_leaders) == set(adjusted_leaders):
                st.write(
                    "• The score leader is unchanged under this adjustment. "
                    "This supports stability for this scenario only."
                )
            else:
                st.write(
                    "• The score leader changes under this adjustment, "
                    "showing sensitivity to the selected weight."
                )

            st.write(
                f"• {adjusted_factor} weight: "
                f"**{original_weight:.0%} → {new_weight:.0%}**. "
                "Other weights change proportionally."
            )
            st.write(
                "• These rankings compare weighted scores only. "
                "Traffic/Energy coverage and event feasibility remain "
                "separate selection considerations."
            )

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