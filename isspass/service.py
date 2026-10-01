import threading
import time
from datetime import datetime, timedelta, timezone

from isspass import tle, weather

GOOD_DAYS = 7
EXPIRED_DAYS = 14
REFRESH_AFTER_HOURS = 12
RETRY_MINUTES = 30
DAYS_AHEAD = 10
CACHE_HOURS = 6
WEATHER_REFRESH_HOURS = 3


class PassService:
    def __init__(self, repo, predictor, auto_update=True, downloader=tle.download,
                 weather_downloader=weather.download):
        self.repo = repo
        self.predictor = predictor
        self.auto_update = auto_update
        self.downloader = downloader
        self.weather_downloader = weather_downloader
        self._cache = {}
        self._last_attempt = None
        self._weather_attempts = {}
        self._lock = threading.Lock()

    def data_status(self, now):
        t = self.repo.latest_tle()
        if t is None:
            return {"state": "none", "ageDays": None, "epoch": None, "source": None,
                    "goodUntil": None, "savedAt": None}
        age = t.age_days(now)
        if age < -1 or age > EXPIRED_DAYS:
            state = "expired"
        elif age > GOOD_DAYS:
            state = "old"
        else:
            state = "fresh"
        return {"state": state, "ageDays": round(age, 2), "epoch": t.epoch, "source": t.source,
                "goodUntil": t.epoch + timedelta(days=GOOD_DAYS), "savedAt": t.saved_at}

    def update_now(self, now):
        with self._lock:
            self._last_attempt = datetime.now(timezone.utc)
            try:
                new = self.downloader()
            except tle.TleError as exc:
                return False, str(exc)
            self.repo.save_tle(new, now)
            self._cache = {}
            return True, "Orbit data updated."

    def update_weather(self, location):
        self._weather_attempts[location.id] = datetime.now(timezone.utc)
        try:
            forecast = self.weather_downloader(location)
        except weather.WeatherError as exc:
            return False, str(exc)
        self.repo.save_weather(location.id, forecast, datetime.now(timezone.utc))
        return True, "Weather updated."

    def ensure_weather(self, location):
        if not self.auto_update or location is None:
            return None
        _, fetched = self.repo.weather(location.id)
        real_now = datetime.now(timezone.utc)
        if fetched and real_now - fetched < timedelta(hours=WEATHER_REFRESH_HOURS):
            return None
        tried = self._weather_attempts.get(location.id)
        if tried and real_now - tried < timedelta(minutes=RETRY_MINUTES):
            return None
        ok, message = self.update_weather(location)
        return {"ok": ok, "message": message}

    def update_all(self, now, location=None):
        ok, message = self.update_now(now)
        if location is not None:
            w_ok, w_message = self.update_weather(location)
            if not w_ok:
                message += " " + w_message
            ok = ok and w_ok
        return ok, message

    def ensure_data(self, now):
        if not self.auto_update:
            return None
        status = self.data_status(now)
        if status["state"] != "none" and status["ageDays"] * 24 < REFRESH_AFTER_HOURS:
            return None
        if self._last_attempt and datetime.now(timezone.utc) - self._last_attempt < timedelta(minutes=RETRY_MINUTES):
            return None
        ok, message = self.update_now(now)
        return {"ok": ok, "message": message}

    def start_background_updates(self, clock, every_minutes=15):
        def loop():
            while True:
                try:
                    self.ensure_data(clock())
                    self.ensure_weather(self.repo.default_location())
                except Exception:
                    pass
                time.sleep(every_minutes * 60)
        threading.Thread(target=loop, daemon=True, name="data-updater").start()

    def upcoming(self, location, now, only_visible=True):
        status = self.data_status(now)
        if status["state"] in ("none", "expired"):
            return status, []
        t = self.repo.latest_tle()
        key = (t.line1, location.latitude, location.longitude)
        cached = self._cache.get(key)
        if cached is None or not (cached[0] <= now < cached[0] + timedelta(hours=CACHE_HOURS)):
            passes = self.predictor.passes(t, location, now - timedelta(minutes=20), DAYS_AHEAD,
                                           only_visible=False)
            self._cache = {key: (now, passes)}
            cached = self._cache[key]
        passes = [p for p in cached[1] if p.shown_end > now]
        if only_visible:
            passes = [p for p in passes if p.visible]
        return status, passes
