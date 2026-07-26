from apps.api.services.vehicle_status import VehicleStatusService


class FakeMotor:
    def __init__(self, device: str):
        self.device = device
        self.commands: list[tuple[int, int]] = []
        self.closed = False

    def send_rpm(self, motor_id: int, rpm: int = 0) -> None:
        self.commands.append((motor_id, rpm))

    def close(self) -> None:
        self.closed = True


def test_start_motors_ramps_all_motors() -> None:
    motors: list[FakeMotor] = []

    def motor_factory(*, device: str) -> FakeMotor:
        motor = FakeMotor(device)
        motors.append(motor)
        return motor

    service = VehicleStatusService(
        motor_device="/dev/test",
        fc_device=None,
        motor_factory=motor_factory,
        sleep_func=lambda _: None,
    )

    response = service.start_motors(12)

    assert response["action"] == "start"
    assert response["current_rpm"] == 12
    assert len(motors) == 1
    assert motors[0].closed is True
    assert motors[0].commands == [
        (3, 5),
        (4, 5),
        (1, -5),
        (2, -5),
        (3, 10),
        (4, 10),
        (1, -10),
        (2, -10),
        (3, 12),
        (4, 12),
        (1, -12),
        (2, -12),
    ]


def test_stop_motors_ramps_down_from_current_speed() -> None:
    motors: list[FakeMotor] = []

    def motor_factory(*, device: str) -> FakeMotor:
        motor = FakeMotor(device)
        motors.append(motor)
        return motor

    service = VehicleStatusService(
        motor_device="/dev/test",
        fc_device=None,
        motor_factory=motor_factory,
        sleep_func=lambda _: None,
    )

    service.start_motors(12)
    response = service.stop_motors()

    assert response["action"] == "stop"
    assert response["current_rpm"] == 0
    assert len(motors) == 2
    assert motors[1].commands == [
        (3, 7),
        (4, 7),
        (1, -7),
        (2, -7),
        (3, 2),
        (4, 2),
        (1, -2),
        (2, -2),
        (3, 0),
        (4, 0),
        (1, 0),
        (2, 0),
    ]
