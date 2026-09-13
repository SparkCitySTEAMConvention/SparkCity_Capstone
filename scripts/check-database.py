#!/usr/bin/env python3
"""Verify the shared PostgreSQL connection without reading application data."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from sparkcityx.database import check_database_connection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path("secrets/.env"),
        help="Ignored environment file containing DATABASE_URL",
    )
    args = parser.parse_args()

    if args.env_file.exists():
        load_dotenv(args.env_file, override=False)

    status = check_database_connection()
    print("PostgreSQL connection: OK")
    print(f"Database: {status.database}")
    print(f"Server version: {status.server_version}")
    print(f"SSL: {'enabled' if status.ssl_enabled else 'disabled'}")


if __name__ == "__main__":
    main()
