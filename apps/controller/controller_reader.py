import time
from dataclasses import dataclass, asdict

import pygame
from apps.common.formatting import print_info, print_error


@dataclass
class ControllerState:
    timestamp: float
    axes: list[float]
    buttons: list[int]

    def to_json(self) -> dict:
        return asdict(self)


class ControllerReader:
    def __init__(self):
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            print_error("No joystick found")
            raise SystemExit(1)

        self.joy = pygame.joystick.Joystick(0)
        self.joy.init()

        print_info(f"Joystick connected: {self.joy.get_name()}")

    def read_state(self):
        pygame.event.pump()

        axes = [self.joy.get_axis(i) for i in range(self.joy.get_numaxes())]
        buttons = [self.joy.get_button(i) for i in range(self.joy.get_numbuttons())]

        return ControllerState(
            timestamp=time.time(),
            axes=axes,
            buttons=buttons,
        )

    @staticmethod
    def quit():
        pygame.quit()
