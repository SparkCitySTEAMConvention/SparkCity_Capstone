#!/usr/bin/env python3
"""Preview or apply the additive SparkCity PostgreSQL schema migration."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from sparkcityx.database import connect_database


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "001_create_sparkcity_schema.sql"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / "secrets" / ".env",
        help="Environment file supplying DATABASE_URL when --apply is used",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the migration; without this flag, only show the plan",
    )
    args = parser.parse_args()

    print(f"Migration: {MIGRATION.relative_to(ROOT)}")
    print("Target schema: sparkcity")
    print("Tables: 7")
    print("Destructive statements: none")
    if not args.apply:
        print("Preview only; rerun with --apply after review.")
        return

    if args.env_file.exists():
        load_dotenv(args.env_file, override=False)
    with connect_database() as connection:
        connection.execute(MIGRATION.read_text(encoding="utf-8"))
    print("Schema migration applied successfully.")


if __name__ == "__main__":
    main()
