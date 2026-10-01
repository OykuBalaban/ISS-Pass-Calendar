import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from isspass.tle import USER_AGENT, _ssl_context

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    56: "Freezing drizzle", 57: "Freezing drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Snow showers", 95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}


class WeatherError(Exception):
    pass


def download(location, days=10, timeout=12):
    query = urllib.parse.urlencode({
        "latitude": location.latitude,
        "longitude": location.longitude,
        "hourly": "cloud_cover,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "timezone": location.timezone,
        "forecast_days": days,
    })
    req = urllib.request.Request(f"{FORECAST_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
            body = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        raise WeatherError("Weather could not be downloaded.")
    return parse(body, location.timezone)


def parse(body, tz_name):
    try:
        tz = ZoneInfo(tz_name)
        hourly = body["hourly"]
        daily = body["daily"]
        hours = [datetime.fromisoformat(t).replace(tzinfo=tz).astimezone(timezone.utc).isoformat()
                 for t in hourly["time"]]
        return {
            "hours": hours,
            "clouds": hourly["cloud_cover"],
            "hour_codes": hourly.get("weather_code"),
            "days": daily["time"],
            "codes": daily["weather_code"],
            "tmax": daily["temperature_2m_max"],
            "tmin": daily["temperature_2m_min"],
        }
    except (KeyError, TypeError, ValueError):
        raise WeatherError("Weather data has an unexpected format.")


def weather_at(forecast, when):
    if not forecast or not forecast["hours"]:
        return None, None
    codes = forecast.get("hour_codes") or [None] * len(forecast["hours"])
    best, best_gap = None, None
    for t, c, code in zip(forecast["hours"], forecast["clouds"], codes):
        gap = abs((datetime.fromisoformat(t) - when).total_seconds())
        if c is not None and gap <= 3600 and (best_gap is None or gap < best_gap):
            best, best_gap = (int(round(c)), code), gap
    return best if best else (None, None)


def clouds_at(forecast, when):
    return weather_at(forecast, when)[0]


def sky(clouds):
    if clouds is None:
        return None
    if clouds <= 25:
        return "clear"
    if clouds <= 60:
        return "partly"
    return "cloudy"


def day_summary(forecast, day):
    if not forecast:
        return None
    key = day.isoformat()
    if key not in forecast["days"]:
        return None
    i = forecast["days"].index(key)
    code = forecast["codes"][i]
    return {
        "text": CODES.get(code, "Unknown"),
        "code": code,
        "tmin": None if forecast["tmin"][i] is None else round(forecast["tmin"][i]),
        "tmax": None if forecast["tmax"][i] is None else round(forecast["tmax"][i]),
    }
