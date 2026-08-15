from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routes.camera import router as camera_router
from apps.api.routes.health import router as health_router
from apps.api.routes.motors import router as motors_router
from apps.api.routes.status import router as status_router
from apps.api.services.camera import CameraService
from apps.api.services.vehicle_status import VehicleStatusService


def create_app(
    vehicle_status_service: VehicleStatusService | None = None,
    camera_service: CameraService | None = None,
) -> FastAPI:
    service = vehicle_status_service or VehicleStatusService()
    camera = camera_service or CameraService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.vehicle_status_service = service
        app.state.camera_service = camera
        service.start()
        # The camera opens on the first stream/snapshot request instead of at
        # boot, so the sensor stays powered down while nobody is watching.
        try:
            yield
        finally:
            service.stop()
            camera.stop()

    app = FastAPI(
        title="R2D2 Vehicle API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "r2d2-vehicle-api",
            "status": "ok",
        }

    app.include_router(camera_router)
    app.include_router(health_router)
    app.include_router(motors_router)
    app.include_router(status_router)
    return app


app = create_app()
