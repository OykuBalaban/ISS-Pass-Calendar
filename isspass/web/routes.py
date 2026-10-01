from zoneinfo import ZoneInfo

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from isspass import score, tle, weather
from isspass.models import Location, now
from isspass.predictor import DIRECTION_WORDS, compass

bp = Blueprint("isspass", __name__)


def _ext(name):
    return current_app.extensions["isspass"][name]


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _loc_json(loc):
    return {"id": loc.id, "name": loc.name, "timezone": loc.timezone,
            "latitude": loc.latitude, "longitude": loc.longitude, "isDefault": loc.is_default,
            "isFavorite": loc.is_favorite}


def _dir(az):
    short = compass(az)
    return {"short": short, "words": DIRECTION_WORDS[short], "azimuth": az}


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/api/places")
def api_places():
    hits = _ext("places").search(request.args.get("q", ""))
    repo = _ext("repo")
    out = []
    for p in hits:
        known = repo.find_near(p["latitude"], p["longitude"])
        out.append({"id": p["id"], "name": p["name"], "country": p["country"],
                    "favorite": bool(known and known.is_favorite)})
    return jsonify(out)


@bp.get("/api/locations")
def api_locations():
    return jsonify([_loc_json(l) for l in _ext("repo").locations()])


@bp.post("/api/locations")
def api_add_location():
    body = request.get_json(silent=True) or {}
    places = _ext("places")
    if "placeId" in body:
        p = places.get(body["placeId"])
        if p is None:
            return jsonify({"error": "Unknown place."}), 404
        loc = Location(f"{p['name']}, {p['country']}", p["latitude"], p["longitude"], p["timezone"])
    else:
        try:
            lat, lon = float(body["latitude"]), float(body["longitude"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Send a placeId, or latitude and longitude."}), 400
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            return jsonify({"error": "Coordinates are out of range."}), 400
        town, inside = places.locate(lat, lon)
        name = str(body.get("name") or "").strip()[:60]
        if not name:
            name = f"{town['name'] if inside else 'Near ' + town['name']}, {town['country']}"
        loc = Location(name, round(lat, 4), round(lon, 4), town["timezone"])
    repo = _ext("repo")
    return jsonify(_loc_json(repo.location(repo.use_location(loc))))


@bp.get("/api/locations/recent")
def api_recent():
    return jsonify([_loc_json(l) for l in _ext("repo").recent()])


@bp.post("/api/locations/<int:loc_id>/favorite")
def api_favorite(loc_id):
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("favorite"), bool):
        return jsonify({"error": "Send {\"favorite\": true} or false."}), 400
    if not _ext("repo").set_favorite(loc_id, body["favorite"]):
        return jsonify({"error": "Unknown location."}), 404
    return jsonify(_loc_json(_ext("repo").location(loc_id)))


@bp.post("/api/locations/<int:loc_id>/select")
def api_select_location(loc_id):
    if not _ext("repo").set_default(loc_id):
        return jsonify({"error": "Unknown location."}), 404
    return jsonify({"ok": True})


@bp.delete("/api/locations/<int:loc_id>")
def api_delete_location(loc_id):
    if not _ext("repo").delete_location(loc_id):
        return jsonify({"error": "Unknown location."}), 404
    return jsonify({"ok": True})


@bp.get("/api/passes")
def api_passes():
    t = now()
    service = _ext("service")
    update = service.ensure_data(t)
    loc = _ext("repo").default_location()
    status, passes = (service.upcoming(loc, t, only_visible=request.args.get("all") != "1")
                      if loc else (service.data_status(t), []))
    forecast, fetched = None, None
    if loc:
        service.ensure_weather(loc)
        forecast, fetched = _ext("repo").weather(loc.id)
    return jsonify({
        "now": _iso(t),
        "location": _loc_json(loc) if loc else None,
        "favorites": [_loc_json(l) for l in _ext("repo").favorites()],
        "data": {**status, "epoch": _iso(status["epoch"]), "goodUntil": _iso(status["goodUntil"]),
                 "savedAt": _iso(status["savedAt"])},
        "update": update,
        "weather": _weather_json(forecast, fetched, loc, t) if loc else None,
        "passes": [{
            "start": _iso(p.shown_start),
            "end": _iso(p.shown_end),
            "peak": _iso(p.peak_time),
            "durationMin": round(p.duration_minutes(), 1),
            "visible": p.visible,
            "reason": p.reason,
            "from": {**_dir(p.start_azimuth), "elevation": p.start_elevation},
            "top": {**_dir(p.peak_azimuth), "elevation": p.max_elevation},
            "to": {**_dir(p.end_azimuth), "elevation": p.end_elevation},
            "path": p.path,
            **_sky_json(p, forecast),
        } for p in passes],
    })


def _sky_json(p, forecast):
    clouds, code = weather.weather_at(forecast, p.shown_start)
    return {
        "clouds": clouds,
        "sky": weather.sky(clouds),
        "wet": score.is_wet(code) or code in score.FOG,
        "weatherText": weather.CODES.get(code) if code is not None else None,
        "score": score.chance(p.visible, p.max_elevation, p.duration_minutes(), p.sun_altitude, clouds, code),
        "hasForecast": clouds is not None,
    }


def _weather_json(forecast, fetched, loc, t):
    if not forecast:
        return {"today": None, "cloudsNow": None, "fetchedAt": None}
    local_day = t.astimezone(ZoneInfo(loc.timezone)).date()
    return {
        "today": weather.day_summary(forecast, local_day),
        "cloudsNow": weather.clouds_at(forecast, t),
        "fetchedAt": _iso(fetched),
    }


@bp.post("/api/data/update")
def api_update():
    ok, message = _ext("service").update_all(now(), _ext("repo").default_location())
    return jsonify({"ok": ok, "message": message}), (200 if ok else 503)


@bp.get("/offline")
def offline_page():
    t = now()
    return render_template("offline.html", status=_ext("service").data_status(t), now=t)


@bp.post("/offline/update")
def offline_update():
    ok, message = _ext("service").update_now(now())
    flash(message, "ok" if ok else "error")
    return redirect(url_for("isspass.offline_page"))


@bp.post("/offline/file")
def offline_file():
    upload = request.files.get("file")
    text = request.form.get("tle", "")
    if upload and upload.filename:
        raw = upload.read(100_000)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            flash("That file is not a text file.", "error")
            return redirect(url_for("isspass.offline_page"))
    try:
        t = tle.parse(text)
    except tle.TleError as exc:
        flash(str(exc), "error")
        return redirect(url_for("isspass.offline_page"))
    _ext("repo").save_tle(t, now())
    _ext("service")._cache = {}
    flash(f"Orbit data loaded (from {t.epoch:%d.%m.%Y}).", "ok")
    return redirect(url_for("isspass.offline_page"))


@bp.get("/favorites")
def favorites_page():
    return render_template("favorites.html", locations=_ext("repo").favorites(),
                           current=_ext("repo").default_location())


@bp.post("/favorites/<int:loc_id>/remove")
def favorites_remove(loc_id):
    loc = _ext("repo").location(loc_id)
    if loc and _ext("repo").set_favorite(loc_id, False):
        flash(f"{loc.name} removed from favorites.", "ok")
    return redirect(url_for("isspass.favorites_page"))


@bp.post("/favorites/add-current")
def favorites_add_current():
    repo = _ext("repo")
    loc = repo.default_location()
    if loc is None:
        flash("Please select a location.", "error")
    elif loc.is_favorite:
        flash(f"{loc.name} is already in your favorites.", "ok")
    else:
        repo.set_favorite(loc.id, True)
        flash(f"{loc.name} added to favorites.", "ok")
    return redirect(url_for("isspass.favorites_page"))


@bp.post("/favorites/<int:loc_id>/select")
def favorites_select(loc_id):
    _ext("repo").set_default(loc_id)
    return redirect(url_for("isspass.index"))
