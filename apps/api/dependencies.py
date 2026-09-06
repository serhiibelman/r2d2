"""Typed access to the services `create_app` put on `app.state`.

Routes ask for what they need instead of reaching into `request.app.state`, so
the lookup is checked and a handler's signature says what it depends on.
"""

from typing import Annotated

from fastapi import Depends, Request

from apps.api.services.camera import CameraService
from apps.api.services.vehicle_status import VehicleStatusService


def get_vehicle_status_service(request: Request) -> VehicleStatusService:
    return request.app.state.vehicle_status_service


def get_camera_service(request: Request) -> CameraService:
    return request.app.state.camera_service


VehicleStatusServiceDep = Annotated[VehicleStatusService, Depends(get_vehicle_status_service)]
CameraServiceDep = Annotated[CameraService, Depends(get_camera_service)]
