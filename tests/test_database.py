import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from apps.api.dependencies import get_telemetry_service
from apps.api.services.telemetry import TelemetryService
from apps.db import Database, DatabaseConfig, DatabaseHealthMonitor
from apps.db.session import normalise_url


@pytest.fixture()
def client(build_app):
    with TestClient(build_app()) as test_client:
        yield test_client


def test_bare_postgres_url_uses_psycopg_driver():
    # psycopg2 has no 32-bit ARM wheels, so the Pi must never fall back to it.
    assert normalise_url("postgresql://u:p@host/db").drivername == "postgresql+psycopg"
    assert normalise_url("postgres://u:p@host/db").drivername == "postgresql+psycopg"


def test_configured_url_keeps_the_password_out_of_responses():
    db = Database(DatabaseConfig(url="postgresql://user:secret@rds.example.com:5432/r2d2"))
    assert db.configured is True
    assert "secret" not in db.safe_url


def test_connection_settings_come_from_the_config_not_the_environment():
    db = Database(DatabaseConfig(url="postgresql://u:p@host/db", sslmode="verify-full"))
    args = db._connect_args()
    assert args["sslmode"] == "verify-full"
    assert args["connect_timeout"] == db.config.connect_timeout


def test_probe_failure_detail_hides_the_endpoint():
    # /health is unauthenticated, so the driver's error text - which names the
    # host and the database user - must not travel in the response.
    db = Database(
        DatabaseConfig(
            url="postgresql://r2d2:secret@127.0.0.1:1/r2d2", sslmode="", connect_timeout=2
        )
    )
    connected, detail = db.check()

    assert connected is False
    assert "Unreachable" in detail
    assert "127.0.0.1" not in detail
    assert "r2d2" not in detail
    assert "secret" not in detail
    db.dispose()


def test_health_monitor_reports_the_time_of_the_actual_probe(monkeypatch):
    db = Database(DatabaseConfig(url="postgresql://u:p@host/db"))
    monkeypatch.setattr(db, "check", lambda: (True, "Connected"))
    monitor = DatabaseHealthMonitor(db, interval_seconds=60)

    before = monitor.snapshot()
    assert before.connected is False
    assert before.detail == "Probe has not run yet"

    monitor.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not monitor.snapshot().connected:
            time.sleep(0.01)
        probed = monitor.snapshot()
    finally:
        monitor.stop()

    assert probed.connected is True
    assert probed.checked_at > before.checked_at


def test_health_monitor_does_not_start_a_thread_without_a_database(offline_database):
    monitor = DatabaseHealthMonitor(offline_database)
    monitor.start()
    try:
        assert monitor.running is False
        assert monitor.snapshot().configured is False
    finally:
        monitor.stop()


def test_health_reports_the_database_outside_components(client):
    payload = client.get("/health").json()

    assert payload["database"]["configured"] is False
    assert payload["database"]["connected"] is False
    # `status` is computed from `components`, so the database must stay out of
    # it - the vehicle is healthy without one.
    assert "database" not in payload["components"]


def test_status_endpoint_works_without_a_database(client):
    assert client.get("/status").status_code == 200


def test_telemetry_endpoints_are_unavailable_without_a_database(client):
    assert client.post("/telemetry/snapshot").status_code == 503
    assert client.get("/telemetry").status_code == 503


def test_only_database_failures_become_503(build_app):
    class BrokenTelemetry:
        configured = True

        def record_snapshot(self, snapshot):
            raise OperationalError("SELECT 1", {}, Exception("boom"))

        def recent(self, limit):
            raise KeyError("snapshot shape changed")

    app = build_app()
    app.dependency_overrides[get_telemetry_service] = BrokenTelemetry

    with TestClient(app, raise_server_exceptions=False) as test_client:
        assert test_client.post("/telemetry/snapshot").status_code == 503
        # A bug must not be dressed up as an uplink outage.
        assert test_client.get("/telemetry").status_code == 500


@pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="Set TEST_DATABASE_URL to run against a real Postgres",
)
def test_snapshot_round_trip(vehicle_service):
    db = Database(DatabaseConfig(url=os.environ["TEST_DATABASE_URL"], sslmode="disable"))
    service = TelemetryService(db)

    stored = service.record_snapshot(vehicle_service.snapshot())

    assert stored.id is not None
    assert stored.id in {event.id for event in service.recent(limit=10)}
    db.dispose()
