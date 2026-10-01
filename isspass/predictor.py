from datetime import timedelta

import numpy as np
from skyfield.api import EarthSatellite, Loader, wgs84
from skyfield_data import get_skyfield_data_path

from isspass.models import Pass

MIN_ELEVATION = 10.0
DARK_SUN_ALTITUDE = -6.0
MIN_VISIBLE_SECONDS = 30
STEP_SECONDS = 10


class PassPredictor:
    def __init__(self):
        load = Loader(get_skyfield_data_path(), expire=False, verbose=False)
        self.eph = load("de421.bsp")
        self.ts = load.timescale(builtin=True)

    def passes(self, tle, location, start, days=5, only_visible=True):
        sat = EarthSatellite(tle.line1, tle.line2, tle.name, self.ts)
        place = wgs84.latlon(location.latitude, location.longitude, elevation_m=location.elevation_m)
        t0 = self.ts.from_datetime(start)
        t1 = self.ts.from_datetime(start + timedelta(days=days))
        times, events = sat.find_events(place, t0, t1, altitude_degrees=MIN_ELEVATION)

        result = []
        rise = None
        for t, e in zip(times, events):
            if e == 0:
                rise = t
            elif e == 2 and rise is not None:
                p = self._describe(sat, place, rise, t)
                if p.visible or not only_visible:
                    result.append(p)
                rise = None
        return result

    def _describe(self, sat, place, rise, set_):
        seconds = (set_.utc_datetime() - rise.utc_datetime()).total_seconds()
        n = max(2, int(seconds / STEP_SECONDS) + 1)
        ts = self.ts.linspace(rise, set_, n)

        alt, az, _ = (sat - place).at(ts).altaz()
        alt, az = alt.degrees, az.degrees
        sunlit = sat.at(ts).is_sunlit(self.eph)
        observer = self.eph["earth"] + place
        sun_alt = observer.at(ts).observe(self.eph["sun"]).apparent().altaz()[0].degrees

        visible = sunlit & (sun_alt < DARK_SUN_ALTITUDE) & (alt >= MIN_ELEVATION)
        i0, i1 = _longest_run(visible)
        is_visible = i0 is not None and (i1 - i0) * seconds / (n - 1) >= MIN_VISIBLE_SECONDS
        reason = None
        if not is_visible:
            i0, i1 = 0, n - 1
            reason = _why_not_visible(sunlit, sun_alt, alt)

        idx = np.linspace(i0, i1, num=min(32, i1 - i0 + 1)).round().astype(int)
        ip = i0 + int(alt[i0:i1 + 1].argmax())
        return Pass(
            rise=rise.utc_datetime(),
            set=set_.utc_datetime(),
            max_elevation=round(float(alt[ip]), 1),
            visible=bool(is_visible),
            shown_start=ts[i0].utc_datetime(),
            shown_end=ts[i1].utc_datetime(),
            start_azimuth=round(float(az[i0]), 1),
            end_azimuth=round(float(az[i1]), 1),
            start_elevation=round(float(alt[i0]), 1),
            end_elevation=round(float(alt[i1]), 1),
            peak_time=ts[ip].utc_datetime(),
            peak_azimuth=round(float(az[ip]), 1),
            sun_altitude=round(float(sun_alt[i0]), 1),
            reason=reason,
            path=[(round(float(az[i]), 1), round(float(alt[i]), 1), round((i - i0) * seconds / (n - 1))) for i in idx],
        )


def _why_not_visible(sunlit, sun_alt, alt):
    up = alt >= MIN_ELEVATION
    if not up.any():
        return "too low"
    if (sun_alt[up] >= DARK_SUN_ALTITUDE).mean() >= 0.5:
        return "daylight"
    if (~sunlit[up]).mean() >= 0.5:
        return "Earth's shadow"
    return "too short"


def _longest_run(mask):
    best, start = (None, None), None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if best[0] is None or i - 1 - start > best[1] - best[0]:
                best = (start, i - 1)
            start = None
    return best


DIRECTION_WORDS = {
    "N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast",
    "E": "east", "ESE": "east-southeast", "SE": "southeast", "SSE": "south-southeast",
    "S": "south", "SSW": "south-southwest", "SW": "southwest", "WSW": "west-southwest",
    "W": "west", "WNW": "west-northwest", "NW": "northwest", "NNW": "north-northwest",
}


def compass(azimuth):
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((azimuth % 360) / 22.5 + 0.5) % 16]
