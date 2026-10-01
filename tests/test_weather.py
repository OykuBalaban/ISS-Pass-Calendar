from datetime import datetime, timedelta, timezone

import pytest

from conftest import MUNICH, T0
from isspass import weather
from isspass.models import Location
from isspass.predictor import PassPredictor
from isspass.service import PassService


def fake_body(start_local, hours, clouds, days=2):
    times = [(start_local + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(hours)]
    day0 = start_local.date()
    return {
        "hourly": {"time": times, "cloud_cover": [clouds(h) for h in range(hours)]},
        "daily": {
            "time": [(day0 + timedelta(days=d)).isoformat() for d in range(days)],
            "weather_code": [2] * days,
            "temperature_2m_max": [15.4] * days,
            "temperature_2m_min": [8.6] * days,
        },
    }


def test_parse_converts_local_hours_to_utc():
    body = fake_body(datetime(2014, 1, 21, 0, 0), 3, lambda h: 10 * h)
    f = weather.parse(body, "Europe/Berlin")
    assert f["hours"][0] == "2014-01-20T23:00:00+00:00"
    assert weather.clouds_at(f, datetime(2014, 1, 21, 0, 20, tzinfo=timezone.utc)) == 10


def test_clouds_far_from_any_hour_are_unknown():
    f = weather.parse(fake_body(datetime(2014, 1, 21), 3, lambda h: 50), "UTC")
    assert weather.clouds_at(f, datetime(2014, 1, 25, tzinfo=timezone.utc)) is None


def test_sky_classes():
    assert [weather.sky(c) for c in (None, 0, 25, 26, 60, 61, 100)] == [
        None, "clear", "clear", "partly", "partly", "cloudy", "cloudy"]


def test_day_summary():
    f = weather.parse(fake_body(datetime(2014, 1, 21), 24, lambda h: 50), "UTC")
    today = weather.day_summary(f, datetime(2014, 1, 21).date())
    assert today == {"text": "Partly cloudy", "code": 2, "tmin": 9, "tmax": 15}
    assert weather.day_summary(f, datetime(2015, 1, 1).date()) is None


def test_bad_answer_is_reported():
    with pytest.raises(weather.WeatherError):
        weather.parse({"hourly": {}}, "UTC")


def test_offline_keeps_the_saved_forecast(repo):
    loc_id = repo.use_location(Location("Munich", 48.1351, 11.582, "Europe/Berlin"))
    loc = repo.location(loc_id)
    good = weather.parse(fake_body(datetime(2014, 1, 21), 24, lambda h: 5), "Europe/Berlin")
    svc = PassService(repo, PassPredictor(), weather_downloader=lambda l: good)
    assert svc.ensure_weather(loc)["ok"]

    def offline(l):
        raise weather.WeatherError("Weather could not be downloaded.")
    svc2 = PassService(repo, PassPredictor(), weather_downloader=offline)
    assert svc2.update_weather(loc)[0] is False
    forecast, _ = repo.weather(loc.id)
    assert forecast["clouds"][0] == 5
