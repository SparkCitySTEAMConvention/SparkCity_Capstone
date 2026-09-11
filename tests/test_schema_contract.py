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
FORBIDDEN_STATEMENT_PATTERNS = (
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bDELETE\b",
    r"\bUPDATE\b",
    r"\bINSERT\b",
    r"\bCOPY\b",
    r"\bMERGE\b",
    r"\bSELECT\b[\s\S]*?\bINTO\b",
    r"\bCREATE\s+TABLE\b[\s\S]*?\bAS\s+SELECT\b",
)


def _without_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*[\s\S]*?\*/", "", sql)
    return re.sub(r"--[^\n]*", "", sql)


def test_schema_migration_is_additive_and_idempotent() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    migration = _without_sql_comments(migration)
    normalized = migration.upper()
    assert "CREATE SCHEMA IF NOT EXISTS SPARKCITY" in normalized
    assert normalized.count("CREATE TABLE IF NOT EXISTS") == 7
    for pattern in FORBIDDEN_STATEMENT_PATTERNS:
        assert re.search(pattern, migration, flags=re.IGNORECASE) is None


def test_schema_migration_defines_expected_tables() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS sparkcity\.(\w+)", migration))
    assert tables == EXPECTED_TABLES
