import socket
import json
from lib.common.formatting import print_warning


class UDPSender:
    def __init__(self, host: str, port: int):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

    def send(self, payload: dict):
        try:
            data = json.dumps(payload).encode()
            self.sock.sendto(data, self.addr)
        except OSError as e:
            # Raspberry offline? Wi-Fi down? No problem.
            print_warning(f"UDP send failed: {e}")

    def quit(self):
        self.sock.close()
