from fastapi import APIRouter, Request

from apps.api.schemas import VehicleHealthResponse

router = APIRouter()


@router.get("/health", response_model=VehicleHealthResponse)
def health(request: Request) -> VehicleHealthResponse:
    snapshot = request.app.state.vehicle_status_service.snapshot()
    return VehicleHealthResponse(
        status=snapshot["overall_status"],
        service=snapshot["service"],
        timestamp=snapshot["timestamp"],
        components=snapshot["components"],
    )
