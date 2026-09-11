"""
ORM models for the SQLite cache.

Two tables:

- `Measurement`: one row per (station, timestamp) raw 10-min reading, the
  finest granularity AEMET provides. Everything else (hourly/daily/monthly
  aggregation) is computed on read from these rows, so we never lose
  information by pre-aggregating on write.

- `FetchLog`: bookkeeping of what we already know for each station, so a
  new request can figure out whether AEMET needs to be called at all, and
  if so, only for the *missing* slice of the range. Antarctic AEMET data is
  an append-mostly timeseries (new readings land at the end a few times a
  day), so tracking "we have everything up to timestamp X, checked at
  time Y" is enough to make the cache effective without a full interval-
  tree implementation.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("station_id", "datetime_utc", name="uq_station_datetime"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    station_id: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    station_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Always stored normalised to UTC (naive datetime, UTC implied) so that
    # querying by range and sorting is unambiguous regardless of how the
    # value is later displayed (Europe/Madrid, with DST-aware offset).
    datetime_utc: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class FetchLog(Base):
    """One row per station: what range of data we already hold locally."""

    __tablename__ = "fetch_log"

    station_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    earliest_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latest_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
