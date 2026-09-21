"""Shared convention scenario used across the SparkCity dashboard."""

from datetime import date


# ------------------------------------------------------------------
# TEAM CONVENTION RECOMMENDATION
# ------------------------------------------------------------------

EVENT_START_DATE = date(2027, 11, 3)
EVENT_END_DATE = date(2027, 11, 5)
EVENT_DURATION_DAYS = (EVENT_END_DATE - EVENT_START_DATE).days + 1
EVENT_ATTENDEES = 15_000

RECOMMENDED_MONTH = "November"
ALTERNATIVE_MONTH = "October"


# ------------------------------------------------------------------
# HISTORICAL BASELINE
# ------------------------------------------------------------------
# The proposed convention is in 2027, but our analysis uses the
# historical data available in the SparkCity database.

BASELINE_YEAR = 2025


# ------------------------------------------------------------------
# DERIVED VALUES
# ------------------------------------------------------------------

EVENT_MONTH_NUM = EVENT_START_DATE.month
EVENT_MONTH_ABBR = EVENT_START_DATE.strftime("%b")
EVENT_MONTH_NAME = EVENT_START_DATE.strftime("%B")

EVENT_DATE_LABEL = (
    f"{EVENT_START_DATE.strftime('%B')} "
    f"{EVENT_START_DATE.day}–{EVENT_END_DATE.day}, "
    f"{EVENT_START_DATE.year}"
)

EVENT_DAYS_LABEL = (
    f"{EVENT_START_DATE.strftime('%a')}–"
    f"{EVENT_END_DATE.strftime('%a')}"
)