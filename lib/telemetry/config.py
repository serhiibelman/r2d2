from __future__ import annotations

from dataclasses import dataclass

from settings import (
    IOT_CERT_PATH,
    IOT_CLIENT_ID,
    IOT_ENDPOINT,
    IOT_KEEP_ALIVE_SECONDS,
    IOT_KEY_PATH,
    IOT_PORT,
    IOT_ROOT_CA_PATH,
    IOT_THING_NAME,
    TELEMETRY_HEARTBEAT_SECONDS,
    TELEMETRY_INTERVAL_SECONDS,
    TELEMETRY_PUBLISH_TIMEOUT_SECONDS,
    TELEMETRY_TOPIC,
)


@dataclass(frozen=True)
class TelemetryConfig:
    """Everything the publisher needs, in one place.

    Defaults come from ``.env``; a second destination or a test double is a
    different config, not a different process environment.
    """

    endpoint: str = IOT_ENDPOINT
    port: int = IOT_PORT
    client_id: str = IOT_CLIENT_ID
    thing_name: str = IOT_THING_NAME
    topic: str = TELEMETRY_TOPIC
    cert_path: str = IOT_CERT_PATH
    key_path: str = IOT_KEY_PATH
    root_ca_path: str = IOT_ROOT_CA_PATH
    interval_seconds: float = TELEMETRY_INTERVAL_SECONDS
    heartbeat_seconds: float = TELEMETRY_HEARTBEAT_SECONDS
    keep_alive_seconds: int = IOT_KEEP_ALIVE_SECONDS
    publish_timeout_seconds: float = TELEMETRY_PUBLISH_TIMEOUT_SECONDS

    @property
    def resolved_topic(self) -> str:
        """``rover/{thing}/telemetry`` - the shape the IoT rule subscribes to."""
        return self.topic.replace("{thing}", self.thing_name)
