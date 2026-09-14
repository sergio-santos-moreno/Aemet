import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.logging_config import configure_logging
from app.routers import antartida

configure_logging()
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: initialising SQLite cache database")
    init_db()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="AEMET Antarctic Weather API",
    description=(
        "Retrieves historical weather data (temperature, pressure, wind speed) from AEMET's "
        "Antarctic meteo stations, with local SQLite caching to minimise load on the source API."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(antartida.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
