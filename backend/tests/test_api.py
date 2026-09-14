def _fake_reading(fhora: str, temp: float, pres: float, vel: float) -> dict:
    return {"identificacion": "89070", "nombre": "Gabriel de Castilla", "fhora": fhora,
            "temp": temp, "pres": pres, "vel": vel}


def test_get_antartida_datos_happy_path(client, fake_aemet_client):
    fake_aemet_client.readings = [
        _fake_reading("2024-01-01T10:00:00", -5.0, 990.0, 3.0),
        _fake_reading("2024-01-01T10:10:00", -4.5, 991.0, 3.5),
    ]

    response = client.get(
        "/api/antartida/datos/fechaini/2024-01-01T10:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["station"] == "Meteo Station Gabriel de Castilla"
    assert body["count"] == 2
    assert body["data"][0]["temperature_c"] == -5.0
    # Datetime must include a UTC offset (Europe/Madrid, winter -> +01:00)
    assert body["data"][0]["datetime"].endswith("+01:00")


def test_get_antartida_datos_filters_data_types(client, fake_aemet_client):
    fake_aemet_client.readings = [_fake_reading("2024-01-01T10:00:00", -5.0, 990.0, 3.0)]

    response = client.get(
        "/api/antartida/datos/fechaini/2024-01-01T10:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla",
        params={"data_types": "temperature"},
    )

    assert response.status_code == 200
    row = response.json()["data"][0]
    assert row["temperature_c"] == -5.0
    assert row["pressure_hpa"] is None
    assert row["speed_ms"] is None


def test_get_antartida_datos_hourly_aggregation(client, fake_aemet_client):
    fake_aemet_client.readings = [
        _fake_reading("2024-01-01T10:00:00", -6.0, 990.0, 2.0),
        _fake_reading("2024-01-01T10:30:00", -4.0, 990.0, 4.0),
    ]

    response = client.get(
        "/api/antartida/datos/fechaini/2024-01-01T10:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla",
        params={"time_aggregation": "hourly"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["temperature_c"] == -5.0  # average of -6.0 and -4.0


def test_get_antartida_datos_invalid_date_format_returns_400(client):
    response = client.get(
        "/api/antartida/datos/fechaini/01-01-2024/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla"
    )
    assert response.status_code == 400


def test_get_antartida_datos_invalid_station_returns_422(client):
    response = client.get(
        "/api/antartida/datos/fechaini/2024-01-01T10:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Not A Real Station"
    )
    assert response.status_code == 422


def test_get_antartida_datos_start_after_end_returns_400(client):
    response = client.get(
        "/api/antartida/datos/fechaini/2024-01-01T12:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla"
    )
    assert response.status_code == 400


def test_second_request_within_ttl_does_not_call_aemet_again(client, fake_aemet_client):
    fake_aemet_client.readings = [_fake_reading("2024-01-01T10:00:00", -5.0, 990.0, 3.0)]

    path = (
        "/api/antartida/datos/fechaini/2024-01-01T10:00:00/fechafin/2024-01-01T11:00:00/"
        "estacion/Meteo Station Gabriel de Castilla"
    )
    first = client.get(path)
    assert first.status_code == 200
    calls_after_first = len(fake_aemet_client.calls)
    assert calls_after_first >= 1

    second = client.get(path)
    assert second.status_code == 200
    # Cache hit: no additional AEMET calls for the exact same, already-fresh range.
    assert len(fake_aemet_client.calls) == calls_after_first
