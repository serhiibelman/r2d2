from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routes.camera import router as camera_router
from apps.api.routes.health import router as health_router
from apps.api.routes.motors import router as motors_router
from apps.api.routes.status import router as status_router
from apps.api.routes.telemetry import router as telemetry_router
from apps.api.services.camera import CameraService
from apps.api.services.telemetry import TelemetryService
from apps.api.services.vehicle_status import VehicleStatusService
from lib.db import DatabaseHealthMonitor, database as default_database
from lib.db.session import Database


def create_app(
    vehicle_status_service: VehicleStatusService | None = None,
    camera_service: CameraService | None = None,
    db: Database | None = None,
) -> FastAPI:
    service = vehicle_status_service or VehicleStatusService()
    camera = camera_service or CameraService()
    # The only place that decides which database is in use.
    db = db or default_database
    telemetry = TelemetryService(db)
    db_health = DatabaseHealthMonitor(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.vehicle_status_service = service
        app.state.camera_service = camera
        app.state.database = db
        app.state.database_health = db_health
        app.state.telemetry_service = telemetry
        service.start()
        db_health.start()
        # The camera opens on the first stream/snapshot request instead of at
        # boot, so the sensor stays powered down while nobody is watching.
        try:
            yield
        finally:
            service.stop()
            camera.stop()
            db_health.stop()
            db.dispose()

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
    app.include_router(telemetry_router)
    return app


app = create_app()
