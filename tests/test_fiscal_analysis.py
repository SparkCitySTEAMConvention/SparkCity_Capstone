import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from sparkcityx.fiscal_analysis import (
    MEASURES, EVENT_START, EVENT_END, validate_fiscal, daily_summary,
    monthly_summary, calendar_analogues, prior_only_flags,
    matched_week_comparisons, trend_statistics,
)


def observations(days=60, start="2025-03-01"):
    return pd.DataFrame({"sensor_id": "test", "timestamp": pd.date_range(start, periods=days),
                         "revenue": np.arange(days, dtype=float) + 100,
                         "expense": 25., "location_lat": 40., "location_lon": -73.})


@pytest.mark.parametrize("case", ["empty", "missing", "null", "blank", "nan", "inf", "string", "bool", "negative", "coordinate", "duplicate", "timestamp"])
def test_invalid_inputs(case):
    frame = observations()
    if case == "empty": frame = frame.iloc[:0]
    if case == "missing": frame = frame.drop(columns="expense")
    if case == "null": frame.loc[0, "sensor_id"] = None
    if case == "blank": frame.loc[0, "sensor_id"] = "\t "
    if case == "nan": frame.loc[0, "revenue"] = np.nan
    if case == "inf": frame.loc[0, "revenue"] = np.inf
    if case == "string": frame["revenue"] = "100"
    if case == "bool": frame["revenue"] = True
    if case == "negative": frame.loc[0, "expense"] = -1
    if case == "coordinate": frame.loc[0, "location_lat"] = 95
    if case == "duplicate": frame = pd.concat([frame, frame.iloc[:1]])
    if case == "timestamp": frame["timestamp"] = "invalid"
    with pytest.raises((ValueError, TypeError)):
        validate_fiscal(frame)


def test_daily_arithmetic_gap_and_month_coverage():
    frame = validate_fiscal(observations(days=40, start="2025-01-01"))
    daily = daily_summary(frame)
    assert np.allclose(daily.net_per_observation, daily.revenue - daily.expense)
    assert daily.revenue_rolling_7d.iloc[:6].isna().all()
    missing = daily_summary(frame.drop(index=10))
    assert pd.isna(missing.loc["2025-01-11", "observations"])
    assert missing.loc["2025-01-11":"2025-01-17", "revenue_rolling_7d"].isna().all()
    month = monthly_summary(frame)
    assert bool(month.loc["2025-01", "complete_month"])
    assert not bool(month.loc["2025-02", "complete_month"])
    assert month.loc["2025-02", "observed_days"] == 9


def test_prior_only_flags_do_not_use_current_or_future():
    daily = daily_summary(validate_fiscal(observations()))
    before = prior_only_flags(daily)
    daily.loc[daily.index[40]:, "revenue"] += 10000
    after = prior_only_flags(daily)
    pd.testing.assert_frame_equal(before[before.day < daily.index[40]], after[after.day < daily.index[40]])
    row = after[(after.day == daily.index[40]) & (after.metric == "revenue")].iloc[0]
    original = before[(before.day == daily.index[40]) & (before.metric == "revenue")].iloc[0]
    assert row.prior_median == original.prior_median
    assert row.review_flag
    constant = daily.copy()
    constant[MEASURES] = 1.
    assert not prior_only_flags(constant).assessed.any()


def test_all_candidate_windows_fair_rules_and_missing_days():
    assert EVENT_START.day_name() == "Tuesday" and EVENT_END.day_name() == "Thursday"
    daily = daily_summary(validate_fiscal(observations(days=30, start="2025-04-01")))
    windows, comparison = calendar_analogues(daily)
    assert len(windows) == 20 and len(comparison) == 15
    assert comparison.analogue_windows.eq(4).all()
    assert windows[windows.selected].historical_start.tolist() == ["2025-04-01", "2025-04-08", "2025-04-15", "2025-04-22"]
    assert windows[windows.selected].weekend_days.eq(0).all()
    assert (windows.historical_start <= "2025-04-28").all()
    daily.loc["2025-04-03", MEASURES] = np.nan
    remaining, _ = calendar_analogues(daily)
    assert len(remaining[remaining.selected]) == 3
    assert "2025-04-01" not in remaining[remaining.selected].historical_start.tolist()


def test_weighting_and_complete_week_rules():
    frame = validate_fiscal(observations(days=30, start="2025-04-01"))
    extra = frame.iloc[[1]].assign(sensor_id="extra", revenue=1000., net_per_observation=975.)
    daily = daily_summary(pd.concat([frame, extra]))
    windows, _ = calendar_analogues(daily)
    first = windows[(windows.selected) & (windows.historical_start == "2025-04-01")].iloc[0]
    assert np.isclose(first.revenue, (100 + 101 + 1000 + 102) / 4)
    assert first.observations == 4
    assert matched_week_comparisons(daily).week_start.nunique() == 3
    daily.loc["2025-04-08", "revenue"] = np.nan
    assert matched_week_comparisons(daily).week_start.nunique() == 2


