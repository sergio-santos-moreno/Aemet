"""
Thin client around AEMET OpenData's "antartida" endpoint.

AEMET's API uses a two-step indirection on every data endpoint:
  1. GET .../api/antartida/datos/fechaini/{ini}/fechafin/{fin}/estacion/{id}
     -> returns a small JSON with a `datos` field containing a *temporary*
        URL where the actual payload lives.
  2. GET that `datos` URL -> the actual list of readings.

The API key is sent both as a header (`api_key`) and query string param for
compatibility, as AEMET's own examples aren't fully consistent across
endpoint versions and this is the safest combination in practice.

Retries: AEMET is a public-sector service known to be occasionally slow or
to rate-limit (50 req/min per their own docs), so transient 5xx/429/timeouts
are retried with exponential backoff via `tenacity`. A 404 (no data for the
requested station/range) is treated as "empty result", not an error.
"""
import logging
from datetime import datetime, timezone

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger("aemet_client")


class AemetApiError(RuntimeError):
    """Raised when AEMET returns something we can't recover from."""


class AemetNoDataError(RuntimeError):
    """Raised when AEMET has no data for the requested station/range."""


def _format_aemet_datetime(dt_utc: datetime) -> str:
    """AEMET expects 'YYYY-MM-DDTHH:MM:SSUTC' (literal 'UTC' suffix, no colon/offset)."""
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S") + "UTC"


class AemetClient:
    def __init__(self, client: httpx.Client | None = None):
        settings = get_settings()
        self._base_url = settings.aemet_base_url.rstrip("/")
        self._api_key = settings.aemet_api_key
        # Allow injecting a client (e.g. respx-mocked) in tests.
        self._client = client or httpx.Client(timeout=30.0)

    @property
    def _headers(self) -> dict[str, str]:
        return {"api_key": self._api_key, "Accept": "application/json"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TransportError, AemetApiError)),
        reraise=True,
    )
    def _get_json(self, url: str, params: dict | None = None) -> dict | list:
        response = self._client.get(url, headers=self._headers, params=params)
        if response.status_code == 404:
            raise AemetNoDataError(f"AEMET returned 404 for {url}")
        if response.status_code == 429:
            raise AemetApiError("AEMET rate limit exceeded (429)")
        if response.status_code >= 500:
            raise AemetApiError(f"AEMET server error {response.status_code}")
        response.raise_for_status()
        return response.json()

    def fetch_antartida_readings(
        self, station_id: str, start_utc: datetime, end_utc: datetime
    ) -> list[dict]:
        """
        Fetch raw readings for one station between start_utc/end_utc (inclusive),
        both timezone-aware UTC datetimes. Returns AEMET's raw dict payloads
        (still containing the original Spanish field names, e.g. `fhora`,
        `temp`, `pres`, `vel`) -- mapping to our domain model happens in the
        cache service, keeping this client a dumb, easily-mockable transport
        layer.
        """
        start_utc = start_utc.astimezone(timezone.utc)
        end_utc = end_utc.astimezone(timezone.utc)

        url = (
            f"{self._base_url}/api/antartida/datos/"
            f"fechaini/{_format_aemet_datetime(start_utc)}/"
            f"fechafin/{_format_aemet_datetime(end_utc)}/"
            f"estacion/{station_id}"
        )

        try:
            first_response = self._get_json(url)
        except AemetNoDataError:
            logger.info("AEMET has no data for station=%s range=%s..%s", station_id, start_utc, end_utc)
            return []

        # AEMET sometimes wraps a "no data" result inside an HTTP 200 response
        # (e.g. {"descripcion": "No hay datos...", "estado": 404}) instead of
        # a real HTTP 404. Its own "estado" field is the authoritative status
        # here, so treat a non-200 "estado" the same as a real 404.
        if isinstance(first_response, dict) and first_response.get("estado") not in (200, None):
            logger.info(
                "AEMET reported no data (estado=%s) for station=%s range=%s..%s",
                first_response.get("estado"), station_id, start_utc, end_utc,
            )
            return []

        if not isinstance(first_response, dict) or "datos" not in first_response:
            raise AemetApiError(f"Unexpected AEMET response shape: {first_response!r}")

        data_url = first_response["datos"]
        try:
            payload = self._get_json(data_url)
        except AemetNoDataError:
            return []

        if not isinstance(payload, list):
            raise AemetApiError(f"Unexpected AEMET data payload shape: {type(payload)}")

        return payload

    def close(self) -> None:
        self._client.close()
