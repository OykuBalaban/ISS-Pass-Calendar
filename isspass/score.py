FOG = {45, 48}


def is_wet(code):
    return code is not None and code >= 51


def geometry(max_elevation, minutes, sun_altitude):
    height = min(1.0, max(0.0, (max_elevation - 10) / 50))
    length = min(1.0, max(0.0, minutes / 5))
    darkness = min(1.0, max(0.0, (-sun_altitude - 6) / 12))
    return 0.5 * height + 0.3 * length + 0.2 * darkness


def weather_factor(clouds, code):
    if clouds is None:
        return 1.0
    factor = 1 - 0.9 * clouds / 100
    if code in FOG:
        factor *= 0.2
    elif is_wet(code):
        factor *= 0.3
    return factor


def chance(visible, max_elevation, minutes, sun_altitude, clouds, code):
    if not visible:
        return 0
    base = 4 + 6 * geometry(max_elevation, minutes, sun_altitude)
    return max(0, min(10, round(base * weather_factor(clouds, code))))
