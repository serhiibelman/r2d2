import argparse
import time
from tqdm import tqdm

from apps.common.formatting import print_info, print_warning, print_error, print_success
from apps.ddsm115 import DDS115

RIGHT_SIDE = [1, 2]
LEFT_SIDE = [3, 4]


def apply_to_all_motors(action, *, dry_run: bool):
    if dry_run:
        return

    for motor_id in RIGHT_SIDE + LEFT_SIDE:
        action(motor_id)


def ramp_rpm(motor, start, stop, step, delay, *, dry_run: bool):
    rpms = list(range(start, stop, step))

    with tqdm(
        rpms,
        desc="RPM",
        unit="rpm",
        leave=False,
    ) as bar:
        for rpm in bar:
            # for rpm in range(start, stop, step):
            bar.set_postfix(rpm=rpm)

            apply_to_all_motors(
                lambda m_id, rpm=rpm: motor.send_rpm(m_id, rpm=rpm),
                dry_run=dry_run,
            )

            time.sleep(delay)


def motor_self_test(*, dry_run: bool):
    print_info("Starting motor self-test")

    try:
        motor = None if dry_run else DDS115()
    except RuntimeError as e:
        print_error(e)
        return

    print_warning("⚠️ RAMP UP")
    ramp_rpm(motor, start=1, stop=100, step=1, delay=0.05, dry_run=dry_run)
    time.sleep(2)

    print_warning("⚠️ RAMP DOWN")
    ramp_rpm(motor, start=100, stop=0, step=-5, delay=0.05, dry_run=dry_run)
    time.sleep(2)

    print_warning("⚠️ BRAKE")
    apply_to_all_motors(
        lambda m_id: motor.set_brake(m_id),
        dry_run=dry_run,
    )
    time.sleep(2)

    print_warning("⚠️ STOP")
    apply_to_all_motors(
        lambda m_id: motor.send_rpm(m_id, rpm=0),
        dry_run=dry_run,
    )

    print_success("Motor self-test completed")


def main():
    parser = argparse.ArgumentParser(description="DDS115 motor self-test")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually run motors (default: dry-run)",
    )

    args = parser.parse_args()
    dry_run = not args.live

    print_warning("⚠️  HARDWARE SELF TEST")
    if dry_run:
        print_warning("DRY-RUN mode enabled — motors will NOT move")
    else:
        input("Motors WILL SPIN. Press ENTER to continue or Ctrl+C to abort")

    motor_self_test(dry_run=dry_run)


if __name__ == "__main__":
    main()
