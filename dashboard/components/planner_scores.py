"""Read the approved 2025 score exports without recalculating rounded totals."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
WEIGHTS = {"Capacity": 0.30, "Fiscal": 0.30, "Air Quality": 0.15,
           "Weather": 0.15, "Energy": 0.10}
FACTOR_COLUMNS = {"capacity": "Capacity", "fiscal": "Fiscal",
                  "air_quality": "Air Quality", "weather": "Weather", "energy": "Energy"}
FILES = {"Monthly": "monthly_scores_2025.csv", "Weekly": "weekly_scores_2025.csv",
         "Daily": "daily_scores_2025.csv"}


def load_scores(period, data_dir=DATA_DIR):
    frame = pd.read_csv(Path(data_dir) / FILES[period])
    date_column = "score_date" if period == "Daily" else "start_date"
    required = {date_column, "suitability", "suitability_rank", *FACTOR_COLUMNS}
    if not required.issubset(frame.columns):
        raise ValueError(f"{period} export is missing required columns.")
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    if frame[date_column].duplicated().any():
        raise ValueError(f"{period} export contains duplicate dates.")
    if not frame[date_column].dt.year.eq(2025).all():
        raise ValueError(f"{period} export contains dates outside 2025.")
    if period != "Daily":
        frame["end_date"] = pd.to_datetime(frame["end_date"], errors="raise")
    if period == "Weekly":
        if not ((frame["end_date"] - frame[date_column]).dt.days.eq(6)
                & frame[date_column].dt.dayofweek.eq(0)).all():
            raise ValueError("Weekly export must contain full Monday–Sunday weeks.")
    for column in [*FACTOR_COLUMNS, "suitability"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not (frame[column].isna() | frame[column].between(0, 100)).all():
            raise ValueError(f"Invalid score in {column}.")
    return frame.sort_values(date_column).reset_index(drop=True)


def monthly_explorer_scores(frame):
    scores = frame.rename(columns={**FACTOR_COLUMNS, "suitability": "Baseline score"}).copy()
    scores["Month"] = scores["start_date"].dt.month_name()
    return scores


def adjusted_scores(scores, adjustment):
    new_weight = WEIGHTS["Capacity"] + adjustment / 100
    if not 0 <= new_weight <= 1:
        raise ValueError("Capacity weight must be between zero and one.")
    weights = {factor: new_weight if factor == "Capacity" else
               weight * (1 - new_weight) / (1 - WEIGHTS["Capacity"])
               for factor, weight in WEIGHTS.items()}
    # Preserve authoritative exported totals at zero; inputs in CSV are rounded.
    if adjustment == 0:
        return scores["Baseline score"].copy(), weights
    result = sum(scores[factor] * weight for factor, weight in weights.items())
    return result, weights
