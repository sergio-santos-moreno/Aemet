"""
The endpoint required by the challenge:

  GET /api/antartida/datos/fechaini/{fechaIniStr}/fechafin/{fechaFinStr}/estacion/{identificacion}

Path parameters map 1:1 to the challenge statement. Everything the
statement calls "optional"/"user shall be able to specify" but that isn't
part of the URL template (location, time aggregation, data types) is
exposed as query parameters, which is the conventional REST place for
filters that don't identify a resource.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.aemet_client import AemetApiError, AemetClient
from app.aggregation import aggregate_measurements
from app.cache_service import ensure_data_cached, read_cached_measurements
from app.db import get_db
from app.schemas import AntartidaResponse, DataType, Station, TimeAggregation
from app.timezone_utils import InvalidLocationError, parse_naive_datetime, resolve_input_timezone, to_utc

logger = logging.getLogger("antartida_router")

router = APIRouter(prefix="/api/antartida", tags=["antartida"])


def get_aemet_client() -> AemetClient:
    """FastAPI dependency so tests can override this with a mocked client."""
    client = AemetClient()
    try:
        yield client
    finally:
        client.close()


@router.get("/datos/fechaini/{fecha_ini_str}/fechafin/{fecha_fin_str}/estacion/{identificacion}",
            response_model=AntartidaResponse)
def get_antartida_datos(
    fecha_ini_str: str,
    fecha_fin_str: str,
    identificacion: Station,
    location: str | None = Query(
        default=None,
        description="IANA timezone (e.g. 'Europe/Berlin') or fixed UTC offset (e.g. '+02:00') "
        "the input datetimes are expressed in. Defaults to UTC when omitted.",
    ),
    aggregation: TimeAggregation = Query(default=TimeAggregation.NONE, alias="time_aggregation"),
    data_types: list[DataType] = Query(
        default=[], description="0 to 3 of: temperature, pressure, speed. Empty = all."
    ),
    db: Session = Depends(get_db),
    aemet_client: AemetClient = Depends(get_aemet_client),
) -> AntartidaResponse:
    if len(set(data_types)) != len(data_types):
        raise HTTPException(status_code=400, detail="data_types must not contain duplicates")

    try:
        naive_start = parse_naive_datetime(fecha_ini_str, "fechaIniStr")
        naive_end = parse_naive_datetime(fecha_fin_str, "fechaFinStr")
        source_tz = resolve_input_timezone(location)
    except (ValueError, InvalidLocationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    start_utc = to_utc(naive_start, source_tz)
    end_utc = to_utc(naive_end, source_tz)

    if start_utc >= end_utc:
        raise HTTPException(status_code=400, detail="fechaIniStr must be strictly before fechaFinStr")

    try:
        ensure_data_cached(db, aemet_client, identificacion, start_utc, end_utc)
    except AemetApiError as exc:
        logger.error("AEMET call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"AEMET source API error: {exc}") from exc

    rows = read_cached_measurements(db, identificacion, start_utc, end_utc)
    aggregated = aggregate_measurements(rows, aggregation, set(data_types))

    return AntartidaResponse(
        station=identificacion,
        aggregation=aggregation,
        from_datetime=fecha_ini_str,
        to_datetime=fecha_fin_str,
        tz_location_requested=location,
        count=len(aggregated),
        data=aggregated,
    )
