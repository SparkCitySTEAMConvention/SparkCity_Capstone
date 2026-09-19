"""Descriptive fiscal analysis; no database writes or event-effect estimation."""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

EVENT_START = pd.Timestamp("2027-04-06")
EVENT_END = pd.Timestamp("2027-04-08")
CANDIDATE_START = pd.Timestamp("2027-04-06")
CANDIDATE_END = pd.Timestamp("2027-04-12")
MEASURES = ["revenue", "expense", "net_per_observation"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _shift_day(day, days):
    # Native calendar arithmetic avoids pandas 2.x / NumPy 2.5 generic-timedelta warnings.
    return pd.Timestamp(day.to_pydatetime() + timedelta(days=int(days)))


def validate_fiscal(frame):
    required = ["sensor_id", "timestamp", "revenue", "expense", "location_lat", "location_lon"]
    if frame.empty or not set(required).issubset(frame.columns):
        raise ValueError("Nonempty fiscal input with all required fields is required")
    frame = frame[required].copy()
    if frame.isna().any().any():
        raise ValueError("Missing fiscal values")
    if not frame.sensor_id.map(lambda s: isinstance(s, str) and bool(s.strip())).all():
        raise ValueError("Blank or nontext sensor identifier")
    frame["timestamp"] = pd.to_datetime(frame.timestamp, errors="raise")
    if frame.timestamp.isna().any() or frame.timestamp.dt.tz is not None:
        raise ValueError("Expected nonmissing source wall-clock timestamps; do not silently convert timezone")
    for col in required[2:]:
        if not pd.api.types.is_numeric_dtype(frame[col]) or pd.api.types.is_bool_dtype(frame[col]):
            raise ValueError("Nonnumeric field: " + col)
        if not np.isfinite(frame[col]).all():
            raise ValueError("Nonfinite field: " + col)
    if (frame[["revenue", "expense"]] < 0).any().any():
        raise ValueError("Negative revenue/expense under current source contract")
    if not frame.location_lat.between(-90, 90).all() or not frame.location_lon.between(-180, 180).all():
        raise ValueError("Invalid coordinates")
    if frame.duplicated(["sensor_id", "timestamp"]).any():
        raise ValueError("Duplicate sensor/timestamp key")
    frame["net_per_observation"] = frame.revenue - frame.expense
    frame["day"] = frame.timestamp.dt.normalize()
    return frame.sort_values(["timestamp", "sensor_id"]).reset_index(drop=True)


def daily_summary(frame):
    grouped = frame.groupby("day", sort=True)
    daily = grouped.agg(observations=("sensor_id", "size"), sensors=("sensor_id", "nunique"))
    for col in MEASURES:
        daily[col] = grouped[col].mean()
        daily[col + "_median"] = grouped[col].median()
    daily["negative_share"] = grouped.net_per_observation.agg(lambda x: float((x < 0).mean()))
    # Insert missing calendar days explicitly; rolling windows must not bridge gaps silently.
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D", name="day"))
    daily["weekday"] = daily.index.day_name()
    daily["month"] = daily.index.to_period("M").astype(str)
    for col in MEASURES:
        for days in (7, 30):
            daily[f"{col}_rolling_{days}d"] = daily[col].rolling(days, min_periods=days).mean()
    return daily


def monthly_summary(frame):
    data = frame.assign(month=frame.timestamp.dt.to_period("M").astype(str))
    result = data.groupby("month").agg(observations=("sensor_id", "size"),
        observed_days=("day", "nunique"), revenue=("revenue", "mean"), expense=("expense", "mean"),
        net_per_observation=("net_per_observation", "mean"))
    result["calendar_days"] = [pd.Period(m).days_in_month for m in result.index]
    result["complete_month"] = result.observed_days == result.calendar_days
    return result


def trend_statistics(daily):
    rows = []
    for metric in MEASURES:
        series = daily[metric].dropna()
        if len(series) < 2:
            raise ValueError("At least two observed days required for trend summaries")
        x = (series.index - series.index.min()).days.to_numpy(dtype=float)
        y = series.to_numpy()
        slope, intercept = np.polyfit(x, y, 1)
        residual = float(np.sum((y - (intercept + slope * x)) ** 2))
        total = float(np.sum((y - y.mean()) ** 2))
        rows.append({"metric": metric, "observed_days": len(y), "slope_source_units_per_day": slope,
                     "r_squared": 1 - residual / total if total > 0 else np.nan,
                     "first_30_calendar_days_mean": series.loc[:_shift_day(series.index.min(), 29)].mean(),
                     "last_30_calendar_days_mean": series.loc[_shift_day(series.index.max(), -29):].mean()})
    return pd.DataFrame(rows)


def prior_only_flags(daily, history_days=28, threshold=3.5):
    """Past-only MAD review score; uncalibrated, not a false-positive probability."""
    rows = []
    for metric in MEASURES:
        values = daily[metric]
        for index in range(len(values)):
            history = values.iloc[max(0, index-history_days):index]
            center, scale, score = np.nan, np.nan, np.nan
            if len(history) == history_days and history.notna().all() and pd.notna(values.iloc[index]):
                center = float(history.median())
                scale = float(np.median(np.abs(history - center)))
                if scale > 0:
                    score = 0.67448975 * (values.iloc[index] - center) / scale
            rows.append({"day": values.index[index], "metric": metric, "value": values.iloc[index],
                         "prior_median": center, "prior_mad": scale, "review_score": score,
                         "assessed": bool(np.isfinite(score)),
                         "review_flag": bool(np.isfinite(score) and abs(score) > threshold)})
    return pd.DataFrame(rows)


def calendar_analogues(daily, historical_year=2025, *, event_start=None, event_end=None,
                        candidate_start=None, candidate_end=None):
    """Equal-duration comparison of every possible start in a candidate window.

    Uses complete same-weekday sequences wholly inside the historical month matching
    `event_start`'s calendar month. These are historical analogue windows, not
    forecasts, independent experiments or confidence intervals.

    `event_start`/`event_end`/`candidate_start`/`candidate_end` default to this
    module's pinned planning constants, so existing callers (the notebook, its
    tests) are unaffected. Passing explicit values lets a caller (e.g. an
    interactive "try another date" tool) run the identical, audited methodology
    against a different candidate window without touching the pinned constants —
    every window is scored the same way; none is special-cased.
    """
    event_start = EVENT_START if event_start is None else pd.Timestamp(event_start)
    event_end = EVENT_END if event_end is None else pd.Timestamp(event_end)
    candidate_start = CANDIDATE_START if candidate_start is None else pd.Timestamp(candidate_start)
    candidate_end = CANDIDATE_END if candidate_end is None else pd.Timestamp(candidate_end)
    rows = []
    duration = (event_end - event_start).days + 1
    history = daily[(daily.index.year == historical_year) & (daily.index.month == event_start.month)]
    for candidate in pd.date_range(candidate_start, _shift_day(candidate_end, 1-duration)):
        end = _shift_day(candidate, duration-1)
        for day in history.index[history.index.weekday == candidate.weekday()]:
            dates = pd.date_range(day, periods=duration)
            if not dates.isin(history.index).all():
                continue
            window = history.loc[dates]
            if window[MEASURES + ["observations"]].isna().any().any():
                continue
            weights = window.observations.to_numpy()
            rows.append({"candidate_start": candidate.date().isoformat(),
                         "candidate_end": end.date().isoformat(),
                         "selected": candidate == event_start,
                         "weekend_days": sum(d.weekday() >= 5 for d in pd.date_range(candidate, end)),
                         "historical_start": day.date().isoformat(),
                         "observations": int(weights.sum()),
                         **{m: float(np.average(window[m], weights=weights)) for m in MEASURES}})
    windows = pd.DataFrame(rows)
    if windows.empty:
        month_label = pd.Timestamp(year=historical_year, month=event_start.month, day=1).strftime("%B %Y")
        raise ValueError(f"No complete historical {month_label} analogue windows")
    summary = []
    for candidate in pd.date_range(candidate_start, _shift_day(candidate_end, 1-duration)):
        start = candidate.date().isoformat()
        group = windows[windows.candidate_start == start]
        for metric in MEASURES:
            summary.append({"candidate_start": start, "candidate_end": _shift_day(candidate, duration-1).date().isoformat(),
                            "selected": candidate == event_start, "metric": metric,
                            "analogue_windows": len(group),
                            "mean": group[metric].mean(), "minimum": group[metric].min(),
                            "maximum": group[metric].max()})
    return windows, pd.DataFrame(summary)


def matched_week_comparisons(daily):
    """Descriptive weekend-minus-weekday differences, retaining complete weeks only."""
    rows = []
    weeks = daily.index - pd.to_timedelta(daily.index.weekday, unit="D")
    for monday, group in daily.groupby(weeks):
        if len(group) != 7 or group[MEASURES].isna().any().any():
            continue
        for metric in MEASURES:
            rows.append({"week_start": monday, "metric": metric,
                         "weekend_minus_weekday": group.loc[group.index.weekday >= 5, metric].mean()
                         - group.loc[group.index.weekday < 5, metric].mean()})
    return pd.DataFrame(rows)


def convention_fiscal_scenarios(path, expected_day3_run):
    """Reuse saved three-day assumptions without recalibrating them from fiscal readings."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    raw = (path / "assumptions.json").read_bytes()
    assumptions = json.loads(raw)
    if manifest.get("status") != "complete" or manifest.get("day3_context_run") != expected_day3_run:
        raise ValueError("Convention context differs from the fiscal source lineage")
    if hashlib.sha256(raw).hexdigest() != manifest["assumptions_sha256"]:
        raise ValueError("Convention assumptions changed")
    if assumptions["attendees"] != 15000 or 3 not in assumptions["durations_days"]:
        raise ValueError("Scenario assumptions do not match attendee count/duration")
    metrics = ["potential_gross_visitor_receipts", "potential_retained_gross_spending", "organizer_cost"]
    draws = pd.read_parquet(path / "simulation_draws.parquet")
    draws = draws[draws.duration_days == 3]
    if draws.scenario_id.nunique() != 9 or set(draws.venue) != set(assumptions["venue_archetypes"]):
        raise ValueError("Expected all nine three-day cases")
    rows = []
    for venue, cases in draws.groupby("venue"):
        if set(cases.weather) != set(assumptions["weather_conditions"]):
            raise ValueError("Missing weather cases")
        reference = cases[cases.weather == "Comfortable/dry"].sort_values("draw")
        if len(reference) != manifest["draws_per_scenario"] or reference.draw.duplicated().any():
            raise ValueError("Missing/duplicate draws")
        if not np.isfinite(reference[metrics].to_numpy()).all() or (reference[metrics] < 0).any().any():
            raise ValueError("Invalid fiscal simulation values")
        if not reference.attendee_days.eq(15000 * 3).all():
            raise ValueError("Scenario attendee-day mismatch")
        for weather, other in cases.groupby("weather"):
            other = other.sort_values("draw")
            if not np.array_equal(reference.draw.to_numpy(), other.draw.to_numpy()) or not np.allclose(reference[metrics], other[metrics]):
                raise ValueError("Weather-dependent fiscal draws require explicit scenario comparison")
        # Weather duplicates are not independent evidence and must not triple sample size.
        for metric in metrics:
            q = reference[metric].quantile([.1, .5, .9])
            rows.append({"venue_archetype": venue, "metric": metric, "p10": q.loc[.1],
                         "p50": q.loc[.5], "p90": q.loc[.9], "draws": len(reference),
                         "interpretation": "Authored assumption quantiles, not forecast confidence intervals"})
    return pd.DataFrame(rows), assumptions
