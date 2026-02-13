import socket
import json
from typing import Optional

from apps.controller.state import ControllerState, AxesState, ButtonsState

from apps.common.formatting import print_error


class UDPReceiver:
    def __init__(self, host: str = "0.0.0.0", port: int = 5005):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.addr)
        self.sock.setblocking(False)

    def receive(self) -> Optional[ControllerState]:
        try:
            data, _ = self.sock.recvfrom(4096)
            payload = json.loads(data.decode())
            return self._deserialize(payload)
        except BlockingIOError:
            # No packet available
            return None
        except (json.JSONDecodeError, KeyError) as e:
            print_error(f"Invalid packet: {e}")
            return None

    def _deserialize(self, payload: dict) -> ControllerState:
        axes = AxesState(**payload["axes"])
        buttons = ButtonsState(**payload["buttons"])

        return ControllerState(
            timestamp=payload["timestamp"],
            axes=axes,
            buttons=buttons,
        )

    def quit(self):
        self.sock.close()
