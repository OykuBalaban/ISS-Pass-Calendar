import json
import sqlite3
import threading
from datetime import datetime, timezone

from isspass.models import Location, TleSet
from isspass.places import distance_km

SCHEMA = """
CREATE TABLE IF NOT EXISTS tle (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, line1 TEXT, line2 TEXT,
    epoch TEXT, source TEXT, saved_at TEXT);
CREATE TABLE IF NOT EXISTS location (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, latitude REAL, longitude REAL,
    elevation_m REAL DEFAULT 0, timezone TEXT, is_default INTEGER DEFAULT 0,
    is_favorite INTEGER DEFAULT 0, last_used TEXT);
CREATE TABLE IF NOT EXISTS weather (
    location_id INTEGER PRIMARY KEY, fetched_at TEXT, forecast TEXT);
"""
COLUMNS = "id, name, latitude, longitude, elevation_m, timezone, is_default, is_favorite"
RECENT = 5
SAME_PLACE_KM = 10.0


class Repository:
    def __init__(self, db_path):
        self._con = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._con:
            self._con.executescript(SCHEMA)
            self._migrate()

    def _migrate(self):
        cols = [r[1] for r in self._con.execute("PRAGMA table_info(location)")]
        if "is_favorite" not in cols:
            self._con.execute("ALTER TABLE location ADD COLUMN is_favorite INTEGER DEFAULT 0")
            self._con.execute("ALTER TABLE location ADD COLUMN last_used TEXT")
            self._con.execute("UPDATE location SET is_favorite = 1")


    def save_tle(self, t: TleSet, saved_at):
        with self._lock, self._con:
            self._con.execute("INSERT INTO tle (name, line1, line2, epoch, source, saved_at) VALUES (?, ?, ?, ?, ?, ?)",
                              (t.name, t.line1, t.line2, t.epoch.isoformat(), t.source, saved_at.isoformat()))
            self._con.execute("DELETE FROM tle WHERE id NOT IN (SELECT id FROM tle ORDER BY id DESC LIMIT 10)")

    def latest_tle(self):
        with self._lock:
            row = self._con.execute("SELECT name, line1, line2, epoch, source, saved_at FROM tle "
                                    "ORDER BY epoch DESC, id DESC LIMIT 1").fetchone()
        if not row:
            return None
        return TleSet(row[0], row[1], row[2], datetime.fromisoformat(row[3]), row[4],
                      datetime.fromisoformat(row[5]) if row[5] else None)

    def save_weather(self, loc_id, forecast, fetched_at):
        with self._lock, self._con:
            self._con.execute("INSERT OR REPLACE INTO weather VALUES (?, ?, ?)",
                              (loc_id, fetched_at.isoformat(), json.dumps(forecast)))

    def weather(self, loc_id):
        with self._lock:
            row = self._con.execute("SELECT fetched_at, forecast FROM weather WHERE location_id = ?",
                                    (loc_id,)).fetchone()
        if not row:
            return None, None
        return json.loads(row[1]), datetime.fromisoformat(row[0])


    def _row(self, r):
        return Location(r[1], r[2], r[3], r[5], r[4], r[0], bool(r[6]), bool(r[7]))

    def _query(self, where="", order="name", limit=None):
        sql = f"SELECT {COLUMNS} FROM location {where} ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self._lock:
            return [self._row(r) for r in self._con.execute(sql).fetchall()]

    def locations(self):
        return self._query()

    def favorites(self):
        return self._query("WHERE is_favorite = 1")

    def recent(self, limit=RECENT):
        return self._query("WHERE last_used IS NOT NULL", "last_used DESC", limit)

    def location(self, loc_id):
        found = self._query(f"WHERE id = {int(loc_id)}")
        return found[0] if found else None

    def default_location(self):
        found = self._query("WHERE is_default = 1")
        return found[0] if found else None

    def find_near(self, lat, lon, km=SAME_PLACE_KM):
        for loc in self.locations():
            if distance_km(lat, lon, loc.latitude, loc.longitude) < km:
                return loc
        return None

    def use_location(self, loc: Location):
        existing = self.find_near(loc.latitude, loc.longitude)
        stamp = datetime.now(timezone.utc).isoformat()
        with self._lock, self._con:
            if existing:
                loc_id = existing.id
                self._con.execute("UPDATE location SET last_used = ? WHERE id = ?", (stamp, loc_id))
            else:
                loc_id = self._con.execute(
                    "INSERT INTO location (name, latitude, longitude, elevation_m, timezone, last_used) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (loc.name, loc.latitude, loc.longitude, loc.elevation_m, loc.timezone, stamp)).lastrowid
            self._con.execute("UPDATE location SET is_default = (id = ?)", (loc_id,))
            self._prune()
        return loc_id

    def _prune(self):
        self._con.execute(
            "DELETE FROM location WHERE is_favorite = 0 AND is_default = 0 AND id NOT IN "
            "(SELECT id FROM location WHERE last_used IS NOT NULL ORDER BY last_used DESC LIMIT ?)", (RECENT,))
        self._con.execute("DELETE FROM weather WHERE location_id NOT IN (SELECT id FROM location)")

    def set_default(self, loc_id):
        with self._lock, self._con:
            if not self._con.execute("SELECT 1 FROM location WHERE id = ?", (loc_id,)).fetchone():
                return False
            self._con.execute("UPDATE location SET is_default = (id = ?)", (loc_id,))
            return True

    def set_favorite(self, loc_id, favorite):
        with self._lock, self._con:
            cur = self._con.execute("UPDATE location SET is_favorite = ? WHERE id = ?", (int(favorite), loc_id))
            self._prune()
            return cur.rowcount == 1

    def delete_location(self, loc_id):
        with self._lock, self._con:
            was_default = self._con.execute("SELECT is_default FROM location WHERE id = ?", (loc_id,)).fetchone()
            self._con.execute("DELETE FROM location WHERE id = ?", (loc_id,))
            self._con.execute("DELETE FROM weather WHERE location_id = ?", (loc_id,))
            if was_default and was_default[0]:
                self._con.execute("UPDATE location SET is_default = 1 WHERE id = "
                                  "(SELECT id FROM location ORDER BY is_favorite DESC, last_used DESC LIMIT 1)")
            return was_default is not None
