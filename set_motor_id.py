import sys

from apps.common.formatting import print_info, print_error, print_success
from apps.ddsm115 import DDS115


def main():
    if len(sys.argv) != 2:
        print("Usage: python set_motor_id.py <motor_id>")
        sys.exit(1)

    try:
        motor_id = int(sys.argv[1])
    except ValueError:
        print_error("Motor ID must be an integer")
        sys.exit(1)

    print_info("▶ Connect a SINGLE motor to the bus")
    input("▶ Press Enter when ready...")

    try:
        motor = DDS115()
    except RuntimeError as e:
        print_error(e)
        sys.exit(1)

    print(f"▶ Setting ID {motor_id} for motor...")
    motor.set_id(motor_id)

    print_success("✔ Motor ID successfully set")
    print("▶ You may now disconnect the motor")


if __name__ == "__main__":
    main()
