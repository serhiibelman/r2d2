"""Tests for the MQTT publisher in `lib/telemetry`.

A fake connection stands in for AWS IoT, so nothing here needs the network,
a certificate or the `awscrt` extension.
"""

import json
from datetime import datetime, timezone

import pytest

from lib.telemetry import TelemetryConfig, TelemetryPublisher


class FakeFuture:
    def result(self, timeout=None):
        return None


class FakeConnection:
    def __init__(self, *, publish_error: Exception | None = None) -> None:
        self.published: list[tuple[str, str]] = []
        self.connects = 0
        self.disconnects = 0
        self._publish_error = publish_error

    def connect(self):
        self.connects += 1
        return FakeFuture()

    def publish(self, topic, payload, qos):
        if self._publish_error is not None:
            raise self._publish_error
        self.published.append((topic, payload))
        return FakeFuture()

    def disconnect(self):
        self.disconnects += 1
        return FakeFuture()


def snapshot() -> dict:
    return {
        "overall_status": "ok",
        "timestamp": datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc),
        "motor_feedback": [{"motor_id": 1, "rpm": 40}],
    }


def make_publisher(connection=None, **overrides):
    fields = {
        "endpoint": "example-ats.iot.eu-central-1.amazonaws.com",
        "client_id": "rover-01",
        "thing_name": "rover-01",
        "topic": "rover/{thing}/telemetry",
        "cert_path": "/certs/device.pem.crt",
        "key_path": "/certs/private.pem.key",
        "root_ca_path": "/certs/Amazon-root-CA-1.pem",
    }
    fields.update(overrides)
    config = TelemetryConfig(**fields)
    connection = connection or FakeConnection()
    publisher = TelemetryPublisher(
        snapshot=snapshot,
        config=config,
        connection_factory=lambda _config: connection,
    )
    return publisher, connection


def test_no_endpoint_leaves_telemetry_switched_off():
    publisher, connection = make_publisher(endpoint="")

    publisher.start()

    assert publisher.configured is False
    assert publisher.publish_once() is False
    assert connection.connects == 0
    publisher.stop()


def test_publishes_to_the_topic_the_iot_rule_subscribes_to():
    publisher, connection = make_publisher()

    assert publisher.publish_once() is True

    topic, _payload = connection.published[0]
    assert topic == "rover/rover-01/telemetry"


def test_payload_is_json_with_the_thing_name_in_the_body():
    # The Lambda reads thing_name from the body, so it never has to parse the
    # topic; the IoT rule can stay a plain `SELECT *`.
    publisher, connection = make_publisher()

    publisher.publish_once()

    _topic, payload = connection.published[0]
    message = json.loads(payload)
    assert message["thing_name"] == "rover-01"
    assert message["snapshot"]["overall_status"] == "ok"


def test_datetimes_survive_serialisation_as_iso_strings():
    publisher, connection = make_publisher()

    publisher.publish_once()

    message = json.loads(connection.published[0][1])
    assert message["snapshot"]["timestamp"] == "2026-09-12T10:00:00+00:00"
    assert datetime.fromisoformat(message["recorded_at"]).tzinfo is not None


def test_the_connection_is_reused_across_publishes():
    publisher, connection = make_publisher()

    publisher.publish_once()
    publisher.publish_once()

    assert connection.connects == 1
    assert len(connection.published) == 2


def test_a_failed_publish_is_swallowed_and_drops_the_connection():
    # The uplink is allowed to fail: the driving loop must never see it, and
    # the next tick reconnects rather than reusing a dead socket.
    publisher, connection = make_publisher(connection=FakeConnection(publish_error=OSError("down")))

    assert publisher.publish_once() is False
    assert publisher.failed == 1
    assert publisher.published == 0
    assert connection.disconnects == 1


def test_stop_disconnects_cleanly():
    publisher, connection = make_publisher()
    publisher.publish_once()

    publisher.stop()

    assert connection.disconnects == 1


class FakePahoClient:
    """Stands in for `paho.mqtt.client.Client`, recording how it was driven."""

    last: "FakePahoClient | None" = None

    def __init__(self, callback_api_version, client_id, protocol, clean_session):
        self.client_id = client_id
        self.clean_session = clean_session
        self.tls = None
        self.connected_to = None
        self.loops_started = 0
        self.loops_stopped = 0
        self.disconnects = 0
        self.publish_rc = 0
        FakePahoClient.last = self

    def tls_set(self, ca_certs, certfile, keyfile, tls_version):
        self.tls = {"ca": ca_certs, "cert": certfile, "key": keyfile}

    def connect(self, host, port, keepalive):
        self.connected_to = (host, port, keepalive)

    def loop_start(self):
        self.loops_started += 1

    def loop_stop(self):
        self.loops_stopped += 1

    def publish(self, topic, payload, qos):
        rc = self.publish_rc

        class Info:
            def __init__(self) -> None:
                self.rc = rc

            def wait_for_publish(self, timeout=None):
                return None

        return Info()

    def disconnect(self):
        self.disconnects += 1


@pytest.fixture()
def fake_paho(monkeypatch):
    import paho.mqtt.client as mqtt

    monkeypatch.setattr(mqtt, "Client", FakePahoClient)
    return mqtt


def test_paho_connects_with_mutual_tls_on_the_iot_port(fake_paho):
    from lib.telemetry.publisher import _PahoConnection

    publisher, _ = make_publisher()
    connection = _PahoConnection(publisher.config)

    connection.connect()

    client = FakePahoClient.last
    assert client.connected_to == ("example-ats.iot.eu-central-1.amazonaws.com", 8883, 30)
    assert client.tls == {
        "ca": "/certs/Amazon-root-CA-1.pem",
        "cert": "/certs/device.pem.crt",
        "key": "/certs/private.pem.key",
    }
    # Without the network thread the QoS 1 handshake never completes.
    assert client.loops_started == 1
    assert client.client_id == "rover-01"


def test_a_nonzero_publish_return_code_is_an_error(fake_paho):
    from lib.telemetry.publisher import _PahoConnection

    publisher, _ = make_publisher()
    connection = _PahoConnection(publisher.config)
    connection.connect()
    FakePahoClient.last.publish_rc = 4

    with pytest.raises(RuntimeError, match="rc=4"):
        connection.publish("rover/rover-01/telemetry", "{}", 1)


def test_disconnect_stops_the_network_thread(fake_paho):
    from lib.telemetry.publisher import _PahoConnection

    publisher, _ = make_publisher()
    connection = _PahoConnection(publisher.config)
    connection.connect()

    connection.disconnect()

    assert FakePahoClient.last.loops_stopped == 1
    assert FakePahoClient.last.disconnects == 1
