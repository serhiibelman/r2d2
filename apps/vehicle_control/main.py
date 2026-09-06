from lib.gamepad.udp_receiver import UDPReceiver
from lib.ddsm115 import DDS115
from apps.vehicle_control.vehicle_controller import VehicleController
from lib.common.formatting import print_error


def main():
    try:
        motor = DDS115()
    except RuntimeError as e:
        print_error(e)
        return

    receiver = UDPReceiver()
    controller = VehicleController(receiver=receiver, motor=motor)

    try:
        controller.run()
    finally:
        receiver.quit()
        motor.close()


if __name__ == "__main__":
    main()
