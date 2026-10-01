import socket

import pytest

from conftest import SAMPLE_TEXT, T0


@pytest.fixture
def client(monkeypatch):
    def blocked(*a, **k):
        raise OSError("network blocked in test")
    monkeypatch.setattr(socket, "create_connection", blocked)

    import isspass.web.routes as routes
    monkeypatch.setattr(routes, "now", lambda: T0)
    from isspass.web import create_app
    app = create_app({"DATABASE": ":memory:", "TESTING": True, "AUTO_UPDATE": True, "BACKGROUND_UPDATE": False})
    return app.test_client()


def test_first_run_has_no_location(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/passes").json["location"] is None


def test_choose_city_then_data_explains_offline(client):
    place = client.get("/api/places?q=kesan").json[0]
    assert place["name"] == "Keşan"
    loc = client.post("/api/locations", json={"placeId": place["id"]}).json
    assert loc["name"] == "Keşan, Turkey" and loc["isDefault"] and not loc["isFavorite"]
    body = client.get("/api/passes").json
    assert body["data"]["state"] == "none"
    assert body["favorites"] == []
    assert "No internet" in body["update"]["message"]


def test_current_location_gets_a_readable_name(client):
    loc = client.post("/api/locations", json={"latitude": 40.95, "longitude": 26.70}).json
    assert loc["name"].startswith("Near Keşan") or loc["name"].startswith("Keşan")
    assert loc["timezone"] == "Europe/Istanbul"
    assert client.post("/api/locations", json={"latitude": 123, "longitude": 0}).status_code == 400


def test_full_flow_offline_with_pasted_data(client):
    place = client.get("/api/places?q=munich").json[0]
    client.post("/api/locations", json={"placeId": place["id"]})
    res = client.post("/offline/file", data={"tle": SAMPLE_TEXT}, follow_redirects=True)
    assert res.status_code == 200
    visible = client.get("/api/passes?all=0").json
    every = client.get("/api/passes?all=1").json
    assert visible["data"]["state"] == "fresh"
    assert all(p["visible"] for p in visible["passes"])
    assert len(every["passes"]) > len(visible["passes"]) > 0
    first = visible["passes"][0]
    assert first["from"]["words"] and first["path"] and first["peak"]


def test_favorites_only_when_asked(client):
    a = client.post("/api/locations", json={"placeId": client.get("/api/places?q=edirne").json[0]["id"]}).json
    b = client.post("/api/locations", json={"placeId": client.get("/api/places?q=landshut").json[0]["id"]}).json
    assert client.get("/api/passes").json["location"]["id"] == b["id"]
    assert client.get("/api/passes").json["favorites"] == []
    fav = client.post(f"/api/locations/{a['id']}/favorite", json={"favorite": True}).json
    assert fav["isFavorite"]
    assert [f["name"] for f in client.get("/api/passes").json["favorites"]] == ["Edirne, Turkey"]
    assert [r["name"] for r in client.get("/api/locations/recent").json] == ["Landshut, Germany", "Edirne, Turkey"]


def test_bad_file_is_explained(client):
    import io
    res = client.post("/offline/file", data={"file": (io.BytesIO(b"1 25544U nonsense"), "iss.txt")},
                      content_type="multipart/form-data", follow_redirects=True)
    assert b"exactly two TLE lines" in res.data


def test_file_upload_loads_data(client):
    import io
    res = client.post("/offline/file", data={"file": (io.BytesIO(SAMPLE_TEXT.encode()), "iss.txt")},
                      content_type="multipart/form-data", follow_redirects=True)
    assert b"Ready to use offline" in res.data


def test_same_place_is_not_saved_twice(client):
    pid = client.get("/api/places?q=kesan").json[0]["id"]
    first = client.post("/api/locations", json={"placeId": pid}).json
    again = client.post("/api/locations", json={"placeId": pid}).json
    near = client.post("/api/locations", json={"latitude": 40.858, "longitude": 26.636}).json
    assert first["id"] == again["id"] == near["id"]
    assert len(client.get("/api/locations/recent").json) == 1
    client.post(f"/api/locations/{first['id']}/favorite", json={"favorite": True})
    client.post(f"/api/locations/{first['id']}/favorite", json={"favorite": True})
    assert len(client.get("/api/passes").json["favorites"]) == 1
    assert client.get("/api/places?q=kesan").json[0]["favorite"] is True


def test_offline_page_states(client):
    assert b"Not ready yet" in client.get("/offline").data
    client.post("/offline/file", data={"tle": SAMPLE_TEXT})
    page = client.get("/offline").data
    assert b"Ready to use offline" in page and b"27 January" in page


def test_favorites_page(client):
    pid = client.get("/api/places?q=edirne").json[0]["id"]
    loc = client.post("/api/locations", json={"placeId": pid}).json
    assert b"No favorites yet" in client.get("/favorites").data
    client.post(f"/api/locations/{loc['id']}/favorite", json={"favorite": True})
    assert b"Edirne, Turkey" in client.get("/favorites").data
    client.post(f"/favorites/{loc['id']}/remove")
    assert b"No favorites yet" in client.get("/favorites").data


def test_coordinates_with_own_name(client):
    loc = client.post("/api/locations", json={"latitude": 40.9, "longitude": 26.7, "name": "Kilickoy"}).json
    assert loc["name"] == "Kilickoy" and loc["timezone"] == "Europe/Istanbul"


def test_istanbul_is_not_saved_twice(client):
    here = client.post("/api/locations", json={"latitude": 41.0082, "longitude": 28.9784}).json
    assert here["name"] == "Istanbul, Turkey"
    pid = client.get("/api/places?q=istanbul").json[0]["id"]
    assert client.post("/api/locations", json={"placeId": pid}).json["id"] == here["id"]
    assert len(client.get("/api/locations/recent").json) == 1


def test_add_favorite_without_a_location(client):
    res = client.post("/favorites/add-current", follow_redirects=True)
    assert b"Please select a location." in res.data
    pid = client.get("/api/places?q=edirne").json[0]["id"]
    client.post("/api/locations", json={"placeId": pid})
    res = client.post("/favorites/add-current", follow_redirects=True)
    assert b"Edirne, Turkey added to favorites." in res.data
    res = client.post("/favorites/add-current", follow_redirects=True)
    assert b"already in your favorites" in res.data


def test_update_button_reports_offline(client):
    res = client.post("/api/data/update")
    assert res.status_code == 503 and "No internet" in res.json["message"]


def test_passes_show_clouds_and_todays_weather(client):
    from datetime import datetime, timedelta
    from isspass import weather
    from flask import current_app
    pid = client.get("/api/places?q=munich").json[0]["id"]
    loc = client.post("/api/locations", json={"placeId": pid}).json
    client.post("/offline/file", data={"tle": SAMPLE_TEXT})
    start = datetime(2014, 1, 21, 0, 0)
    body = {
        "hourly": {"time": [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(24 * 6)],
                   "cloud_cover": [90 if h < 30 else 0 for h in range(24 * 6)]},
        "daily": {"time": [(start + timedelta(days=d)).date().isoformat() for d in range(6)],
                  "weather_code": [3, 0, 0, 0, 0, 0], "temperature_2m_max": [4] * 6, "temperature_2m_min": [-2] * 6},
    }
    forecast = weather.parse(body, "Europe/Berlin")
    with client.application.app_context():
        current_app.extensions["isspass"]["repo"].save_weather(loc["id"], forecast, datetime.now(T0.tzinfo))
    data = client.get("/api/passes").json
    assert data["weather"]["today"]["text"] == "Overcast"
    skies = [p["sky"] for p in data["passes"]]
    assert "cloudy" in skies and "clear" in skies
    assert all(p["clouds"] is None or 0 <= p["clouds"] <= 100 for p in data["passes"])
    cloudy = [p["score"] for p in data["passes"] if p["sky"] == "cloudy"]
    clear = [p["score"] for p in data["passes"] if p["sky"] == "clear"]
    assert max(cloudy) < min(clear)
    assert all(0 <= p["score"] <= 10 for p in data["passes"])
