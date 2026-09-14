"""
Aggregation of raw 10-min readings into hourly/daily/monthly buckets.

Implemented with plain Python (dict-based group-by) rather than pandas: the
volume of data for a single station/date-range request is small (a few
thousand 10-min rows at most) so pandas would be a heavier dependency for no
real benefit, and a hand-rolled group-by is easy to unit test in isolation.

Bucketing always happens on the Europe/Madrid representation of each
timestamp (see timezone_utils for why), so a "day" or "month" always means a
Madrid calendar day/month, DST included.
"""
from collections import defaultdict
from datetime import datetime

from app.models_db import Measurement
from app.schemas import DataType, MeasurementOut, TimeAggregation
from app.timezone_utils import format_iso_with_offset, utc_to_madrid

_FIELD_BY_DATATYPE = {
    DataType.TEMPERATURE: "temperature_c",
    DataType.PRESSURE: "pressure_hpa",
    DataType.SPEED: "speed_ms",
}


def _selected_fields(data_types: set[DataType]) -> list[str]:
    """Empty selection means 'all three', per the challenge statement."""
    if not data_types:
        data_types = set(DataType)
    return [_FIELD_BY_DATATYPE[dt] for dt in data_types]


def _bucket_start(madrid_dt: datetime, aggregation: TimeAggregation) -> datetime:
    if aggregation is TimeAggregation.HOURLY:
        return madrid_dt.replace(minute=0, second=0, microsecond=0)
    if aggregation is TimeAggregation.DAILY:
        return madrid_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    if aggregation is TimeAggregation.MONTHLY:
        return madrid_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"_bucket_start called with non-aggregating value: {aggregation}")


def aggregate_measurements(
    rows: list[Measurement],
    aggregation: TimeAggregation,
    data_types: set[DataType],
) -> list[MeasurementOut]:
    fields = _selected_fields(data_types)

    if aggregation is TimeAggregation.NONE:
        out = []
        for row in sorted(rows, key=lambda r: r.datetime_utc):
            madrid_dt = utc_to_madrid(row.datetime_utc)
            out.append(
                MeasurementOut(
                    station=row.station_name,
                    datetime=format_iso_with_offset(madrid_dt),
                    temperature_c=row.temperature_c if "temperature_c" in fields else None,
                    pressure_hpa=row.pressure_hpa if "pressure_hpa" in fields else None,
                    speed_ms=row.speed_ms if "speed_ms" in fields else None,
                )
            )
        return out

    # Group raw rows into buckets keyed by (bucket_start, station_name)
    buckets: dict[tuple[datetime, str], list[Measurement]] = defaultdict(list)
    for row in rows:
        madrid_dt = utc_to_madrid(row.datetime_utc)
        bucket_key = (_bucket_start(madrid_dt, aggregation), row.station_name)
        buckets[bucket_key].append(row)

    out = []
    for (bucket_start, station_name), bucket_rows in sorted(buckets.items(), key=lambda kv: kv[0][0]):
        averaged = {}
        for field in fields:
            values = [getattr(r, field) for r in bucket_rows if getattr(r, field) is not None]
            averaged[field] = round(sum(values) / len(values), 2) if values else None

        out.append(
            MeasurementOut(
                station=station_name,
                datetime=format_iso_with_offset(bucket_start),
                temperature_c=averaged.get("temperature_c"),
                pressure_hpa=averaged.get("pressure_hpa"),
                speed_ms=averaged.get("speed_ms"),
            )
        )
    return out
