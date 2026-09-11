from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sparkcityx.database import check_database_connection, get_database_url


def test_database_url_comes_from_environment(monkeypatch) -> None:
    url = "postgresql://user:secret@database.example/sparkcity?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", url)
    assert get_database_url() == url


def test_missing_database_url_has_setup_guidance(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="secrets/.env"):
        get_database_url()


@pytest.mark.parametrize(
    "url",
    ["mysql://user:secret@example/db", "postgresql://USERNAME:PASSWORD@example/db"],
)
def test_database_url_rejects_invalid_configuration(url: str) -> None:
    with pytest.raises(ValueError):
        get_database_url(url)


@patch("sparkcityx.database.psycopg.connect")
def test_health_check_returns_only_safe_metadata(connect: MagicMock) -> None:
    cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("smartcity_db", "16.15", True)

    status = check_database_connection("postgresql://user:secret@example/db")

    assert status.as_dict() == {
        "database": "smartcity_db",
        "server_version": "16.15",
        "ssl_enabled": True,
    }
    connect.assert_called_once_with(
        "postgresql://user:secret@example/db",
        connect_timeout=10,
    )
