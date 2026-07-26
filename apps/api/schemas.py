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
    components: dict[str, ComponentStatus]


class VehicleStatusResponse(BaseModel):
    service: str
    timestamp: datetime
    motor_device: str | None
    fc_device: str | None
    motor_ids: dict[str, list[int]]
    components: dict[str, ComponentStatus]
    motor_feedback: list[MotorFeedback]


class StartMotorsRequest(BaseModel):
    rpm: int


class MotorCommandResponse(BaseModel):
    service: str
    action: str
    target_rpm: int
    current_rpm: int
    detail: str
    timestamp: datetime
