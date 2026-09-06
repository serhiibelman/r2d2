"""Tests for the connection layer in `lib/db`.

There is no model and no migration yet, so nothing here needs a live database.
"""

import os

import pytest

from lib.db import Database, DatabaseConfig, normalise_url


def test_bare_postgres_url_uses_psycopg_driver():
    # psycopg2 has no 32-bit ARM wheels, so the Pi must never fall back to it.
    assert normalise_url("postgresql://u:p@host/db").drivername == "postgresql+psycopg"
    assert normalise_url("postgres://u:p@host/db").drivername == "postgresql+psycopg"


def test_an_empty_url_leaves_the_database_switched_off():
    db = Database(DatabaseConfig(url=""))

    assert db.configured is False
    assert db.safe_url is None
    with pytest.raises(RuntimeError):
        db.engine


def test_configured_url_keeps_the_password_out_of_responses():
    db = Database(DatabaseConfig(url="postgresql://user:secret@rds.example.com:5432/r2d2"))

    assert db.configured is True
    assert "secret" not in db.safe_url


def test_connection_settings_come_from_the_config_not_the_environment():
    db = Database(DatabaseConfig(url="postgresql://u:p@host/db", sslmode="verify-full"))

    args = db._connect_args()

    assert args["sslmode"] == "verify-full"
    assert args["connect_timeout"] == db.config.connect_timeout
    assert args["options"] == f"-c statement_timeout={db.config.statement_timeout_ms}"


def test_probe_failure_detail_hides_the_endpoint():
    # Driver errors name the host and the database user; the detail is meant to
    # be safe to hand to a caller, so the full text belongs in the log only.
    db = Database(
        DatabaseConfig(
            url="postgresql://r2d2:secret@127.0.0.1:1/r2d2", sslmode="", connect_timeout=2
        )
    )

    connected, detail = db.check()

    assert connected is False
    assert "Unreachable" in detail
    assert "127.0.0.1" not in detail
    assert "secret" not in detail
    db.dispose()


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run against a real Postgres",
)
def test_check_succeeds_against_a_real_database():
    db = Database(DatabaseConfig(url=os.environ["TEST_DATABASE_URL"], sslmode="disable"))

    connected, detail = db.check()

    assert connected is True
    assert detail == "Connected"
    db.dispose()
