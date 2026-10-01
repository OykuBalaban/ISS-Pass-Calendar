import math
import unicodedata

import geonamescache


def normalize(text):
    text = text.replace("ı", "i").replace("İ", "i").casefold()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


class PlaceIndex:

    def __init__(self):
        gc = geonamescache.GeonamesCache()
        countries = {code: c["name"] for code, c in gc.get_countries().items()}
        self.places = {}
        self._index = []
        for c in gc.get_cities().values():
            place = {
                "id": c["geonameid"],
                "name": c["name"],
                "country": countries.get(c["countrycode"], c["countrycode"]),
                "latitude": c["latitude"],
                "longitude": c["longitude"],
                "timezone": c["timezone"],
                "population": c["population"],
            }
            self.places[place["id"]] = place
            alts = {normalize(a) for a in c.get("alternatenames", []) if a.isascii() and len(a) > 2}
            self._index.append((normalize(c["name"]), alts, place))

    def get(self, place_id):
        return self.places.get(place_id)

    def search(self, query, limit=8):
        q = normalize(query)
        if len(q) < 1:
            return []
        hits = []
        for name, alts, place in self._index:
            if name == q:
                rank = 0
            elif name.startswith(q):
                rank = 1
            elif any(a.startswith(q) for a in alts):
                rank = 2
            else:
                continue
            hits.append((rank, -place["population"], place))
        hits.sort(key=lambda h: (h[0], h[1]))
        return [h[2] for h in hits[:limit]]

    def locate(self, lat, lon, radius_km=10):
        around = [(p, distance_km(lat, lon, p["latitude"], p["longitude"])) for _, _, p in self._index]
        close = [(p, km) for p, km in around if km <= radius_km]
        if close:
            return max(close, key=lambda c: c[0]["population"])[0], True
        return min(around, key=lambda c: c[1])[0], False

    def nearest(self, lat, lon):
        best, best_km = None, float("inf")
        for _, _, p in self._index:
            km = distance_km(lat, lon, p["latitude"], p["longitude"])
            if km < best_km:
                best, best_km = p, km
        return best, best_km


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))
