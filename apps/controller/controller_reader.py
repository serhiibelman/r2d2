import time

import pygame
from apps.common.formatting import print_info, print_error
from apps.controller.state import ControllerState, AxesState, ButtonsState


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

    def read_state(self) -> ControllerState:
        pygame.event.pump()
        # print("AXIS", [self.joy.get_axis(x) for x in range(6)])
        # print("BUTTONS", [self.joy.get_button(x) for x in range(11)])

        for x in range(6):
            axs = self.joy.get_axis(x)
            print("AXIS pressed:", x, axs)
        axes = AxesState(
            left_x=self.joy.get_axis(0),
            left_y=self.joy.get_axis(1),
            right_x=self.joy.get_axis(3),
            right_y=self.joy.get_axis(4),
            trigger_left=self.joy.get_button(9),
            trigger_right=self.joy.get_button(10),
        )
        # Buttons if connected by usb port
        buttons = ButtonsState(
            a=bool(self.joy.get_button(0)),
            b=bool(self.joy.get_button(1)),
            x=bool(self.joy.get_button(2)),
            y=bool(self.joy.get_button(3)),
            lb=bool(self.joy.get_button(4)),
            rb=bool(self.joy.get_button(5)),
            l=bool(self.joy.get_button(9)),
            r=bool(self.joy.get_button(10)),
        )

        return ControllerState(
            timestamp=time.time(),
            axes=axes,
            buttons=buttons,
        )

    @staticmethod
    def quit():
        pygame.quit()
