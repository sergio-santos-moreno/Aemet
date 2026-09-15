"""
Cache-aside orchestration (Part 2 of the challenge).

Strategy
--------
AEMET only publishes new Antarctic readings a few times a day, but traders
poll far more often than that to refresh their intraday view. Re-fetching
the *entire* requested range from AEMET on every request would both be slow
and risk hitting AEMET's own rate limit (50 req/min) once this service is
shared by "thousands of requests from internal applications" (per the
challenge statement).

So, per station, we track the contiguous span of data we already hold
(`FetchLog.earliest/latest_datetime_utc`) and when it was last verified
against AEMET (`last_checked_at`). On each request we only ask AEMET for
the slice we are missing:

- Cold cache for this station -> fetch the whole requested range.
- Requested range's start is before what we have -> fetch the missing
  "left" slice too (handles late backfills / first-ever historical query).
- Requested range's end is beyond `latest_datetime_utc`, OR our cached
  data is older than `CACHE_TTL_MINUTES` -> fetch the missing/possibly-
  updated "right" (most recent) slice, since that's where AEMET appends
  new readings.
- Otherwise -> served entirely from SQLite, zero calls to AEMET.

This keeps the common case (polling for the latest data within an already-
seen range) cheap, while staying correct for first-time/historical queries.
Rows are upserted by their (station_id, datetime_utc) unique constraint, so
re-fetching an overlapping slice is idempotent.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.aemet_client import AemetClient
from app.config import get_settings
from app.models_db import FetchLog, Measurement
from app.schemas import Station

logger = logging.getLogger("cache_service")


def _parse_fhora(value: str) -> datetime:
    """
    AEMET's `fhora` field for antartida readings comes back as
    'YYYY-MM-DDTHH:MM:SS', sometimes with a trailing 'Z' (Zulu/UTC marker,
    e.g. '2024-01-15T23:50:00Z') and sometimes without it -- observed to
    vary, so we strip it defensively before parsing. We requested the range
    in UTC (fechaini/fechafin with the 'UTC' suffix), and AEMET's own docs
    confirm all `antartida` observations are reported in UTC, so we treat
    `fhora` as UTC and store it as such.
    """
    if value.endswith("Z"):
        value = value[:-1]
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def _upsert_readings(db: Session, station: Station, raw_rows: list[dict]) -> int:
    inserted_or_updated = 0
    for raw in raw_rows:
        try:
            dt_utc = _parse_fhora(raw["fhora"])
        except (KeyError, ValueError):
            logger.warning("Skipping malformed AEMET row (bad/missing fhora): %r", raw)
            continue

        existing = db.execute(
            select(Measurement).where(
                Measurement.station_id == station.aemet_id,
                Measurement.datetime_utc == dt_utc.replace(tzinfo=None),
            )
        ).scalar_one_or_none()

        temp = raw.get("temp")
        pres = raw.get("pres")
        vel = raw.get("vel")

        if existing:
            existing.temperature_c = temp
            existing.pressure_hpa = pres
            existing.speed_ms = vel
        else:
            db.add(
                Measurement(
                    station_id=station.aemet_id,
                    station_name=station.value,
                    datetime_utc=dt_utc.replace(tzinfo=None),
                    temperature_c=temp,
                    pressure_hpa=pres,
                    speed_ms=vel,
                )
            )
        inserted_or_updated += 1
    return inserted_or_updated


def _get_or_create_fetch_log(db: Session, station: Station) -> FetchLog:
    log = db.get(FetchLog, station.aemet_id)
    if log is None:
        log = FetchLog(station_id=station.aemet_id)
        db.add(log)
        db.flush()
    return log


def ensure_data_cached(
    db: Session, aemet_client: AemetClient, station: Station, start_utc: datetime, end_utc: datetime
) -> None:
    """Fetch from AEMET whatever slice of [start_utc, end_utc] is missing/stale, and store it."""
    settings = get_settings()
    log = _get_or_create_fetch_log(db, station)
    now = datetime.now(timezone.utc)

    start_naive = start_utc.astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = end_utc.astimezone(timezone.utc).replace(tzinfo=None)

    ranges_to_fetch: list[tuple[datetime, datetime]] = []

    if log.latest_datetime_utc is None:
        # Cold cache for this station: fetch the whole requested range.
        ranges_to_fetch.append((start_naive, end_naive))
    else:
        is_stale = (
            log.last_checked_at is None
            or now - log.last_checked_at.replace(tzinfo=timezone.utc) > timedelta(minutes=settings.cache_ttl_minutes)
        )

        if start_naive < log.earliest_datetime_utc:
            # Requested history predates what we've ever fetched.
            ranges_to_fetch.append((start_naive, min(log.earliest_datetime_utc, end_naive)))

        if end_naive > log.latest_datetime_utc or is_stale:
            # New data may exist beyond what we last saw (or it's time to re-check).
            fetch_from = max(log.latest_datetime_utc, start_naive)
            ranges_to_fetch.append((fetch_from, end_naive))

    for range_start, range_end in ranges_to_fetch:
        if range_start >= range_end:
            continue
        logger.info(
            "Fetching from AEMET: station=%s (%s) %s -> %s",
            station.aemet_id, station.value, range_start, range_end,
        )
        raw_rows = aemet_client.fetch_antartida_readings(
            station.aemet_id,
            range_start.replace(tzinfo=timezone.utc),
            range_end.replace(tzinfo=timezone.utc),
        )
        count = _upsert_readings(db, station, raw_rows)
        logger.info("Upserted %d readings for station=%s", count, station.aemet_id)

    # Update bookkeeping regardless of whether AEMET actually had new rows,
    # so we don't hammer it again before the TTL expires.
    log.earliest_datetime_utc = (
        start_naive if log.earliest_datetime_utc is None else min(log.earliest_datetime_utc, start_naive)
    )
    log.latest_datetime_utc = (
        end_naive if log.latest_datetime_utc is None else max(log.latest_datetime_utc, end_naive)
    )
    log.last_checked_at = now.replace(tzinfo=None)
    db.commit()


def read_cached_measurements(
    db: Session, station: Station, start_utc: datetime, end_utc: datetime
) -> list[Measurement]:
    start_naive = start_utc.astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = end_utc.astimezone(timezone.utc).replace(tzinfo=None)
    return list(
        db.execute(
            select(Measurement)
            .where(
                Measurement.station_id == station.aemet_id,
                Measurement.datetime_utc >= start_naive,
                Measurement.datetime_utc <= end_naive,
            )
            .order_by(Measurement.datetime_utc)
        ).scalars()
    )
