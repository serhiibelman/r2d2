import time
from lib.common.formatting import print_info
from apps.controller.controller_reader import ControllerReader
from lib.gamepad.udp_sender import UDPSender

UDP_HOST = "raspberrypi.local"
UDP_PORT = 5005
SEND_INTERVAL = 0.05  # 20 Hz


class GamepadMain:
    def __init__(self):
        self.reader = ControllerReader()
        self.sender = UDPSender(UDP_HOST, UDP_PORT)

    def run(self):
        print_info("Controller started")

        try:
            while True:
                state = self.reader.read_state()
                print("state:", state)
                self.sender.send(state.to_json())

                time.sleep(SEND_INTERVAL)

        except KeyboardInterrupt:
            print_info("Controller stopped")

        finally:
            self.shutdown()

    def shutdown(self):
        self.reader.quit()
        self.sender.quit()
        print_info("Shutdown")


if __name__ == "__main__":
    gamepad = GamepadMain()
    gamepad.run()
