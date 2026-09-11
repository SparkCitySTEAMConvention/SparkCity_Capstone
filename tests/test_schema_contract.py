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
PROHIBITED_PATTERNS = {
    "drop": r"\bDROP\b",
    "truncate": r"\bTRUNCATE\b",
    "delete": r"\bDELETE\s+FROM\b",
    "update": r"\bUPDATE\s+\S+\s+SET\b",
    "insert": r"\bINSERT\s+INTO\b",
    "copy": r"\bCOPY\s+\S+\s+(?:FROM|TO)\b",
    "merge": r"\bMERGE\s+INTO\b",
    "select into": r"\bSELECT\b[\s\S]*?\bINTO\s+(?:TABLE\s+)?\S+",
    "create table as": r"\bCREATE\s+TABLE\b[\s\S]*?\bAS\s+SELECT\b",
}


def find_prohibited_operations(sql: str) -> list[str]:
    normalized = sql.upper()
    return [
        operation
        for operation, pattern in PROHIBITED_PATTERNS.items()
        if re.search(pattern, normalized)
    ]


def test_schema_migration_is_additive_and_idempotent() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    normalized = migration.upper()
    assert "CREATE SCHEMA IF NOT EXISTS SPARKCITY" in normalized
    assert normalized.count("CREATE TABLE IF NOT EXISTS") == 7
    assert find_prohibited_operations(migration) == []


def test_schema_migration_defines_expected_tables() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS sparkcity\.(\w+)", migration))
    assert tables == EXPECTED_TABLES


def test_safety_check_handles_whitespace_and_data_loading() -> None:
    unsafe_sql = """
        INSERT\nINTO example VALUES (1);
        COPY example\nFROM '/tmp/data.csv';
        MERGE\nINTO example USING source ON true;
        SELECT value\nINTO   TABLE copied FROM source;
    """
    assert set(find_prohibited_operations(unsafe_sql)) == {
        "insert", "copy", "merge", "select into"
    }
