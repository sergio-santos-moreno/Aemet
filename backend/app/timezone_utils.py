"""
Timezone handling.

Two independent timezone concerns exist in this API, and it's important not
to conflate them:

1. INPUT timezone: the `location` query parameter tells us how to interpret
   the naive `fechaIniStr` / `fechaFinStr` strings the user typed
   (e.g. "2024-01-15T10:00:00" in "Europe/Berlin" vs the same string in
   "+02:00"). We only use this to convert the requested range to UTC before
   querying data.

   Design decision: if `location` is omitted, we assume the input strings
   are already UTC. This is documented in the API docstring/README because
   the challenge statement leaves the "no location given" case unspecified.

2. OUTPUT / AGGREGATION timezone: per the challenge statement, the output
   `Datetime` field must always be expressed in CET/CEST (Europe/Madrid),
   including the UTC offset, *regardless* of what `location` the user
   passed for the input. Daily/monthly aggregation buckets must also be
   computed against Europe/Madrid calendar days/months -- not UTC days --
   because a UTC day and a Madrid day disagree for part of the year once
   DST shifts the offset by an hour.

We use the stdlib `zoneinfo` (PEP 615) instead of `pytz`: zoneinfo lets
Python resolve DST transitions automatically from the IANA tz database
whenever we attach it to a datetime, with no manual `.localize()`/
`.normalize()` dance that `pytz` requires (a very common source of subtle
DST bugs).
"""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MADRID_TZ = ZoneInfo("Europe/Madrid")

_OFFSET_RE = re.compile(r"^([+-])(\d{2}):(\d{2})$")


class InvalidLocationError(ValueError):
    pass


def resolve_input_timezone(location: str | None) -> timezone | ZoneInfo:
    """
    Turn the optional `location` query param into a tzinfo object.

    Accepts either:
    - an IANA timezone name, e.g. "Europe/Berlin" -> ZoneInfo (DST-aware)
    - a fixed UTC offset, e.g. "+02:00" -> datetime.timezone (fixed, not DST-aware,
      exactly as the challenge statement's example implies)

    Defaults to UTC when no location is supplied.
    """
    if not location:
        return timezone.utc

    match = _OFFSET_RE.match(location)
    if match:
        sign, hours, minutes = match.groups()
        delta = timedelta(hours=int(hours), minutes=int(minutes))
        if sign == "-":
            delta = -delta
        return timezone(delta)

    try:
        return ZoneInfo(location)
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain-specific error
        raise InvalidLocationError(
            f"'{location}' is not a valid IANA timezone name nor a '+HH:MM'/'-HH:MM' offset."
        ) from exc


def parse_naive_datetime(value: str, field_name: str) -> datetime:
    """Parse an 'AAAA-MM-DDTHH:MM:SS' string, as mandated by the challenge statement."""
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValueError(
            f"{field_name}='{value}' must have format YYYY-MM-DDTHH:MM:SS"
        ) from exc


def to_utc(naive_dt: datetime, source_tz: timezone | ZoneInfo) -> datetime:
    """Attach the source timezone and convert to an aware UTC datetime."""
    return naive_dt.replace(tzinfo=source_tz).astimezone(timezone.utc)


def utc_to_madrid(utc_dt: datetime) -> datetime:
    """Convert an (aware or naive-assumed-UTC) datetime to aware Europe/Madrid time."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(MADRID_TZ)


def format_iso_with_offset(dt: datetime) -> str:
    """'2024-01-15T10:00:00+01:00' style formatting, always including the offset."""
    return dt.isoformat(timespec="seconds")
