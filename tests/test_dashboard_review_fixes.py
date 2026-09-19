"""Regression coverage for dashboard integrity and connection contracts."""

import hashlib
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from pages.convention_planner import get_planner_engine
from pages.fiscal_impact import (
    FISCAL_RUNS_DIR,
    _combined_event_impact,
    _complete_2025_months,
    _explorer_summary,
    _load_run,
    _load_occupancy_snapshot,
    _monthly_fiscal_index,
    _monthly_occupancy_context,
    _verify_run_artifacts,
)


def test_fiscal_dashboard_snapshot_is_packaged_and_loadable():
    """A fresh clone must include everything needed to render Fiscal Impact."""
    assert FISCAL_RUNS_DIR.is_relative_to(ROOT / "dashboard" / "data")
    _load_run.clear()
    data = _load_run()

    assert data is not None
    assert data["manifest"]["status"] == "complete"
    assert not data["monthly"].empty
    assert not data["daily"].empty


def test_fiscal_explorer_responds_to_season_in_shared_data():
    """The primary explorer outputs must change when its selected month changes."""
    _load_run.clear()
    daily = _load_run()["daily"]

    winter = _explorer_summary(daily, date(2027, 1, 5), 3)
    summer = _explorer_summary(daily, date(2027, 6, 8), 3)

    assert summer.loc["revenue", "mean"] > winter.loc["revenue", "mean"]
    assert summer.loc["net_per_observation", "mean"] > winter.loc[
        "net_per_observation", "mean"
    ]


def test_occupancy_context_uses_shared_monthly_snapshot_without_inventory_claim():
    _load_occupancy_snapshot.clear()
    occupancy = _load_occupancy_snapshot()
    january = _monthly_occupancy_context(occupancy, 1)
    june = _monthly_occupancy_context(occupancy, 6)

    assert len(occupancy) == 12
    assert june["occupancy_rate"] > january["occupancy_rate"]
    assert june["pressure_index"] > january["pressure_index"]
    assert "available_rooms_observation" in june


def test_combined_event_impact_uses_fiscal_index_only_for_variable_spending():
    _load_run.clear()
    monthly = _load_run()["monthly"]
    january_index = _monthly_fiscal_index(monthly, 1)
    june_index = _monthly_fiscal_index(monthly, 6)

    january = _combined_event_impact(15_000, 3, "Planning", january_index)
    june = _combined_event_impact(15_000, 3, "Planning", june_index)

    assert june_index > january_index
    assert june["indexed_nonhotel"] > january["indexed_nonhotel"]
    assert june["visitor_activity"] > january["visitor_activity"]
    assert june["hotel_spending"] == january["hotel_spending"]
    assert june["organizer_cost"] == january["organizer_cost"]


def test_custom_javits_proposal_replaces_scenario_allowance():
    impact = _combined_event_impact(
        15_000, 3, "Planning", fiscal_index=1.0, facility_allowance=625_000,
    )

    assert impact["venue_cost"] == 625_000
    assert impact["organizer_cost"] == 625_000 + 15_000 * 3 * 35
    assert impact["organizer_cost_per_attendee"] == pytest.approx(146.6666667)


def test_fiscal_dashboard_verifies_signed_artifacts(tmp_path):
    artifact = tmp_path / "monthly.csv"
    artifact.write_text("month,value\n2025-04,1\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    _verify_run_artifacts(tmp_path, {"artifacts_sha256": {"monthly.csv": digest}}, ("monthly.csv",))

    artifact.write_text("month,value\n2025-04,2\n")
    with pytest.raises(ValueError, match="integrity verification"):
        _verify_run_artifacts(tmp_path, {"artifacts_sha256": {"monthly.csv": digest}}, ("monthly.csv",))


def test_fiscal_ranking_excludes_partial_or_out_of_year_months():
    monthly = pd.DataFrame({
        "month": ["2025-01", "2025-04", "2026-01"],
        "complete_month": [True, True, False],
        "net_per_observation": [100.0, 200.0, 999.0],
    })

    comparable = _complete_2025_months(monthly)

    assert comparable["month"].tolist() == ["2025-01", "2025-04"]
    assert comparable.loc[comparable["net_per_observation"].idxmax(), "month"] == "2025-04"


@pytest.mark.parametrize("sslmode", ["disable", "prefer"])
def test_planner_rejects_unencrypted_database_urls(sslmode):
    get_planner_engine.clear()
    with pytest.raises(ValueError, match="sslmode"):
        get_planner_engine(f"postgresql://user:secret@example/db?sslmode={sslmode}")
