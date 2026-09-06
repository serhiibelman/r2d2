from fastapi import APIRouter

from apps.api.dependencies import DatabaseHealthDep, VehicleStatusServiceDep
from apps.api.schemas import ComponentStatus, VehicleHealthResponse

router = APIRouter()


@router.get("/health", response_model=VehicleHealthResponse)
def health(service: VehicleStatusServiceDep, db_health: DatabaseHealthDep) -> VehicleHealthResponse:
    snapshot = service.snapshot()
    probe = db_health.snapshot()
    return VehicleHealthResponse(
        status=snapshot["overall_status"],
        service=snapshot["service"],
        timestamp=snapshot["timestamp"],
        components=snapshot["components"],
        # Deliberately outside `components`: the robot drives without a
        # database, so this never moves `status`, and a consumer recomputing
        # health from `components` must not see it there.
        database=ComponentStatus(
            configured=probe.configured,
            connected=probe.connected,
            detail=probe.detail,
            checked_at=probe.checked_at,
        ),
    )
