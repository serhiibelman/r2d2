from datetime import datetime

from pydantic import BaseModel


class ComponentStatus(BaseModel):
    configured: bool
    connected: bool
    detail: str
    checked_at: datetime


class MotorFeedback(BaseModel):
    motor_id: int
    rpm: int | None
    current_raw: int | None


class VehicleHealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    # Hardware only - `status` is computed from these.
    components: dict[str, ComponentStatus]
    # Advisory: the vehicle is healthy without a database.
    database: ComponentStatus


class VehicleStatusResponse(BaseModel):
    service: str
    timestamp: datetime
    motor_device: str | None
    fc_device: str | None
    motor_ids: dict[str, list[int]]
    components: dict[str, ComponentStatus]
    motor_feedback: list[MotorFeedback]


class VehicleStatusEventResponse(BaseModel):
    id: int
    recorded_at: datetime
    service: str
    overall_status: str
    motor_device: str | None
    fc_device: str | None
    components: dict
    motor_feedback: list


class CameraStatusResponse(BaseModel):
    service: str
    timestamp: datetime
    running: bool
    clients: int
    width: int
    height: int
    framerate: int
    jpeg_quality: int
    encoder: str | None
    frames_captured: int
    last_frame_at: datetime | None
    component: ComponentStatus


class CameraCommandResponse(BaseModel):
    service: str
    action: str
    running: bool
    detail: str
    timestamp: datetime


class StartMotorsRequest(BaseModel):
    rpm: int


class MotorCommandResponse(BaseModel):
    service: str
    action: str
    target_rpm: int
    current_rpm: int
    detail: str
    timestamp: datetime
