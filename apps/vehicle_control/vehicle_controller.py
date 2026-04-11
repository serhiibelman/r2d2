import time
from typing import Optional

from apps.common.formatting import print_info, print_warning
from apps.controller.udp_receiver import UDPReceiver
from apps.controller.state import ControllerState
from apps.ddsm115 import DDS115
from settings import RIGHT_SIDE, LEFT_SIDE

MAX_RPM = 100
RAMP_STEP = 5
DEAD_ZONE = 0.1
LOOP_INTERVAL = 0.05  # 20 Hz


class VehicleController:
    def __init__(self, receiver: UDPReceiver, motor: DDS115):
        self.receiver = receiver
        self.motor = motor
        self._current_rpm: float = 0.0
        self._braked: bool = False

    def run(self):
        """
        Public interface
        """
        print_info("VehicleController started")
        try:
            while True:
                state = self.receiver.receive()
                if state is not None:
                    self._handle(state)
                time.sleep(LOOP_INTERVAL)
        except KeyboardInterrupt:
            print_info("VehicleController stopped")
        finally:
            self._stop_motors()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle(self, state: ControllerState) -> None:
        if state.buttons.lb:
            self._brake()
            return

        self._braked = False

        if state.buttons.l:
            left_y = state.axes.left_y  # up = -1, down = +1
            left_x = state.axes.left_x  # left = -1, right = +1

            target_rpm = -left_y * MAX_RPM
            self._current_rpm = self._ramp_toward(self._current_rpm, target_rpm)

            left_rpm, right_rpm = self._compute_side_rpms(
                self._current_rpm, left_x, left_y
            )
        else:
            # Dead-man released: ramp back to zero
            self._current_rpm = self._ramp_toward(self._current_rpm, 0.0)
            left_rpm = self._current_rpm
            right_rpm = self._current_rpm

        self._apply(left_rpm, right_rpm)

    def _compute_side_rpms(
        self, base_rpm: float, left_x: float, left_y: float
    ) -> tuple[float, float]:
        if abs(left_y) > DEAD_ZONE:
            # Differential steering: reduce one side proportionally
            steer = left_x  # -1 = turn left, +1 = turn right
            if steer > 0:
                # Turn right: slow the right side
                left_rpm = base_rpm
                right_rpm = base_rpm * (1.0 - steer)
            else:
                # Turn left: slow the left side
                left_rpm = base_rpm * (1.0 + steer)  # steer is negative
                right_rpm = base_rpm
        else:
            # Tank turn: no forward/backward, just spin in opposite directions
            if abs(left_x) > DEAD_ZONE:
                left_rpm = left_x * MAX_RPM
                right_rpm = -left_x * MAX_RPM
            else:
                left_rpm = 0.0
                right_rpm = 0.0

        return left_rpm, right_rpm

    def _apply(self, left_rpm: float, right_rpm: float) -> None:
        left = round(left_rpm)
        right = round(right_rpm)
        for motor_id in LEFT_SIDE:
            self.motor.send_rpm(motor_id, rpm=left)
        for motor_id in RIGHT_SIDE:
            self.motor.send_rpm(motor_id, rpm=right * (-1))

    def _brake(self) -> None:
        if not self._braked:
            print_warning("BRAKE")
            for motor_id in LEFT_SIDE + RIGHT_SIDE:
                self.motor.set_brake(motor_id)
            self._current_rpm = 0.0
            self._braked = True

    def _stop_motors(self) -> None:
        for motor_id in LEFT_SIDE + RIGHT_SIDE:
            self.motor.send_rpm(motor_id, rpm=0)

    @staticmethod
    def _ramp_toward(current: float, target: float) -> float:
        diff = target - current
        if abs(diff) <= RAMP_STEP:
            return target
        return current + RAMP_STEP * (1 if diff > 0 else -1)