def test_calendar_analogues_explicit_dates_match_a_different_month_and_leave_defaults_intact():
    """An explicit-date caller (e.g. an interactive "try another date" tool) must
    get the identical methodology applied to its own month, without touching the
    pinned module constants used by every other caller (the notebook, its tests)."""
    daily = daily_summary(validate_fiscal(observations(days=31, start="2025-07-01")))
    windows, comparison = calendar_analogues(
        daily, event_start="2027-07-07", event_end="2027-07-09",
        candidate_start="2027-07-07", candidate_end="2027-07-13",
    )
    assert (windows.historical_start.str.startswith("2025-07")).all()
    assert windows[windows.selected].historical_start.tolist() == \
        ["2025-07-02", "2025-07-09", "2025-07-16", "2025-07-23"]
    # Calling again with no explicit dates still reproduces the pinned April behavior.
    april_daily = daily_summary(validate_fiscal(observations(days=30, start="2025-04-01")))
    default_windows, _ = calendar_analogues(april_daily)
    assert default_windows[default_windows.selected].historical_start.tolist() == \
        ["2025-04-01", "2025-04-08", "2025-04-15", "2025-04-22"]


def test_calendar_analogues_rejects_month_with_no_history():
    daily = daily_summary(validate_fiscal(observations(days=30, start="2025-04-01")))
    with pytest.raises(ValueError, match="No complete historical August 2025"):
        calendar_analogues(daily, event_start="2027-08-03", event_end="2027-08-05",
                            candidate_start="2027-08-03", candidate_end="2027-08-09")


def test_trend_known_slope():
    stats = trend_statistics(daily_summary(validate_fiscal(observations()))).set_index("metric")
    assert np.isclose(stats.loc["revenue", "slope_source_units_per_day"], 1)
    assert np.isclose(stats.loc["revenue", "r_squared"], 1)
    assert pd.isna(stats.loc["expense", "r_squared"])


def test_notebook_code_compiles():
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/Hakeem_fiscal_analysis.ipynb").read_text())
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"fiscal-cell-{index}", "exec")


def scenario_fixture(path):
    import hashlib
    assumptions = {"attendees": 15000, "durations_days": [3],
                   "venue_archetypes": {k: {} for k in ["A", "B", "C"]},
                   "weather_conditions": {k: {} for k in ["Comfortable/dry", "Hot/dry", "Wet"]}}
    raw = json.dumps(assumptions).encode()
    (path / "assumptions.json").write_bytes(raw)
    (path / "manifest.json").write_text(json.dumps({"status": "complete", "day3_context_run": "fixture",
        "assumptions_sha256": hashlib.sha256(raw).hexdigest(), "draws_per_scenario": 2}))
    rows = []
    for venue in assumptions["venue_archetypes"]:
        for weather in assumptions["weather_conditions"]:
            for draw in range(2):
                rows.append({"venue": venue, "weather": weather, "draw": draw,
                             "scenario_id": venue + weather, "duration_days": 3, "attendee_days": 45000,
                             "potential_gross_visitor_receipts": 100. + draw,
                             "potential_retained_gross_spending": 75. + draw,
                             "organizer_cost": 20. + draw})
    pd.DataFrame(rows).to_parquet(path / "simulation_draws.parquet")


def test_scenario_duplicates_are_not_extra_evidence(tmp_path):
    from sparkcityx.fiscal_analysis import convention_fiscal_scenarios
    scenario_fixture(tmp_path)
    summary, _ = convention_fiscal_scenarios(tmp_path, "fixture")
    assert len(summary) == 9
    assert summary.draws.eq(2).all()  # Not six after pooling duplicate weather draws.
    assert np.isclose(summary.iloc[0].p50, 100.5)
    with pytest.raises(ValueError, match="lineage"):
        convention_fiscal_scenarios(tmp_path, "wrong")


@pytest.mark.parametrize("change", ["missing_weather", "different_weather_value", "assumptions"])
def test_changed_scenarios_rejected(tmp_path, change):
    from sparkcityx.fiscal_analysis import convention_fiscal_scenarios
    scenario_fixture(tmp_path)
    draws = pd.read_parquet(tmp_path / "simulation_draws.parquet")
    if change == "missing_weather":
        draws = draws[draws.weather != "Wet"]
    if change == "different_weather_value":
        draws.loc[draws.weather == "Wet", "organizer_cost"] += 1
    if change == "assumptions":
        (tmp_path / "assumptions.json").write_text('{"attendees":1}')
    draws.to_parquet(tmp_path / "simulation_draws.parquet")
    with pytest.raises(ValueError):
        convention_fiscal_scenarios(tmp_path, "fixture")
