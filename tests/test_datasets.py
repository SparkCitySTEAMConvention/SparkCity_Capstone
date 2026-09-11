from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sparkcityx import load_dataset, validate_dataframe


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_CASES = {
    "traffic_sensors.csv": "traffic",
    "air_quality.json": "air_quality",
    "weather_data.json": "weather",
    "energy_meters.csv": "energy",
    "city_zones.csv": "city_zones",
}
GENERATED_CASES = {
    "traffic_sensors.csv": "traffic",
    "air_quality.json": "air_quality",
    "weather_data.parquet": "weather",
    "energy_meters.csv": "energy",
    "city_zones.csv": "city_zones",
    "occupancy_data.csv": "occupancy",
    "fiscal_data.csv": "fiscal",
}


@pytest.mark.parametrize(("filename", "dataset_type"), REFERENCE_CASES.items())
def test_checked_in_reference_dataset(spark, filename: str, dataset_type: str) -> None:
    df = load_dataset(spark, ROOT / "data" / "reference" / filename)
    report = validate_dataframe(df, dataset_type)
    assert report["valid"], report


@pytest.fixture(scope="session")
def generated_dir(tmp_path_factory) -> Path:
    output = tmp_path_factory.mktemp("generated-data")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate-data.py"),
         "--records", "24", "--seed", "42", "--output-dir", str(output)],
        check=True,
    )
    return output


@pytest.mark.parametrize(("filename", "dataset_type"), GENERATED_CASES.items())
def test_generated_dataset(
    spark, generated_dir: Path, filename: str, dataset_type: str
) -> None:
    df = load_dataset(spark, generated_dir / filename)
    report = validate_dataframe(df, dataset_type)
    assert report["record_count"] == 24
    assert report["valid"], report
