"""Regression coverage for dashboard integrity and connection contracts."""

import hashlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from pages.convention_planner import get_planner_engine
from pages.fiscal_impact import (
    FISCAL_RUNS_DIR,
    _complete_2025_months,
    _load_run,
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
    assert not data["candidates"].empty
    assert not data["daily"].empty


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
