"""Safe shared PostgreSQL connection utilities."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.conninfo import conninfo_to_dict


@dataclass(frozen=True)
class DatabaseStatus:
    """Non-sensitive metadata returned by the database health check."""

    database: str
    server_version: str
    ssl_enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_database_url(database_url: str | None = None) -> str:
    """Return an explicit URL or ``DATABASE_URL`` without logging its contents."""
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to secrets/.env and add "
            "the instructor-provided credentials."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL must use the postgresql:// URL format")
    if "USERNAME" in url or "PASSWORD" in url:
        raise ValueError("DATABASE_URL still contains placeholder credentials")
    sslmode = conninfo_to_dict(url).get("sslmode")
    if sslmode not in {"require", "verify-ca", "verify-full"}:
        raise ValueError(
            "DATABASE_URL must set sslmode=require, verify-ca, or verify-full"
        )
    return url


def connect_database(
    database_url: str | None = None,
    *,
    connect_timeout: int = 10,
) -> Connection:
    """Open a PostgreSQL connection using the shared URL convention."""
    return psycopg.connect(
        get_database_url(database_url),
        connect_timeout=connect_timeout,
    )


def check_database_connection(database_url: str | None = None) -> DatabaseStatus:
    """Run a read-only health check and return non-sensitive server metadata."""
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_setting('server_version'),
                    EXISTS (
                        SELECT 1
                        FROM pg_stat_ssl
                        WHERE pid = pg_backend_pid() AND ssl
                    )
                """
            )
            database, server_version, ssl_enabled = cursor.fetchone()
    if not ssl_enabled:
        raise RuntimeError("PostgreSQL health check failed: SSL is not enabled")
    return DatabaseStatus(database, server_version, ssl_enabled)
