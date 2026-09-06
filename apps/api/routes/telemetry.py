from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from apps.api.dependencies import TelemetryServiceDep, VehicleStatusServiceDep
from apps.api.schemas import VehicleStatusEventResponse
from apps.api.services.telemetry import MAX_LIMIT
from apps.db import VehicleStatusEvent

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _response(event: VehicleStatusEvent) -> VehicleStatusEventResponse:
    return VehicleStatusEventResponse(
        id=event.id,
        recorded_at=event.recorded_at,
        service=event.service,
        overall_status=event.overall_status,
        motor_device=event.motor_device,
        fc_device=event.fc_device,
        components=event.components,
        motor_feedback=event.motor_feedback,
    )


@router.post(
    "/snapshot",
    response_model=VehicleStatusEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def store_snapshot(
    telemetry: TelemetryServiceDep, vehicle: VehicleStatusServiceDep
) -> VehicleStatusEventResponse:
    """Persist the current vehicle snapshot as one history row."""
    snapshot = vehicle.snapshot()
    try:
        event = telemetry.record_snapshot(snapshot)
    except SQLAlchemyError as error:
        # Only database failures become 503; anything else is a bug and must
        # surface as a 500 instead of hiding behind "the uplink is down".
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database write failed: {type(error).__name__}",
        ) from error
    return _response(event)


@router.get("", response_model=list[VehicleStatusEventResponse])
def list_events(
    telemetry: TelemetryServiceDep, limit: int = Query(50, ge=1, le=MAX_LIMIT)
) -> list[VehicleStatusEventResponse]:
    try:
        events = telemetry.recent(limit=limit)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database read failed: {type(error).__name__}",
        ) from error
    return [_response(event) for event in events]
