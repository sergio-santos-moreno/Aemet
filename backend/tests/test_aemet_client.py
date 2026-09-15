from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.aemet_client import AemetApiError, AemetClient


BASE_URL = "https://opendata.aemet.es/opendata"


@pytest.fixture()
def aemet_client(monkeypatch):
    monkeypatch.setenv("AEMET_API_KEY", "fake-key")
    monkeypatch.setenv("AEMET_BASE_URL", BASE_URL)
    from app.config import get_settings

    get_settings.cache_clear()
    client = AemetClient(client=httpx.Client())
    yield client
    client.close()
    get_settings.cache_clear()


@respx.mock
def test_fetch_antartida_readings_happy_path(aemet_client):
    first_url = (
        f"{BASE_URL}/api/antartida/datos/fechaini/2024-01-01T00:00:00UTC/"
        f"fechafin/2024-01-01T01:00:00UTC/estacion/89070"
    )
    data_url = "https://opendata.aemet.es/opendata/sh/some-temp-token"

    respx.get(first_url).mock(
        return_value=httpx.Response(200, json={"descripcion": "ok", "estado": 200, "datos": data_url})
    )
    respx.get(data_url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"identificacion": "89070", "nombre": "Gabriel de Castilla", "fhora": "2024-01-01T00:00:00",
                 "temp": -5.2, "pres": 985.3, "vel": 12.1},
            ],
        )
    )

    result = aemet_client.fetch_antartida_readings(
        "89070",
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )

    assert len(result) == 1
    assert result[0]["temp"] == -5.2


@respx.mock
def test_fetch_antartida_readings_no_data_returns_empty_list(aemet_client):
    first_url = (
        f"{BASE_URL}/api/antartida/datos/fechaini/2024-01-01T00:00:00UTC/"
        f"fechafin/2024-01-01T01:00:00UTC/estacion/89070"
    )
    respx.get(first_url).mock(return_value=httpx.Response(404))

    result = aemet_client.fetch_antartida_readings(
        "89070",
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )
    assert result == []

@respx.mock
def test_fetch_antartida_readings_soft_404_in_200_body_returns_empty_list(aemet_client):
    """
    AEMET sometimes answers with a real HTTP 200 but an embedded
    'estado': 404 in the JSON body instead of a genuine HTTP 404. This must
    be treated as "no data", not as an unexpected/malformed response.
    """
    first_url = (
        f"{BASE_URL}/api/antartida/datos/fechaini/2024-01-01T00:00:00UTC/"
        f"fechafin/2024-01-01T01:00:00UTC/estacion/89070"
    )
    respx.get(first_url).mock(
        return_value=httpx.Response(
            200, json={"descripcion": "No hay datos que satisfagan esos criterios", "estado": 404}
        )
    )

    result = aemet_client.fetch_antartida_readings(
        "89070",
        datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    )
    assert result == []

@respx.mock
def test_fetch_antartida_readings_server_error_raises_after_retries(aemet_client):
    first_url = (
        f"{BASE_URL}/api/antartida/datos/fechaini/2024-01-01T00:00:00UTC/"
        f"fechafin/2024-01-01T01:00:00UTC/estacion/89070"
    )
    respx.get(first_url).mock(return_value=httpx.Response(503))

    with pytest.raises(AemetApiError):
        aemet_client.fetch_antartida_readings(
            "89070",
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        )
