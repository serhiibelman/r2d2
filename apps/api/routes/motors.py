from fastapi import APIRouter, HTTPException, Request, status

from apps.api.schemas import MotorCommandResponse, StartMotorsRequest

router = APIRouter(prefix="/motors", tags=["motors"])


@router.post("/start", response_model=MotorCommandResponse)
def start_motors(request: Request, payload: StartMotorsRequest) -> MotorCommandResponse:
    service = request.app.state.vehicle_status_service
    try:
        result = service.start_motors(payload.rpm)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return MotorCommandResponse(**result)


@router.post("/stop", response_model=MotorCommandResponse)
def stop_motors(request: Request) -> MotorCommandResponse:
    service = request.app.state.vehicle_status_service
    try:
        result = service.stop_motors()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return MotorCommandResponse(**result)
