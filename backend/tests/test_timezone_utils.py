from datetime import datetime, timezone

import pytest

from app.timezone_utils import (
    InvalidLocationError,
    format_iso_with_offset,
    parse_naive_datetime,
    resolve_input_timezone,
    to_utc,
    utc_to_madrid,
)


def test_parse_naive_datetime_ok():
    dt = parse_naive_datetime("2024-01-15T10:30:00", "fechaIniStr")
    assert dt == datetime(2024, 1, 15, 10, 30, 0)


def test_parse_naive_datetime_bad_format_raises():
    with pytest.raises(ValueError):
        parse_naive_datetime("15/01/2024 10:30", "fechaIniStr")


def test_resolve_input_timezone_defaults_to_utc():
    assert resolve_input_timezone(None) is timezone.utc


def test_resolve_input_timezone_fixed_offset():
    tz = resolve_input_timezone("+02:00")
    dt = datetime(2024, 6, 1, 12, 0, 0, tzinfo=tz)
    assert dt.utcoffset().total_seconds() == 2 * 3600


def test_resolve_input_timezone_iana_name():
    tz = resolve_input_timezone("Europe/Berlin")
    dt_summer = datetime(2024, 6, 1, 12, 0, 0, tzinfo=tz)
    # Berlin is UTC+2 in summer (CEST)
    assert dt_summer.utcoffset().total_seconds() == 2 * 3600


def test_resolve_input_timezone_invalid_raises():
    with pytest.raises(InvalidLocationError):
        resolve_input_timezone("Not/A_Real_Zone")


def test_to_utc_conversion():
    naive = datetime(2024, 6, 1, 12, 0, 0)
    tz = resolve_input_timezone("+02:00")
    result = to_utc(naive, tz)
    assert result == datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


def test_madrid_offset_is_dst_aware():
    """
    Core DST requirement from the challenge statement: the same UTC instant
    must map to different Madrid offsets depending on the time of year
    (CET = +01:00 in winter, CEST = +02:00 in summer).
    """
    winter_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    summer_utc = datetime(2024, 7, 15, 12, 0, 0, tzinfo=timezone.utc)

    winter_madrid = utc_to_madrid(winter_utc)
    summer_madrid = utc_to_madrid(summer_utc)

    assert winter_madrid.utcoffset().total_seconds() == 1 * 3600
    assert summer_madrid.utcoffset().total_seconds() == 2 * 3600

    assert format_iso_with_offset(winter_madrid).endswith("+01:00")
    assert format_iso_with_offset(summer_madrid).endswith("+02:00")


def test_dst_transition_boundary():
    """
    2024's spring-forward happened at 2024-03-31 01:00 UTC (Madrid clocks
    jumped from 02:00 CET straight to 03:00 CEST). Readings either side of
    that instant must carry different offsets even though they're only
    seconds apart in UTC.
    """
    just_before = datetime(2024, 3, 31, 0, 59, 59, tzinfo=timezone.utc)
    just_after = datetime(2024, 3, 31, 1, 0, 1, tzinfo=timezone.utc)

    assert utc_to_madrid(just_before).utcoffset().total_seconds() == 1 * 3600
    assert utc_to_madrid(just_after).utcoffset().total_seconds() == 2 * 3600
