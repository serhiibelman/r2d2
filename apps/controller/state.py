from dataclasses import asdict, dataclass


@dataclass
class AxesState:
    left_x: float
    left_y: float
    right_x: float
    right_y: float
    trigger_left: float
    trigger_right: float


@dataclass
class ButtonsState:
    a: bool
    b: bool
    x: bool
    y: bool
    lb: bool
    rb: bool
    lt: bool
    rt: bool
    l: bool
    r: bool


@dataclass
class ControllerState:
    timestamp: float
    axes: AxesState
    buttons: ButtonsState

    def to_json(self) -> dict:
        return asdict(self)
