from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.routes.health import router as health_router
from apps.api.routes.motors import router as motors_router
from apps.api.routes.status import router as status_router
from apps.api.services.vehicle_status import VehicleStatusService


def create_app(vehicle_status_service: VehicleStatusService | None = None) -> FastAPI:
    service = vehicle_status_service or VehicleStatusService()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.vehicle_status_service = service
        service.start()
        try:
            yield
        finally:
            service.stop()

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

    app.include_router(health_router)
    app.include_router(motors_router)
    app.include_router(status_router)
    return app


app = create_app()
