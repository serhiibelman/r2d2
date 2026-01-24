from apps.common.formatting import print_warning
from apps.ddsm115 import DDS115


def test_actuator():
    m1 = DDS115()
    m1.get_motor_id()


if __name__ == "__main__":
    print_warning("⚠️  HARDWARE SELF TEST – MOTORS WILL SPIN")
    input("Press ENTER to continue or Ctrl+C to abort")

    test_actuator()
