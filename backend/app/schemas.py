"""
Pydantic models: the public "contract" of the API.

Using enums for Station / DataType / TimeAggregation means FastAPI validates
and documents the allowed values automatically (visible in /docs) instead of
us hand-rolling "if value not in [...]" checks in the endpoint.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Station(str, Enum):
    """The only two stations in scope per the challenge statement."""

    GABRIEL_DE_CASTILLA = "Meteo Station Gabriel de Castilla"
    JUAN_CARLOS_I = "Meteo Station Juan Carlos I"

    @property
    def aemet_id(self) -> str:
        """AEMET's own station identifier (SYNOP indicator)."""
        return {
            Station.GABRIEL_DE_CASTILLA: "89070",
            Station.JUAN_CARLOS_I: "89064",
        }[self]


class DataType(str, Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    SPEED = "speed"


class TimeAggregation(str, Enum):
    NONE = "none"
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class MeasurementOut(BaseModel):
    """One row of the output dataset."""

    station: str
    # ISO-8601 string including UTC offset, e.g. "2024-01-15T10:00:00+01:00"
    datetime: str
    temperature_c: float | None = Field(default=None, description="Temperature in \u00baC")
    pressure_hpa: float | None = Field(default=None, description="Pressure in hPa")
    speed_ms: float | None = Field(default=None, description="Wind speed in m/s")


class AntartidaResponse(BaseModel):
    station: Station
    aggregation: TimeAggregation
    from_datetime: str
    to_datetime: str
    tz_location_requested: str | None
    count: int
    data: list[MeasurementOut]
