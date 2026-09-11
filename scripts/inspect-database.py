#!/usr/bin/env python3
"""List SparkCity tables and row counts without modifying the database."""

from __future__ import annotations

import argparse
from pathlib import Path

from psycopg import sql
from dotenv import load_dotenv

from sparkcityx.database import connect_database


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / "secrets" / ".env",
        help="Ignored environment file containing DATABASE_URL",
    )
    args = parser.parse_args()
    if args.env_file.exists():
        load_dotenv(args.env_file, override=False)

    with connect_database() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'sparkcity' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            table_names = [row[0] for row in cursor.fetchall()]
            print(f"sparkcity tables: {len(table_names)}")
            for table_name in table_names:
                cursor.execute(
                    sql.SQL("SELECT count(*) FROM {}.{}").format(
                        sql.Identifier("sparkcity"), sql.Identifier(table_name)
                    )
                )
                print(f"{table_name}: {cursor.fetchone()[0]} rows")


if __name__ == "__main__":
    main()
