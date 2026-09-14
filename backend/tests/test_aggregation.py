from datetime import datetime, timezone

from app.aggregation import aggregate_measurements
from app.models_db import Measurement
from app.schemas import DataType, TimeAggregation


def _row(dt: datetime, temp: float, pres: float, vel: float) -> Measurement:
    return Measurement(
        station_id="89070",
        station_name="Meteo Station Gabriel de Castilla",
        datetime_utc=dt,
        temperature_c=temp,
        pressure_hpa=pres,
        speed_ms=vel,
    )


def test_none_aggregation_returns_every_row_unaggregated():
    rows = [
        _row(datetime(2024, 1, 1, 0, 0), 1.0, 990.0, 5.0),
        _row(datetime(2024, 1, 1, 0, 10), 2.0, 991.0, 6.0),
    ]
    out = aggregate_measurements(rows, TimeAggregation.NONE, set())
    assert len(out) == 2
    assert out[0].temperature_c == 1.0
    assert out[1].temperature_c == 2.0


def test_empty_data_types_returns_all_fields():
    rows = [_row(datetime(2024, 1, 1, 0, 0), 1.0, 990.0, 5.0)]
    out = aggregate_measurements(rows, TimeAggregation.NONE, set())
    assert out[0].temperature_c is not None
    assert out[0].pressure_hpa is not None
    assert out[0].speed_ms is not None


def test_selected_data_types_filters_other_fields_to_none():
    rows = [_row(datetime(2024, 1, 1, 0, 0), 1.0, 990.0, 5.0)]
    out = aggregate_measurements(rows, TimeAggregation.NONE, {DataType.TEMPERATURE})
    assert out[0].temperature_c == 1.0
    assert out[0].pressure_hpa is None
    assert out[0].speed_ms is None


def test_hourly_aggregation_averages_within_the_hour():
    rows = [
        _row(datetime(2024, 1, 1, 10, 0), 1.0, 990.0, 4.0),
        _row(datetime(2024, 1, 1, 10, 10), 3.0, 992.0, 6.0),
        _row(datetime(2024, 1, 1, 11, 0), 100.0, 900.0, 50.0),  # different hour bucket
    ]
    out = aggregate_measurements(rows, TimeAggregation.HOURLY, set())
    assert len(out) == 2
    assert out[0].temperature_c == 2.0  # average of 1.0 and 3.0
    assert out[1].temperature_c == 100.0


def test_daily_aggregation_uses_madrid_calendar_day_not_utc_day():
    """
    23:30 UTC on 2024-01-01 is already 2024-01-02 00:30 in Madrid (CET,
    +01:00 in winter). Aggregating "daily" must bucket this reading into
    Jan 2nd in Madrid time, not Jan 1st (the UTC day).
    """
    rows = [_row(datetime(2024, 1, 1, 23, 30, tzinfo=timezone.utc), 5.0, 1000.0, 1.0)]
    out = aggregate_measurements(rows, TimeAggregation.DAILY, {DataType.TEMPERATURE})
    assert len(out) == 1
    assert out[0].datetime.startswith("2024-01-02")


def test_monthly_aggregation_buckets_by_month():
    rows = [
        _row(datetime(2024, 1, 5, 10, 0), 1.0, 990.0, 4.0),
        _row(datetime(2024, 1, 20, 10, 0), 3.0, 992.0, 6.0),
        _row(datetime(2024, 2, 1, 10, 0), 10.0, 995.0, 1.0),
    ]
    out = aggregate_measurements(rows, TimeAggregation.MONTHLY, {DataType.TEMPERATURE})
    assert len(out) == 2
    assert out[0].temperature_c == 2.0
    assert out[1].temperature_c == 10.0
