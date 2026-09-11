from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "001_create_sparkcity_schema.sql"
EXPECTED_TABLES = {
    "air_quality",
    "city_zones",
    "energy_meters",
    "fiscal_data",
    "occupancy_data",
    "traffic_sensors",
    "weather_data",
}


def test_schema_migration_is_additive_and_idempotent() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    normalized = migration.upper()
    assert "CREATE SCHEMA IF NOT EXISTS SPARKCITY" in normalized
    assert normalized.count("CREATE TABLE IF NOT EXISTS") == 7
    for destructive_keyword in ("DROP ", "TRUNCATE ", "DELETE ", "UPDATE "):
        assert destructive_keyword not in normalized


def test_schema_migration_defines_expected_tables() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS sparkcity\.(\w+)", migration))
    assert tables == EXPECTED_TABLES
