"""Typed access to the services `create_app` put on `app.state`.

Routes ask for what they need instead of reaching into `request.app.state`, so
the lookup is checked, the guards live in one place, and a handler's signature
says what it depends on.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from apps.api.services.camera import CameraService
from apps.api.services.telemetry import TelemetryService
from apps.api.services.vehicle_status import VehicleStatusService
from apps.db import DatabaseHealthMonitor


def get_vehicle_status_service(request: Request) -> VehicleStatusService:
    return request.app.state.vehicle_status_service


def get_camera_service(request: Request) -> CameraService:
    return request.app.state.camera_service


def get_database_health(request: Request) -> DatabaseHealthMonitor:
    return request.app.state.database_health


def get_telemetry_service(request: Request) -> TelemetryService:
    service: TelemetryService = request.app.state.telemetry_service
    if not service.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured (DATABASE_URL is empty)",
        )
    return service


VehicleStatusServiceDep = Annotated[VehicleStatusService, Depends(get_vehicle_status_service)]
CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]
DatabaseHealthDep = Annotated[DatabaseHealthMonitor, Depends(get_database_health)]
TelemetryServiceDep = Annotated[TelemetryService, Depends(get_telemetry_service)]
