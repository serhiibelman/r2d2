from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from apps.api.dependencies import CameraServiceDep
from apps.api.schemas import CameraCommandResponse, CameraStatusResponse

router = APIRouter(prefix="/camera", tags=["camera"])

BOUNDARY = "FRAME"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Age": "0",
}


async def _multipart(request: Request, service) -> AsyncIterator[bytes]:
    """Yield MJPEG parts until the camera stops or the viewer goes away.

    The frame wait is blocking, so it runs in a worker thread; the generator
    itself stays async so a disconnect reliably reaches the ``finally`` and
    hands the viewer slot back.
    """
    try:
        last_seq = -1
        while not await request.is_disconnected():
            try:
                result = await run_in_threadpool(service.next_frame, last_seq)
            except RuntimeError:
                # The camera died mid-stream; /camera/status carries the reason.
                break
            if result is None:
                break
            last_seq, frame = result
            yield (
                f"--{BOUNDARY}\r\n"
                f"Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n"
            ).encode() + frame + b"\r\n"
    finally:
        service.release_client_slot()


@router.get("/stream")
def stream(request: Request, service: CameraServiceDep) -> StreamingResponse:
    try:
        service.acquire_client_slot()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return StreamingResponse(
        _multipart(request, service),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers=NO_CACHE_HEADERS,
    )


@router.get("/snapshot")
def snapshot(service: CameraServiceDep) -> Response:
    try:
        frame = service.capture_frame()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return Response(content=frame, media_type="image/jpeg", headers=NO_CACHE_HEADERS)


@router.get("/status", response_model=CameraStatusResponse)
def camera_status(service: CameraServiceDep) -> CameraStatusResponse:
    return CameraStatusResponse(**service.snapshot())


@router.post("/start", response_model=CameraCommandResponse)
def start_camera(service: CameraServiceDep) -> CameraCommandResponse:
    try:
        result = service.start()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return CameraCommandResponse(**result)


@router.post("/stop", response_model=CameraCommandResponse)
def stop_camera(service: CameraServiceDep) -> CameraCommandResponse:
    try:
        result = service.stop()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return CameraCommandResponse(**result)
